"""Validate converted output — checks MD existence, image paths, and manifest consistency."""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config_loader import get_output_dir, get_manifest_path
from .manifest_manager import load_manifest


class ValidationResult:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.files_checked: int = 0

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        parts = [f"Checked: {self.files_checked} files"]
        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")
        if self.warnings:
            parts.append(f"Warnings: {len(self.warnings)}")
        return " | ".join(parts)


def validate_conversion(
    output_dir: Optional[Path] = None,
) -> ValidationResult:
    """
    Validate all entries in manifest.json against actual files on disk.

    Checks:
      - Each manifest entry's output_md file exists
      - Each manifest entry's attachments directory exists (if specified)
      - Image paths in MD files reference valid files
    """
    output_dir = Path(output_dir or get_output_dir()).expanduser().resolve()
    result = ValidationResult()

    manifest = load_manifest(get_manifest_path(output_dir))
    files = manifest.get("files", {})

    if not files:
        result.warnings.append("No records in manifest to validate")
        return result

    for file_hash, record in files.items():
        result.files_checked += 1

        # Check MD file exists
        md_rel = record.get("output_md", "")
        if not md_rel:
            result.warnings.append(f"Record {file_hash}: no output_md path")
            continue

        md_path = output_dir / md_rel
        if not md_path.exists():
            result.errors.append(f"MD file missing: {md_path}")
            continue

        # Check attachments exist
        attachments_rel = record.get("output_attachments", "")
        if attachments_rel:
            attachments_path = output_dir / attachments_rel
            if not attachments_path.exists():
                result.warnings.append(f"Attachments missing: {attachments_path}")

        # Check image references in MD
        if md_path.exists():
            _check_image_refs(md_path, output_dir, result)

    return result


def _check_image_refs(md_path: Path, output_dir: Path, result: ValidationResult) -> None:
    """Check that all image references in a markdown file point to existing files."""
    content = md_path.read_text(encoding="utf-8")
    pattern = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
    refs = pattern.findall(content)

    for ref in refs:
        # Skip external URLs
        if ref.startswith("http://") or ref.startswith("https://"):
            continue

        img_path = output_dir / ref
        if not img_path.exists():
            result.warnings.append(f"Image not found: {img_path} (referenced from {md_path})")


if __name__ == "__main__":
    import sys
    output = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else None
    vr = validate_conversion(output_dir=output)
    print(vr.summary())
    for e in vr.errors:
        print(f"  ERROR: {e}", file=sys.stderr)
    for w in vr.warnings:
        print(f"  WARN:  {w}")
    sys.exit(0 if vr.is_valid else 1)
