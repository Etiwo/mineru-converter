"""Tests for epub_converter module and EPUB integration in converter.py."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from ebooklib import epub

from scripts.epub_converter import (
    convert_epub,
    _compute_file_hash,
    _extract_images,
    _convert_content,
    _rewrite_image_paths,
    _derive_filename,
    EpubConvertError,
)
from scripts.converter import convert_single, _convert_epub_workflow


# ---------------------------------------------------------------------------
# Helpers — build minimal EPUB fixtures
# ---------------------------------------------------------------------------

def _make_minimal_epub(tmp_dir: Path) -> Path:
    """Create an EPUB with one section of text and one embedded image."""
    book = epub.EpubBook()
    book.set_identifier("test-001")
    book.set_title("Test Book")
    book.set_language("en")

    chapter = epub.EpubHtml(
        title="Chapter 1",
        file_name="chap_01.xhtml",
        lang="en",
    )
    chapter.content = (
        "<html><body>"
        "<h1>Chapter 1</h1>"
        "<p>Hello world.</p>"
        '<p><img src="../images/cover.png" alt="Cover"/></p>'
        "</body></html>"
    ).encode("utf-8")
    book.add_item(chapter)

    cover = epub.EpubImage()
    cover.file_name = "images/cover.png"
    cover.content = b"\x89PNG\r\n\x1a\n" + b"fake" * 100  # valid PNG header
    book.add_item(cover)

    book.toc = [epub.Link("chap_01.xhtml", "Chapter 1", "ch1")]
    book.spine = ["nav", chapter]

    nav = epub.EpubNav()
    book.add_item(nav)

    tmp_dir.mkdir(parents=True, exist_ok=True)
    epub_path = tmp_dir / "test.epub"
    epub.write_epub(str(epub_path), book, {})
    return epub_path


def _make_noimage_epub(tmp_dir: Path) -> Path:
    """Create an EPUB with no images at all."""
    book = epub.EpubBook()
    book.set_identifier("test-002")
    book.set_title("Text Only")
    book.set_language("en")

    ch = epub.EpubHtml(title="Only", file_name="only.xhtml", lang="en")
    ch.content = "<html><body><p>Just text.</p></body></html>".encode("utf-8")
    book.add_item(ch)
    book.toc = [epub.Link("only.xhtml", "Only", "only")]
    book.spine = ["nav", ch]
    book.add_item(epub.EpubNav())

    tmp_dir.mkdir(parents=True, exist_ok=True)
    epub_path = tmp_dir / "noimage.epub"
    epub.write_epub(str(epub_path), book, {})
    return epub_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def minimal_epub(tmp_dir):
    return _make_minimal_epub(tmp_dir)


@pytest.fixture
def noimage_epub(tmp_dir):
    return _make_noimage_epub(tmp_dir)


# ---------------------------------------------------------------------------
# Unit tests — epub_converter internals
# ---------------------------------------------------------------------------

class TestComputeFileHash:
    def test_returns_hex_string(self, minimal_epub):
        h = _compute_file_hash(minimal_epub)
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self, tmp_dir):
        p1 = _make_minimal_epub(tmp_dir / "a")
        p2 = _make_minimal_epub(tmp_dir / "b")
        assert _compute_file_hash(p1) == _compute_file_hash(p2)


class TestExtractImages:
    def test_extracts_images(self, tmp_dir, minimal_epub):
        book = epub.read_epub(str(minimal_epub))
        adir = tmp_dir / "attachments" / "abcd1234"
        nm = _extract_images(book, adir)
        assert "images/cover.png" in nm
        assert "cover.png" in nm
        assert (adir / "cover.png").exists()

    def test_no_images(self, tmp_dir, noimage_epub):
        book = epub.read_epub(str(noimage_epub))
        adir = tmp_dir / "attachments" / "none"
        nm = _extract_images(book, adir)
        assert nm == {}


class TestConvertContent:
    def test_returns_markdown(self, minimal_epub):
        book = epub.read_epub(str(minimal_epub))
        md = _convert_content(book)
        assert "Chapter 1" in md
        assert "Hello world" in md

    def test_text_only(self, noimage_epub):
        book = epub.read_epub(str(noimage_epub))
        md = _convert_content(book)
        assert "Just text" in md


class TestRewriteImagePaths:
    def test_rewrites_from_name_map(self):
        md = "![Cover](../images/cover.png)"
        nm = {"images/cover.png": "cover.png", "cover.png": "cover.png"}
        result = _rewrite_image_paths(md, "attachments/abc123", nm)
        assert result == "![Cover](attachments/abc123/cover.png)"

    def test_preserves_non_image_content(self):
        md = "# Title\n\n[link](http://x.com)\n\n![x](images/a.png)"
        nm = {"images/a.png": "a.png", "a.png": "a.png"}
        result = _rewrite_image_paths(md, "attachments/h", nm)
        assert "# Title" in result
        assert "link](http://x.com)" in result
        assert "attachments/h/a.png" in result

    def test_no_images(self):
        md = "Just plain text."
        result = _rewrite_image_paths(md, "attachments/x", {})
        assert result == md

    def test_fallback_basename(self):
        """When name_map doesn't contain the ref, use the basename."""
        md = "![img](some/unknown/path/fig.jpg)"
        result = _rewrite_image_paths(md, "attachments/h", {})
        assert result == "![img](attachments/h/fig.jpg)"


