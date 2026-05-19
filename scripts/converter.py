"""Core converter — orchestrates single file, batch, and plan operations."""

import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config_loader import load_config, get_output_dir, get_supported_extensions, get_manifest_path
from .manifest_manager import (
    load_manifest,
    check_converted,
    upsert_file_record,
    compute_sha256,
    ManifestLoadError,
    ManifestSaveError,
)
from .mineru_caller import run_mineru, MineruError
from .file_organizer import move_mineru_output, OrganizerError


class ConvertError(Exception):
    """Base exception for conversion operations."""


def _get_format(file_path: Path) -> str:
    """Return lowercase file extension."""
    return file_path.suffix.lower()


def _is_supported(file_path: Path, config: Optional[Dict] = None) -> bool:
    """Check if a file extension is supported."""
    return file_path.suffix.lower() in get_supported_extensions(config)


def _collect_files(input_path: Path) -> List[Path]:
    """Recursively collect supported files from a directory, or return the single file."""
    input_path = Path(input_path).expanduser().resolve()
    config = load_config()

    if input_path.is_file():
        return [input_path]

    files = []
    for ext in config.get("supported_extensions", []):
        files.extend(input_path.rglob(f"*{ext}"))

    return sorted(files)


def _parse_page_range(pages_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse page range string like '3-5' into (start, end) 0-indexed.
    Single page '3' returns (2, 2).

    Returns:
        (start_page, end_page) as 0-indexed ints, or (None, None).
    """
    if not pages_str:
        return None, None
    pages_str = pages_str.strip()
    if "-" in pages_str:
        parts = pages_str.split("-", 1)
        start = int(parts[0]) - 1
        end = int(parts[1]) - 1
        return start, end
    else:
        page = int(pages_str) - 1
        return page, page


def convert_single(
    file_path: Path,
    output_dir: Optional[Path] = None,
    force: bool = False,
    verbose: bool = False,
    pages: Optional[str] = None,
    method: Optional[str] = None,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert a single file.

    Args:
        pages: Page range string, e.g. '3-5' (1-indexed). Only for PDF.
        method: PDF parsing method — 'auto', 'txt', 'ocr'.
        lang: Document language code.

    Returns:
        Dict with keys: path, status (success/skipped/failed), error, details
    """
    file_path = Path(file_path).expanduser().resolve()
    output_dir = Path(output_dir or get_output_dir()).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse page range
    start_page, end_page = _parse_page_range(pages) if pages else (None, None)

    result = {
        "path": str(file_path),
        "status": "pending",
        "error": None,
        "details": None,
    }

    # Check if supported
    if not _is_supported(file_path):
        result["status"] = "skipped"
        result["error"] = f"Unsupported format: {file_path.suffix}"
        return result

    # Check if already converted
    manifest = load_manifest(get_manifest_path(output_dir))
    is_converted, new_hash = check_converted(file_path, manifest)

    if is_converted and not force:
        result["status"] = "skipped"
        return result

    file_format = _get_format(file_path)
    file_hash = new_hash or _get_file_hash(file_path)

    # EPUB conversion — does not use MinerU
    if file_format == ".epub":
        return _convert_epub_workflow(
            file_path, output_dir, file_format, result,
        )

    try:
        # Step 1: Run MinerU
        tmp_dir = output_dir / f".tmp_mineru_{uuid.uuid4().hex[:8]}"
        mineru_results = run_mineru(
            file_path, tmp_dir, verbose=verbose,
            start_page=start_page, end_page=end_page,
            method=method, lang=lang,
        )

        if not mineru_results:
            raise MineruError("MinerU produced no output")

        # Use the first (and usually only) output subdirectory from MinerU
        mineru_subdir = Path(mineru_results[0]["subdir"])

        # Step 2: Move outputs and rewrite paths
        final_result = move_mineru_output(mineru_subdir, output_dir)

        # Step 3: Cleanup temp MinerU directory
        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass

        # Step 4: Update manifest (atomic load-modify-save)
        attachments_rel = f"attachments/{final_result['hash_prefix']}"
        md_rel = Path(final_result["md_path"]).relative_to(output_dir)
        upsert_file_record(
            file_path,
            output_md=str(md_rel),
            output_attachments=attachments_rel,
            file_format=file_format,
            status="success",
        )

        result["status"] = "success"
        result["details"] = {
            "md_path": str(final_result["md_path"]),
            "attachments_path": final_result["attachments_path"],
            "images": final_result["image_count"],
        }

    except MineruError as e:
        result["status"] = "failed"
        result["error"] = f"MinerU error: {e}"
        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass
        try:
            upsert_file_record(
                file_path,
                output_md="", output_attachments="",
                file_format=file_format,
                status="failed", error=str(e),
            )
        except ManifestSaveError:
            pass

    except OrganizerError as e:
        result["status"] = "failed"
        result["error"] = f"Organization error: {e}"
        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass

    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"Unexpected error: {e}"
        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass

    return result


def convert_batch(
    dir_path: Path,
    output_dir: Optional[Path] = None,
    force: bool = False,
    workers: int = 1,
    verbose: bool = False,
    method: Optional[str] = None,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert all supported files in a directory.

    Args:
        method: PDF parsing method applied to all files.
        lang: Document language applied to all files.

    Returns:
        Dict with scanned, processed, skipped, failed counts and per-file results.
    """
    dir_path = Path(dir_path).expanduser().resolve()
    output_dir = Path(output_dir or get_output_dir()).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_files(dir_path)
    if not files:
        return {
            "scanned": 0, "processed": 0, "skipped": 0, "failed": 0,
            "items": [], "message": f"No supported files found in {dir_path}",
        }

    results = []
    stats = {"scanned": len(files), "processed": 0, "skipped": 0, "failed": 0}

    def _convert_one(fp: Path) -> Dict[str, Any]:
        return convert_single(fp, output_dir, force=force, verbose=verbose, method=method, lang=lang)

    # Single-threaded by default for manifest safety; parallel if workers > 1
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_convert_one, fp): fp for fp in files}
            for future in as_completed(futures):
                try:
                    r = future.result()
                except Exception as e:
                    r = {"path": str(futures[future]), "status": "failed", "error": str(e), "details": None}
                results.append(r)
    else:
        for fp in files:
            results.append(_convert_one(fp))

    # Aggregate stats
    for r in results:
        if r["status"] == "skipped":
            stats["skipped"] += 1
        elif r["status"] == "success":
            stats["processed"] += 1
        elif r["status"] == "failed":
            stats["failed"] += 1

    stats["items"] = results
    return stats


def build_plan(
    dir_path: Path,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Build a conversion plan: which files are skip vs process.

    Returns:
        Dict with scanned count, skip list, process list, and failed list.
    """
    dir_path = Path(dir_path).expanduser().resolve()
    output_dir = Path(output_dir or get_output_dir()).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_files(dir_path)
    manifest = load_manifest(get_manifest_path(output_dir))

    plan = {
        "source_dir": str(dir_path),
        "output_dir": str(output_dir),
        "scanned": len(files),
        "skip": [],
        "process": [],
        "unsupported": [],
    }

    for fp in files:
        if not _is_supported(fp):
            plan["unsupported"].append({"path": str(fp), "reason": f"Unsupported format: {fp.suffix}"})
            continue

        is_converted, _ = check_converted(fp, manifest)
        entry = {"path": str(fp)}

        if is_converted:
            # Check if content has changed
            file_hash = _get_file_hash(fp)
            # Find existing record by filename
            found = False
            for hk, record in manifest.get("files", {}).items():
                if record.get("source_filename") == fp.name:
                    if hk == file_hash:
                        entry["reason"] = "Already converted"
                    else:
                        entry["reason"] = "Modified (re-conversion needed)"
                    break
            if not found:
                entry["reason"] = "Already converted"
            plan["skip"].append(entry)
        else:
            plan["process"].append(entry)

    return plan


def get_status(
    output_dir: Optional[Path] = None,
    list_converted: bool = False,
    list_failed: bool = False,
) -> Dict[str, Any]:
    """Get conversion status statistics."""
    output_dir = Path(output_dir or get_output_dir()).expanduser().resolve()
    manifest = load_manifest(get_manifest_path(output_dir))

    files = manifest.get("files", {})
    status = {
        "output_dir": str(output_dir),
        "total": len(files),
        "success": 0,
        "failed": 0,
        "converted": [],
        "failed_list": [],
    }

    for hash_key, record in files.items():
        if record.get("status") == "success":
            status["success"] += 1
            if list_converted:
                status["converted"].append({
                    "file": record.get("source_filename"),
                    "format": record.get("format"),
                    "converted_at": record.get("converted_at"),
                })
        else:
            status["failed"] += 1
            if list_failed:
                status["failed_list"].append({
                    "file": record.get("source_filename"),
                    "error": record.get("error"),
                })

    return status


def _get_file_hash(file_path: Path) -> str:
    """Helper to compute file hash (wrapper for manifest_manager.compute_sha256)."""
    return compute_sha256(file_path)


def _convert_epub_workflow(
    file_path: Path,
    output_dir: Path,
    file_format: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Convert an EPUB file and record the result in the manifest."""
    from .epub_converter import convert_epub, EpubConvertError

    manifest_path = get_manifest_path(output_dir)

    try:
        final_result = convert_epub(file_path, output_dir)

        attachments_rel = f"attachments/{final_result['hash_prefix']}"
        md_rel = Path(final_result["md_path"]).relative_to(output_dir)
        upsert_file_record(
            file_path,
            output_md=str(md_rel),
            output_attachments=attachments_rel,
            file_format=file_format,
            status="success",
            manifest_path=manifest_path,
        )

        result["status"] = "success"
        result["details"] = {
            "md_path": str(final_result["md_path"]),
            "attachments_path": final_result["attachments_path"],
            "images": final_result["image_count"],
        }

    except EpubConvertError as e:
        result["status"] = "failed"
        result["error"] = f"EPUB conversion error: {e}"
        try:
            upsert_file_record(
                file_path,
                output_md="", output_attachments="",
                file_format=file_format,
                status="failed", error=str(e),
                manifest_path=manifest_path,
            )
        except ManifestSaveError:
            pass

    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"Unexpected EPUB error: {e}"
        try:
            upsert_file_record(
                file_path,
                output_md="", output_attachments="",
                file_format=file_format,
                status="failed", error=str(e),
                manifest_path=manifest_path,
            )
        except ManifestSaveError:
            pass

    return result
