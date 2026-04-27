"""Manifest manager for tracking converted files with SHA256 hashing and file locking."""

import hashlib
import json
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from contextlib import contextmanager

from .config_loader import load_config, get_output_dir, get_manifest_path


class ManifestError(Exception):
    """Base exception for manifest operations."""


class ManifestLoadError(ManifestError):
    """Failed to load manifest."""


class ManifestSaveError(ManifestError):
    """Failed to save manifest."""


@contextmanager
def _locked_file(file_path: Path, mode: str = "r+"):
    """Context manager that applies file locking for safe concurrent access."""
    if not file_path.exists() and "r" not in mode:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(file_path, mode)
    else:
        fd = open(file_path, mode)

    try:
        if "r" in mode:
            fcntl.flock(fd, fcntl.LOCK_SH)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    file_path = Path(file_path).expanduser().resolve()
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_manifest(manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load manifest.json from disk."""
    if manifest_path is None:
        output_dir = get_output_dir()
        manifest_path = get_manifest_path(output_dir)

    if not manifest_path.exists():
        return {
            "version": load_config().get("manifest", {}).get("version", "1.0"),
            "files": {},
        }

    try:
        with _locked_file(manifest_path, "r") as f:
            content = f.read()
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        raise ManifestLoadError(f"Failed to load manifest from {manifest_path}: {e}")


def save_manifest(manifest: Dict[str, Any], manifest_path: Optional[Path] = None) -> None:
    """Save manifest to disk with file locking."""
    if manifest_path is None:
        output_dir = get_output_dir()
        manifest_path = get_manifest_path(output_dir)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with _locked_file(manifest_path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            f.truncate()
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise ManifestSaveError(f"Failed to save manifest to {manifest_path}: {e}")


def upsert_file_record(
    file_path: Path,
    output_md: str,
    output_attachments: str,
    file_format: str,
    status: str = "success",
    error: Optional[str] = None,
    manifest_path: Optional[Path] = None,
) -> None:
    """Atomically load manifest, add/update a file record, and save — all under one lock."""
    if manifest_path is None:
        output_dir = get_output_dir()
        manifest_path = get_manifest_path(output_dir)

    file_path = Path(file_path).expanduser().resolve()
    manifest_path = Path(manifest_path).expanduser().resolve()

    file_hash = compute_sha256(file_path)
    record = build_record(
        source_path=file_path,
        output_md=output_md,
        output_attachments=output_attachments,
        file_format=file_format,
        status=status,
        error=error,
    )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure file exists before opening for read+write
    if not manifest_path.exists():
        json.dump(
            {"version": load_config().get("manifest", {}).get("version", "1.0"), "files": {}},
            open(manifest_path, "w"),
        )
    try:
        with open(manifest_path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            content = f.read()
            if not content:
                content = "{}"
            try:
                manifest = json.loads(content)
            except json.JSONDecodeError:
                manifest = {"version": load_config().get("manifest", {}).get("version", "1.0"), "files": {}}
            manifest.setdefault("files", {})[file_hash] = record
            f.seek(0)
            f.truncate()
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.flush()
    except IOError as e:
        raise ManifestSaveError(f"Failed to save manifest to {manifest_path}: {e}")


def upsert_record(manifest: Dict[str, Any], file_hash: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update a file record in the manifest."""
    manifest.setdefault("files", {})[file_hash] = record
    return manifest


def build_record(
    source_path: Path,
    output_md: str,
    output_attachments: str,
    file_format: str,
    status: str = "success",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a manifest record for a converted file."""
    return {
        "source_path": str(Path(source_path).expanduser().resolve()),
        "source_filename": source_path.name,
        "output_md": output_md,
        "output_attachments": output_attachments,
        "format": file_format,
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error": error,
    }


def check_converted(
    file_path: Path,
    manifest: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Check if a file has already been converted.
    Returns (is_converted, hash_key).
    """
    file_path = Path(file_path).expanduser().resolve()
    file_hash = compute_sha256(file_path)

    files = manifest.get("files", {})
    for hash_key, record in files.items():
        if record.get("source_path") == str(file_path):
            # Source path matches — check if hash changed
            if hash_key == file_hash:
                return True, hash_key
            else:
                # File modified — return not converted but with new hash
                return False, file_hash
        # Also check by source_filename + size as fallback
        if record.get("source_filename") == file_path.name:
            existing_size = record.get("source_size")
            current_size = file_path.stat().st_size
            if existing_size == current_size:
                if hash_key == file_hash:
                    return True, hash_key

    return False, file_hash


def add_conversion_record(
    manifest: Dict[str, Any],
    file_path: Path,
    output_md: str,
    output_attachments: str,
    file_format: str,
    status: str = "success",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a conversion record to the manifest and return the hash key."""
    file_hash = compute_sha256(file_path)
    record = build_record(
        source_path=file_path,
        output_md=output_md,
        output_attachments=output_attachments,
        file_format=file_format,
        status=status,
        error=error,
    )
    manifest = upsert_record(manifest, file_hash, record)
    return manifest
