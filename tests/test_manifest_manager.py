"""Tests for manifest_manager module."""

import json
import hashlib
import tempfile
from pathlib import Path
import pytest

from scripts.manifest_manager import (
    compute_sha256,
    load_manifest,
    save_manifest,
    upsert_record,
    build_record,
    check_converted,
    add_conversion_record,
    ManifestLoadError,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_file(tmp_dir):
    f = tmp_dir / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    return f


def test_compute_sha256(sample_file):
    h = compute_sha256(sample_file)
    assert isinstance(h, str)
    assert len(h) == 64
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert h == expected


def test_compute_sha256_different_content(tmp_dir):
    f1 = tmp_dir / "a.txt"
    f1.write_text("aaa", encoding="utf-8")
    f2 = tmp_dir / "b.txt"
    f2.write_text("bbb", encoding="utf-8")
    assert compute_sha256(f1) != compute_sha256(f2)


def test_load_manifest_empty(tmp_dir):
    manifest_path = tmp_dir / "manifest.json"
    m = load_manifest(manifest_path)
    assert "version" in m
    assert m["files"] == {}


def test_load_manifest_from_existing(tmp_dir):
    manifest_path = tmp_dir / "manifest.json"
    data = {"version": "2.0", "files": {"abc123": {"status": "success"}}}
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    m = load_manifest(manifest_path)
    assert m["version"] == "2.0"
    assert "abc123" in m["files"]


def test_load_manifest_corrupted(tmp_dir):
    manifest_path = tmp_dir / "manifest.json"
    manifest_path.write_text("not valid json {{{", encoding="utf-8")
    with pytest.raises(ManifestLoadError):
        load_manifest(manifest_path)


def test_save_and_load_manifest(tmp_dir):
    manifest_path = tmp_dir / "manifest.json"
    m = {"version": "1.0", "files": {}}
    save_manifest(m, manifest_path)
    loaded = load_manifest(manifest_path)
    assert loaded["version"] == "1.0"


def test_upsert_record():
    m = {"files": {}}
    m = upsert_record(m, "hash1", {"status": "success"})
    assert "hash1" in m["files"]
    assert m["files"]["hash1"]["status"] == "success"


def test_build_record():
    r = build_record(
        source_path=Path("/tmp/doc.pdf"),
        output_md="doc.md",
        output_attachments="attachments/abc123",
        file_format="pdf",
    )
    assert r["format"] == "pdf"
    assert r["status"] == "success"
    assert r["output_md"] == "doc.md"
    assert "converted_at" in r


def test_check_converted_new_file(tmp_dir):
    f = tmp_dir / "new.pdf"
    f.write_text("pdf content", encoding="utf-8")
    manifest = {"version": "1.0", "files": {}}
    is_conv, h = check_converted(f, manifest)
    assert is_conv is False
    assert isinstance(h, str)


def test_check_converted_existing(tmp_dir):
    f = tmp_dir / "existing.pdf"
    f.write_text("same content", encoding="utf-8")
    h = compute_sha256(f)
    manifest = {
        "version": "1.0",
        "files": {h: {"source_path": str(f.resolve()), "status": "success"}},
    }
    is_conv, h2 = check_converted(f, manifest)
    assert is_conv is True


def test_check_converted_modified(tmp_dir):
    f = tmp_dir / "changed.pdf"
    f.write_text("original content", encoding="utf-8")
    h_original = compute_sha256(f)

    # Create manifest with old hash
    manifest = {
        "version": "1.0",
        "files": {h_original: {"source_path": str(f.resolve()), "status": "success"}},
    }

    # Modify file
    f.write_text("modified content", encoding="utf-8")
    new_h = compute_sha256(f)

    is_conv, h_new = check_converted(f, manifest)
    assert is_conv is False
    assert h_new == new_h


def test_add_conversion_record(tmp_dir):
    f = tmp_dir / "doc.pdf"
    f.write_text("some pdf", encoding="utf-8")
    manifest = {"version": "1.0", "files": {}}
    manifest = add_conversion_record(
        manifest, f, "doc.md", "attachments/abc", "pdf", status="success"
    )
    assert len(manifest["files"]) == 1
    file_hash = compute_sha256(f)
    assert file_hash in manifest["files"]
    assert manifest["files"][file_hash]["status"] == "success"
