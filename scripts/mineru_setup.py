"""MinerU installation guidance and automatic setup."""

import subprocess
from pathlib import Path
from typing import Tuple
import yaml

from .config_loader import load_config

_SKILL_DIR = Path(__file__).resolve().parent.parent


def check_mineru_available() -> Tuple[bool, str]:
    """
    Check if MinerU is available by running mineru --version.

    Returns:
        (available: bool, version: str)
    """
    from .mineru_caller import check_mineru_available as _check
    return _check()


def install_mineru_auto(
    use_all: bool = True,
) -> bool:
    """
    Automatically install MinerU in a local venv under the skill directory.

    Creates ~/.config/opencode/skills/mineru-converter/.mineru_venv
    and installs mineru[all] or mineru[core] into it.
    Updates config.yaml to point to the venv's mineru binary.

    Args:
        use_all: If True, install mineru[all]; otherwise mineru[core].

    Returns:
        True if installation succeeded.
    """
    venv_dir = _SKILL_DIR / ".mineru_venv"
    pip_install = "mineru[all]" if use_all else "mineru[core]"

    print(f"\nCreating virtual environment at {venv_dir}...")
    result = subprocess.run(
        ["python3", "-m", "venv", str(venv_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Failed to create venv: {result.stderr}")
        return False

    pip_cmd = str(venv_dir / "bin" / "pip")
    print(f"Installing {pip_install}...")
    result = subprocess.run(
        [pip_cmd, "install", "-i", "https://mirrors.aliyun.com/pypi/simple", pip_install],
        capture_output=True, text=True,
        timeout=600,
    )
    if result.returncode != 0:
        print(f"Installation failed: {result.stderr}")
        return False

    mineru_bin = str(venv_dir / "bin" / "mineru")
    print(f"\nMinerU installed successfully at {mineru_bin}")

    # Update config.yaml
    _update_config_command(_SKILL_DIR / "config.yaml", mineru_bin)

    return True


def _update_config_command(config_path: Path, mineru_bin: str) -> None:
    """Update config.yaml with the new mineru command path."""
    cfg_path = Path(config_path).expanduser().resolve()
    if not cfg_path.exists():
        return

    with open(cfg_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    config.setdefault("mineru", {})["command"] = mineru_bin

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def show_manual_instructions() -> str:
    """Return installation instructions as text."""
    return (
        "\nMinerU is not installed. Install it manually:\n\n"
        "  1. Create a virtual environment:\n"
        "     python3 -m venv ~/Projects/mineru_env\n"
        "     source ~/Projects/mineru_env/bin/activate\n\n"
        "  2. Install MinerU (with all backends):\n"
        "     pip install -i https://mirrors.aliyun.com/pypi/simple 'mineru[all]'\n\n"
        "     Or core only (lighter):\n"
        "     pip install -i https://mirrors.aliyun.com/pypi/simple 'mineru[core]'\n\n"
        "  3. Verify:\n"
        "     mineru --version\n\n"
        "After installing, call the converter again.\n"
    )
