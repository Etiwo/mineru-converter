"""MinerU CLI wrapper — invokes mineru command and returns output metadata."""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .config_loader import load_config, get_output_dir, get_manifest_path


class MineruError(Exception):
    """Base exception for MinerU operations."""


class MineruNotFoundError(MineruError):
    """MinerU CLI not found."""


class MineruExecutionError(MineruError):
    """MinerU command failed."""


# Format-specific extra arguments
_FORMAT_EXTRA_ARGS: Dict[str, List[str]] = {
    ".xlsx": ["--table"],
}

# Timeout in seconds
_TIMEOUT = 300


def run_mineru(
    input_path: Path,
    output_dir: Path,
    verbose: bool = False,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    method: Optional[str] = None,
    lang: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Invoke MinerU to convert a single file.

    Args:
        input_path: Path to the source file.
        output_dir: Directory where MinerU writes results.
        verbose: If True, print MinerU stderr output.
        start_page: 0-indexed start page (PDF only).
        end_page: 0-indexed end page (PDF only).
        method: PDF parsing method — 'auto', 'txt', or 'ocr'.
        lang: Document language code (e.g. 'ch', 'en', 'ja').

    Returns:
        List of dicts with keys:
          - subdir: relative path of the output subdirectory
          - md_files: list of .md file paths found
          - images_dir: path to the images directory (or None)

    Raises:
        MineruNotFoundError: If mineru command is not available.
        MineruExecutionError: If MinerU fails.
    """
    input_path = Path(input_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    mineru_config = config.get("mineru", {})
    mineru_cmd = mineru_config.get("command", "mineru")
    default_args = mineru_config.get("args", {})

    cmd = [
        mineru_cmd,
        "-p", str(input_path),
        "-o", str(output_dir),
        "-b", default_args.get("backend", "pipeline"),
    ]

    # -m method: CLI arg overrides config
    if method is not None:
        cmd.extend(["-m", method])
    elif default_args.get("method", "auto") != "auto":
        cmd.extend(["-m", default_args["method"]])

    # -l language: CLI arg overrides config
    if lang is not None:
        cmd.extend(["-l", lang])
    elif default_args.get("language", "ch") != "ch":
        cmd.extend(["-l", default_args["language"]])

    # -s/-e page range (only for PDF)
    if start_page is not None:
        cmd.extend(["-s", str(start_page)])
    if end_page is not None:
        cmd.extend(["-e", str(end_page)])

    # Add format-specific arguments
    ext = input_path.suffix.lower()
    cmd.extend(_FORMAT_EXTRA_ARGS.get(ext, []))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        raise MineruNotFoundError(
            f"mineru command not found: {mineru_cmd}. "
            "Please ensure MinerU is installed and available in PATH."
        )
    except subprocess.TimeoutExpired:
        raise MineruExecutionError(f"MinerU timed out after {_TIMEOUT}s for {input_path}")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if verbose:
            print(f"[mineru stderr] {stderr}")
        raise MineruExecutionError(
            f"MinerU failed (exit code {e.returncode}) for {input_path}: {stderr}"
        )

    if verbose and result.stdout:
        print(f"[mineru output] {result.stdout.strip()}")

    return _scan_mineru_output(output_dir, input_path)


def check_mineru_available() -> Tuple[bool, Optional[str]]:
    """
    Check if the MinerU command is available and responds to --version.

    Reads the command from config.yaml, falls back to "mineru".

    Returns:
        Tuple of (available: bool, version_string: str or None).
    """
    config = load_config()
    mineru_cmd = config.get("mineru", {}).get("command", "mineru")

    try:
        result = subprocess.run(
            [mineru_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[-1].strip()
            return True, version
        return False, None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, None


def _scan_mineru_output(output_dir: Path, input_path: Path) -> List[Dict[str, str]]:
    """
    Scan the output directory for MinerU-generated subdirectories.

    Finds all subdirectories, locates .md files and images, returns metadata.
    """
    output_dir = Path(output_dir).resolve()
    results = []

    for item in sorted(output_dir.iterdir()):
        if not item.is_dir():
            continue

        md_files = []
        for md_file in item.rglob("*.md"):
            if md_file.is_file():
                md_files.append(str(md_file))

        images_dir = None
        images_path = item / "images"
        if images_path.is_dir():
            images_dir = str(images_path)

        results.append({
            "subdir": str(item),
            "md_files": md_files,
            "images_dir": images_dir,
        })

    if not results:
        raise MineruExecutionError(
            f"No output subdirectories found in {output_dir}. "
            "MinerU may have failed or written to an unexpected location."
        )

    return results
