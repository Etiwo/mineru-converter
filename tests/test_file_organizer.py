"""Tests for file_organizer module."""

import tempfile
from pathlib import Path
import pytest

from scripts.file_organizer import (
    move_mineru_output,
    rewrite_image_paths,
    cleanup_mineru_subdirs,
    _select_best_md,
    _copy_images,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_rewrite_image_paths_basic():
    """Test basic image path rewriting."""
    content = "![alt](images/test.png)\n![other](./images/pic.jpg)"
    result = rewrite_image_paths(content, "attachments", "abc12345")
    assert "attachments/abc12345/test.png" in result
    assert "attachments/abc12345/pic.jpg" in result
    assert "images/test.png" not in result
    assert "./images/pic.jpg" not in result


def test_rewrite_image_paths_no_images():
    """Test content without images is unchanged."""
    content = "Just text, no images here."
    result = rewrite_image_paths(content, "attachments", "abc12345")
    assert result == content


def test_rewrite_image_paths_preserves_text():
    """Test that non-image content is preserved."""
    content = "# Title\n\nParagraph with ![img](images/foo.png) inline.\n\n---\n\n[link](http://example.com)"
    result = rewrite_image_paths(content, "attachments", "hash123")
    assert "# Title" in result
    assert "Paragraph with" in result
    assert "link](http://example.com)" in result
    assert "attachments/hash123/foo.png" in result


def test_move_mineru_output_creates_md(tmp_dir):
    """Test that move_mineru_output extracts and creates the MD file."""
    # Setup MinerU-like output structure
    mineru_dir = tmp_dir / "mineru_output" / "my_document" / "auto"
    mineru_dir.mkdir(parents=True)
    (mineru_dir / "my_document.md").write_text(
        "# My Doc\n\n![photo](images/screenshot.png)", encoding="utf-8"
    )
    images_dir = mineru_dir / "images"
    images_dir.mkdir()
    (images_dir / "screenshot.png").write_bytes(b"fake_png_data")

    target = tmp_dir / "raw"

    result = move_mineru_output(mineru_dir, target)
    assert result["md_path"] is not None
    assert Path(result["md_path"]).exists()
    assert result["image_count"] == 1

    # Verify image path was rewritten
    md_content = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "attachments/" in md_content
    assert "screenshot.png" in md_content
    assert "images/screenshot.png" not in md_content


def test_move_mineru_output_creates_attachments(tmp_dir):
    """Test that images are copied to attachments directory."""
    mineru_dir = tmp_dir / "mineru_output" / "doc" / "auto"
    mineru_dir.mkdir(parents=True)
    (mineru_dir / "doc.md").write_text("content", encoding="utf-8")
    images_dir = mineru_dir / "images"
    images_dir.mkdir()
    (images_dir / "pic.jpg").write_bytes(b"fake_jpg")

    target = tmp_dir / "raw"
    result = move_mineru_output(mineru_dir, target)

    assert Path(result["attachments_path"]).exists()
    assert (Path(result["attachments_path"]) / "pic.jpg").exists()


def test_move_mineru_output_no_images(tmp_dir):
    """Test when MinerU output has no images directory."""
    mineru_dir = tmp_dir / "mineru_output" / "nodocs" / "auto"
    mineru_dir.mkdir(parents=True)
    (mineru_dir / "nodocs.md").write_text("# No Images", encoding="utf-8")

    target = tmp_dir / "raw"
    result = move_mineru_output(mineru_dir, target)
    assert result["image_count"] == 0
    assert Path(result["md_path"]).exists()


def test_cleanup_mineru_subdirs(tmp_dir):
    """Test cleanup of temporary subdirectories."""
    (tmp_dir / "keep_me").mkdir()
    (tmp_dir / "remove_me_1").mkdir()
    (tmp_dir / "remove_me_2").mkdir()

    count = cleanup_mineru_subdirs(tmp_dir, keep_subdirs=["keep_me"])
    assert count == 2
    assert (tmp_dir / "keep_me").exists()
    assert not (tmp_dir / "remove_me_1").exists()
    assert not (tmp_dir / "remove_me_2").exists()


def test_select_best_md_by_name():
    """Test MD selection prefers matching name."""
    files = [
        Path("/tmp/other.md"),
        Path("/tmp/my_paper.md"),
        Path("/tmp/extra.md"),
    ]
    selected = _select_best_md(files, "my_paper")
    assert selected.name == "my_paper.md"


def test_select_best_md_by_content(tmp_dir):
    """Test MD selection falls back to largest file."""
    f1 = tmp_dir / "small.md"
    f1.write_text("a", encoding="utf-8")
    f2 = tmp_dir / "large.md"
    f2.write_text("a" * 100, encoding="utf-8")
    files = [f1, f2]

    selected = _select_best_md(files, "unmatched_name")
    assert selected.name == "large.md"
