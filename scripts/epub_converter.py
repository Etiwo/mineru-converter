"""EPUB to Markdown converter — standalone, does not depend on MinerU.

Extracts images, converts HTML content to Markdown, and rewrites
image paths to the `attachments/<hash>/` convention used by
the mineru-converter skill.
"""

import hashlib
import re
from pathlib import Path
from typing import Dict, Any, Optional

from ebooklib import epub
from html2text import HTML2Text

from .config_loader import load_config

ITEM_IMAGE = 1
ITEM_DOCUMENT = 9


class EpubConvertError(Exception):
    """Base exception for EPUB conversion."""


def convert_epub(
    epub_path: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """Convert an EPUB file to Markdown and extract its images.

    Args:
        epub_path: Path to the .epub file.
        output_dir: Root output directory (e.g. ``./raw``).

    Returns:
        Dict with keys:
          - md_path: absolute path to the written .md file
          - attachments_path: absolute path to the images subdirectory
          - image_count: number of extracted images
          - hash_prefix: 8-char hex prefix used for the attachments folder
    """
    epub_path = Path(epub_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    file_hash = _compute_file_hash(epub_path)
    config = load_config()
    org = config.get("organizer", {})
    hash_prefix_len = org.get("hash_prefix_length", 8)
    hash_prefix = file_hash[:hash_prefix_len]
    attachments_dir_name = org.get("attachments_dir", "attachments")
    attachments_path = output_dir / attachments_dir_name / hash_prefix
    attachments_path.mkdir(parents=True, exist_ok=True)

    book = epub.read_epub(str(epub_path))

    name_map = _extract_images(book, attachments_path)
    md_content = _convert_content(book)
    md_content = _rewrite_image_paths(
        md_content,
        f"{attachments_dir_name}/{hash_prefix}",
        name_map,
    )

    md_path = output_dir / _derive_filename(book, epub_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_content, encoding="utf-8")

    return {
        "md_path": str(md_path.resolve()),
        "attachments_path": str(attachments_path.resolve()),
        "image_count": len(name_map) // 2,
        "hash_prefix": hash_prefix,
    }


def _compute_file_hash(file_path: Path) -> str:
    """SHA-256 of the entire EPUB file (used for attachment folder naming)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_images(
    book: epub.EpubBook,
    attachments_dir: Path,
) -> Dict[str, str]:
    """Save every image embedded in the EPUB to *attachments_dir*.

    Returns a mapping of *both* the original EPUB path (``images/foo.jpg``)
    and bare filename (``foo.jpg``) → the filename used on disk, so that
    path rewriting can succeed regardless of how the HTML references the
    image.
    """
    name_map: Dict[str, str] = {}
    for item in book.get_items():
        if item.get_type() != ITEM_IMAGE:
            continue
        orig = item.get_name()
        base = Path(orig).name
        if not base:
            continue

        dest = attachments_dir / base
        if dest.exists():
            stem = Path(base).stem
            counter = 1
            while dest.exists():
                dest = attachments_dir / f"{stem}_{counter}{Path(base).suffix}"
                counter += 1

        attachments_dir.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(item.get_content())

        name_map[orig] = dest.name
        name_map[base] = dest.name

    return name_map


def _convert_content(book: epub.EpubBook) -> str:
    """Walk every ``ITEM_DOCUMENT`` in spine order and convert to Markdown."""
    h = HTML2Text()
    h.body_width = 0
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.unicode_snob = True
    h.single_line_break = True

    parts: list[str] = []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        content = item.get_body_content().decode("utf-8", errors="replace")
        md = h.handle(content)
        parts.append(md)

    return "\n\n".join(parts)


def _rewrite_image_paths(
    md_content: str,
    attachments_rel: str,
    name_map: Dict[str, str],
) -> str:
    """Replace every ``![alt](<any-path>)`` with the correct attachments path.

    Uses *name_map* (built by :func:`_extract_images`) to look up the
    actual saved filename regardless of the original reference style
    (``images/x.jpg``, ``../images/x.jpg``, ``OEBPS/x.jpg``, …).
    """

    def _replacer(m):
        alt = m.group(1)
        ref = m.group(2)
        basename = Path(ref).name
        saved = name_map.get(ref) or name_map.get(basename) or basename
        return f"![{alt}]({attachments_rel}/{saved})"

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _replacer, md_content)


def _derive_filename(book: epub.EpubBook, epub_path: Path) -> str:
    """Produce a human-friendly ``.md`` filename from metadata or the file path."""

    title: Optional[str] = None
    try:
        title = book.get_metadata("DC", "title")
        if title:
            title = title[0][0]
    except Exception:
        pass

    stem = (title or epub_path.stem).strip()
    stem = re.sub(r'[\\/:*?"<>|]', "_", stem)
    if len(stem) > 128:
        stem = stem[:128]
    return f"{stem}.md"