class TestDeriveFilename:
    def test_from_metadata(self, minimal_epub):
        book = epub.read_epub(str(minimal_epub))
        name = _derive_filename(book, minimal_epub)
        assert name == "Test Book.md"

    def test_fallback_to_stem(self, tmp_dir):
        book = epub.EpubBook()
        path = tmp_dir / "my_document.epub"
        name = _derive_filename(book, path)
        assert name == "my_document.md"

    def test_sanitizes_invalid_chars(self, tmp_dir):
        path = tmp_dir / "bad:name?.epub"
        name = _derive_filename(epub.EpubBook(), path)
        assert ":" not in name
        assert "?" not in name


# ---------------------------------------------------------------------------
# Integration tests — convert_epub
# ---------------------------------------------------------------------------

class TestConvertEpub:
    def test_returns_expected_keys(self, tmp_dir, minimal_epub):
        result = convert_epub(minimal_epub, tmp_dir)
        assert "md_path" in result
        assert "attachments_path" in result
        assert "image_count" in result
        assert "hash_prefix" in result
        assert len(result["hash_prefix"]) == 8

    def test_writes_markdown_file(self, tmp_dir, minimal_epub):
        result = convert_epub(minimal_epub, tmp_dir)
        md_path = Path(result["md_path"])
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "Chapter 1" in content
        assert "Hello world" in content

    def test_writes_attachments(self, tmp_dir, minimal_epub):
        result = convert_epub(minimal_epub, tmp_dir)
        ap = Path(result["attachments_path"])
        assert ap.exists()
        images = list(ap.iterdir())
        assert len(images) >= 1
        assert result["image_count"] >= 1

    def test_image_path_rewritten(self, tmp_dir, minimal_epub):
        result = convert_epub(minimal_epub, tmp_dir)
        content = Path(result["md_path"]).read_text(encoding="utf-8")
        # Should reference attachments/, not images/ or ../images/
        assert "attachments/" in content
        assert "cover.png" in content
        assert "../images/" not in content

    def test_no_images(self, tmp_dir, noimage_epub):
        result = convert_epub(noimage_epub, tmp_dir)
        assert result["image_count"] == 0
        md = Path(result["md_path"]).read_text(encoding="utf-8")
        assert "Just text" in md


# ---------------------------------------------------------------------------
# Integration tests — converter.py integration
# ---------------------------------------------------------------------------

class TestConverterIntegration:
    def test_convert_single_epub(self, tmp_dir, minimal_epub):
        """convert_single should handle EPUB correctly and return success."""
        result = convert_single(minimal_epub, output_dir=tmp_dir)
        assert result["status"] == "success"
        assert result["details"] is not None
        assert result["details"]["images"] >= 1
        assert Path(result["details"]["md_path"]).exists()

    def test_skip_already_converted(self, tmp_dir, minimal_epub):
        """Second call without --force should skip."""
        r1 = convert_single(minimal_epub, output_dir=tmp_dir)
        assert r1["status"] == "success"
        r2 = convert_single(minimal_epub, output_dir=tmp_dir)
        assert r2["status"] == "skipped"

    def test_force_reconvert(self, tmp_dir, minimal_epub):
        """--force should re-convert even if already done."""
        convert_single(minimal_epub, output_dir=tmp_dir)
        r2 = convert_single(minimal_epub, output_dir=tmp_dir, force=True)
        assert r2["status"] == "success"

    def test_epub_without_images(self, tmp_dir, noimage_epub):
        result = convert_single(noimage_epub, output_dir=tmp_dir)
        assert result["status"] == "success"
        assert result["details"]["images"] == 0

    def test_manifest_record_created(self, tmp_dir, minimal_epub):
        from scripts.manifest_manager import load_manifest, get_manifest_path
        convert_single(minimal_epub, output_dir=tmp_dir)
        manifest = load_manifest(get_manifest_path(tmp_dir))
        assert len(manifest["files"]) >= 1
        for rec in manifest["files"].values():
            if rec["source_filename"].endswith(".epub"):
                assert rec["format"] == ".epub"
                assert rec["status"] == "success"
                break
        else:
            pytest.fail("No EPUB record found in manifest")
