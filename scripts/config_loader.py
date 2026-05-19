"""Configuration loader for mineru-converter-skill."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Project root is the parent of the scripts/ directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"
_DEFAULT_CONFIG: Dict[str, Any] = {
    "output_dir": "./raw",
    "mineru": {
        "command": "mineru",
        "args": {
            "backend": "pipeline",
            "model": "auto",
            "language": "ch",
            "method": "auto",
        },
    },
    "supported_extensions": [
        ".pdf", ".docx", ".pptx", ".xlsx",
        ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
        ".epub",
    ],
    "manifest": {
        "filename": "manifest.json",
        "version": "1.0",
    },
    "organizer": {
        "attachments_dir": "attachments",
        "hash_prefix_length": 8,
    },
}


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from YAML file, falling back to defaults."""
    path = config_path or _CONFIG_PATH
    if not path.exists():
        return _DEFAULT_CONFIG

    with open(path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    return _merge_defaults(_DEFAULT_CONFIG, user_config)


def _merge_defaults(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge overrides into defaults."""
    merged = {}
    for key, default_val in defaults.items():
        override_val = overrides.get(key)
        if isinstance(default_val, dict) and isinstance(override_val, dict):
            merged[key] = _merge_defaults(default_val, override_val)
        else:
            merged[key] = override_val if override_val is not None else default_val
    return merged


def get_output_dir(config: Optional[Dict[str, Any]] = None) -> Path:
    """Get expanded output directory path from config.
    
    Relative paths (e.g., "./raw") are resolved against the current working directory.
    Absolute paths or tilde paths are resolved normally.
    """
    cfg = config or load_config()
    raw_path = Path(cfg["output_dir"])
    if raw_path.is_absolute() or str(raw_path).startswith("~"):
        return raw_path.expanduser().resolve()
    # Relative path — resolve against CWD
    return (Path.cwd() / raw_path).resolve()


def get_supported_extensions(config: Optional[Dict[str, Any]] = None) -> set:
    """Get set of supported file extensions from config."""
    cfg = config or load_config()
    return set(cfg["supported_extensions"])


def get_manifest_path(output_dir: Path) -> Path:
    """Get manifest.json path within output_dir."""
    return output_dir / "manifest.json"
