"""File organizer — moves outputs, rewrites image paths, cleans up temp files."""

import hashlib
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config_loader import load_config
from .manifest_manager import compute_sha256


class OrganizerError(Exception):
    """Base exception for file organization operations."""


def _hash_dir(dir_path: Path) -> str:
    """Compute a hash based on all files within a directory (for grouping attachments)."""
    h = hashlib.sha256()
    for f in sorted(dir_path.rglob("*")):
        if f.is_file():
            h.update(f.name.encode())
            h.update(str(f.stat().st_size).encode())
    return h.hexdigest()


class ImagePathRewriteError(OrganizerError):
    """Failed to rewrite image paths in markdown."""


def move_mineru_output(
    mineru_output_dir: Path,
    target_output_dir: Path,
) -> Dict[str, Any]:
    """
    Extract markdown and images from MinerU output, move to target directory,
    and clean up temporary MinerU subdirectories.

    Args:
        mineru_output_dir: The top-level directory where MinerU wrote results.
        target_output_dir: The target output directory (raw/).

    Returns:
        Dict with keys:
          - md_path: Path to the final markdown file
          - attachments_path: Path to the attachments subdirectory
          - md_content: Content of the markdown file (for path rewriting)
    """
    mineru_output_dir = Path(mineru_output_dir).resolve()
    target_output_dir = Path(target_output_dir).expanduser().resolve()
    target_output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    organizer_config = config.get("organizer", {})
    attachments_dir_name = organizer_config.get("attachments_dir", "attachments")
    hash_prefix_len = organizer_config.get("hash_prefix_length", 8)

    # Compute hash for attachments folder (from md files' content)
    md_files = list(mineru_output_dir.rglob("*.md"))
    if md_files:
        file_hash = compute_sha256(md_files[0])
    else:
        file_hash = _hash_dir(mineru_output_dir)
    hash_prefix = file_hash[:hash_prefix_len]
    attachments_path = target_output_dir / attachments_dir_name / hash_prefix
    attachments_path.mkdir(parents=True, exist_ok=True)

    # Find all .md files in the mineru output
    md_files = []
    for md_file in mineru_output_dir.rglob("*.md"):
        if md_file.is_file() and md_file.stat().st_size > 0:
            md_files.append(md_file)

    if not md_files:
        raise OrganizerError(f"No valid markdown files found in {mineru_output_dir}")

    # Use the .md file whose name most closely matches the input directory name
    input_dir_name = mineru_output_dir.name.lower()
    md_file = _select_best_md(md_files, input_dir_name)

    # Copy images to attachments — search recursively (MinerU v3.x puts images in subdirs)
    images_src = None
    for img_dir in mineru_output_dir.rglob("images"):
        if img_dir.is_dir() and any(img_dir.iterdir()):
            images_src = img_dir
            break

    image_count = 0
    if images_src is not None:
        image_count = _copy_images(images_src, attachments_path)

    # Determine the target MD filename
    md_filename = _get_md_filename(md_file)
    md_dest = target_output_dir / md_filename

    # Read content, rewrite image paths, then write
    md_content = md_file.read_text(encoding="utf-8")
    md_content = rewrite_image_paths(md_content, attachments_dir_name, hash_prefix)
    md_dest.write_text(md_content, encoding="utf-8")

    return {
        "md_path": str(md_dest),
        "attachments_path": str(attachments_path),
        "md_content": md_content,
        "image_count": image_count,
        "hash_prefix": hash_prefix,
    }


def _select_best_md(md_files: List[Path], input_dir_name: str) -> Path:
    """
    Select the most appropriate .md file from the MinerU output.
    Prefers files whose stem matches the input directory name.
    """
    for md_file in md_files:
        stem = md_file.stem.lower()
        if input_dir_name in stem or stem in input_dir_name:
            return md_file

    # Fallback: pick the file with the most content
    return max(md_files, key=lambda f: f.stat().st_size)


def _get_md_filename(md_file: Path) -> str:
    """
    Derive a clean filename for the output markdown.
    Uses the md file's stem, replacing characters that are invalid in filenames.
    """
    stem = md_file.stem
    # Replace characters that could be problematic
    stem = re.sub(r'[\\/:*?"<>|]', '_', stem)
    # Limit length
    if len(stem) > 128:
        stem = stem[:128]
    return f"{stem}.md"


def _copy_images(images_src: Path, attachments_dest: Path) -> int:
    """
    Copy all images from source to destination, handling name conflicts
    by appending a numeric suffix.

    Returns the number of images copied.
    """
    count = 0
    for img_file in sorted(images_src.iterdir()):
        if not img_file.is_file():
            continue
        ext = img_file.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"):
            continue

        dest = attachments_dest / img_file.name
        if dest.exists():
            # Handle conflicts
            counter = 1
            base = img_file.stem
            while dest.exists():
                dest = attachments_dest / f"{base}_{counter}{ext}"
                counter += 1
        shutil.copy2(str(img_file), str(dest))
        count += 1

    return count


def rewrite_image_paths(
    md_content: str,
    attachments_base: str = "attachments",
    hash_prefix: str = "",
) -> str:
    """
    Rewrite image paths in markdown content.

    Converts paths like:
      - ![alt](images/img.png)
      - ![alt](./images/img.png)
    To:
      - ![alt](attachments/<hash>/img.png)

    Args:
        md_content: The markdown content to rewrite.
        attachments_base: Base name for the attachments directory (default: "attachments").
        hash_prefix: The hash prefix for the attachments subdirectory.

    Returns:
        The rewritten markdown content.
    """
    # Pattern matches ![...](path) where path starts with images/ or ./images/
    pattern = re.compile(
        r'(!\[[^\]]*\])\((?:\./)?images/([^)]+)\)'
    )

    def replacer(match):
        prefix = match.group(1)
        img_name = match.group(2)
        return f"{prefix}({attachments_base}/{hash_prefix}/{img_name})"

    return pattern.sub(replacer, md_content)


def cleanup_mineru_subdirs(output_dir: Path, keep_subdirs: Optional[List[str]] = None) -> int:
    """
    Remove temporary subdirectories created by MinerU that are no longer needed.

    Args:
        output_dir: The top-level output directory.
        keep_subdirs: List of subdirectory names to keep (relative to output_dir).

    Returns:
        Number of directories removed.
    """
    output_dir = Path(output_dir).resolve()
    keep_subdirs = keep_subdirs or []
    removed = 0

    for item in output_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name in keep_subdirs:
            continue
        try:
            shutil.rmtree(item)
            removed += 1
        except OSError:
            pass

    return removed
