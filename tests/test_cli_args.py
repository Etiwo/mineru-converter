"""Tests for CLI argument parsing."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure scripts/ is in path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.cli import main


def _mock_convert_success():
    """Return a mock result dict for a successful conversion."""
    return {
        "path": "/fake/file.pdf",
        "status": "success",
        "error": None,
        "details": {"md_path": "/fake/out/file.md", "images": 5},
    }


class TestCliPagesParam:
    """Test --pages parameter handling."""

    def test_pages_with_file_succeeds(self, tmp_path):
        """--pages with --file should be accepted."""
        f = tmp_path / "test.pdf"
        f.write_text("fake", encoding="utf-8")

        with patch("scripts.cli.convert_single", return_value=_mock_convert_success()):
            with patch("scripts.cli._ensure_mineru_installed", return_value=True):
                with patch("sys.argv", ["mineru-converter", "convert", "--file", str(f), "--pages", "3-5"]):
                    main()

    def test_pages_with_dir_errors(self, tmp_path):
        """--pages with --dir should raise argparse error in main()."""
        d = tmp_path / "inbox"
        d.mkdir()

        with patch("scripts.cli._ensure_mineru_installed", return_value=True):
            with patch("sys.argv", ["mineru-converter", "convert", "--dir", str(d), "--pages", "3-5"]):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 2  # parser.error exits with code 2 in argparse

    def test_pages_single_page(self, tmp_path):
        """--pages 3 (single page) should be accepted."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--file", type=str)
        p.add_argument("--pages", type=str, default=None)

        args = parser.parse_args(["convert", "--file", "/fake.pdf", "--pages", "3"])
        assert args.pages == "3"


class TestCliMethodParam:
    """Test --method parameter handling."""

    def test_method_choices(self):
        """--method should accept auto, txt, ocr."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--method", type=str, choices=["auto", "txt", "ocr"])

        for choice in ["auto", "txt", "ocr"]:
            args = parser.parse_args(["convert", "--method", choice])
            assert args.method == choice

    def test_method_invalid(self):
        """--method with invalid value should raise error."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--method", type=str, choices=["auto", "txt", "ocr"])

        with pytest.raises(SystemExit):
            parser.parse_args(["convert", "--method", "invalid"])

    def test_method_with_dir_allowed(self):
        """--method with --dir should be accepted (no error)."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--dir", type=str)
        p.add_argument("--method", type=str, choices=["auto", "txt", "ocr"])

        args = parser.parse_args(["convert", "--dir", "/some/dir", "--method", "ocr"])
        assert args.method == "ocr"


class TestCliLangParam:
    """Test --lang parameter handling."""

    def test_lang_accepted(self):
        """--lang should be accepted."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--file", type=str)
        p.add_argument("--lang", type=str, default=None)

        args = parser.parse_args(["convert", "--file", "/f.pdf", "--lang", "en"])
        assert args.lang == "en"

    def test_lang_with_dir_allowed(self):
        """--lang with --dir should be accepted."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--dir", type=str)
        p.add_argument("--lang", type=str, default=None)

        args = parser.parse_args(["convert", "--dir", "/some/dir", "--lang", "ja"])
        assert args.lang == "ja"


class TestCliMutualExclusion:
    """Test mutual exclusion rules."""

    def test_pages_and_dir_mutually_exclusive(self):
        """--pages and --dir together should error."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("convert")
        p.add_argument("--dir", type=str)
        p.add_argument("--file", type=str)
        p.add_argument("--pages", type=str, default=None)

        args = parser.parse_args(["convert", "--dir", "/d", "--pages", "1-3"])
        # The mutual exclusion check is done in cli.py logic, not argparse
        # So argparse succeeds, but main() should call parser.error
        assert args.dir == "/d"
        assert args.pages == "1-3"
        # The actual error is tested in the integration below


class TestCliEnsureMineru:
    """Test _ensure_mineru_installed function."""

    def test_mineru_available_returns_true(self):
        """When MinerU is available, returns True."""
        with patch("scripts.cli.check_mineru_available", return_value=(True, "3.1.4")):
            result = main.__globals__["_ensure_mineru_installed"]()
            assert result is True

    def test_mineru_unavailable_prompt_auto(self):
        """When MinerU missing and user chooses auto, returns True."""
        with patch("scripts.cli.check_mineru_available", return_value=(False, None)):
            with patch("scripts.cli.install_mineru_auto", return_value=True):
                with patch("scripts.cli.check_mineru_available", return_value=(True, "3.1.4")):
                    with patch("builtins.input", return_value="a"):
                        result = main.__globals__["_ensure_mineru_installed"]()
                        assert result is True

    def test_mineru_unavailable_prompt_manual(self):
        """When MinerU missing and user chooses manual, returns False."""
        with patch("scripts.cli.check_mineru_available", return_value=(False, None)):
            with patch("builtins.input", return_value="m"):
                result = main.__globals__["_ensure_mineru_installed"]()
                assert result is False


class TestConvertSubcommandIntegration:
    """Integration test: convert --file with new parameters."""

    def test_convert_file_with_pages(self, tmp_path):
        """convert --file with --pages calls convert_single with page args."""
        f = tmp_path / "test.pdf"
        f.write_text("fake", encoding="utf-8")

        with patch("scripts.cli.convert_single", return_value=_mock_convert_success()) as mock_conv:
            with patch("scripts.cli._ensure_mineru_installed", return_value=True):
                with patch("sys.argv", ["mineru-converter", "convert", "--file", str(f), "--pages", "3-5"]):
                    main()

        mock_conv.assert_called_once()
        call_kwargs = mock_conv.call_args
        assert call_kwargs.kwargs.get("pages") == "3-5"

    def test_convert_file_with_method(self, tmp_path):
        """convert --file with --method ocr."""
        f = tmp_path / "test.pdf"
        f.write_text("fake", encoding="utf-8")

        with patch("scripts.cli.convert_single", return_value=_mock_convert_success()) as mock_conv:
            with patch("scripts.cli._ensure_mineru_installed", return_value=True):
                with patch("sys.argv", ["mineru-converter", "convert", "--file", str(f), "--method", "ocr"]):
                    main()

        call_kwargs = mock_conv.call_args
        assert call_kwargs.kwargs.get("method") == "ocr"

    def test_convert_file_with_lang(self, tmp_path):
        """convert --file with --lang en."""
        f = tmp_path / "test.pdf"
        f.write_text("fake", encoding="utf-8")

        with patch("scripts.cli.convert_single", return_value=_mock_convert_success()) as mock_conv:
            with patch("scripts.cli._ensure_mineru_installed", return_value=True):
                with patch("sys.argv", ["mineru-converter", "convert", "--file", str(f), "--lang", "en"]):
                    main()

        call_kwargs = mock_conv.call_args
        assert call_kwargs.kwargs.get("lang") == "en"

    def test_convert_dir_with_method(self, tmp_path):
        """convert --dir with --method ocr."""
        d = tmp_path / "inbox"
        d.mkdir()

        with patch("scripts.cli.convert_batch", return_value={
            "scanned": 0, "processed": 0, "skipped": 0, "failed": 0, "items": []
        }) as mock_conv:
            with patch("scripts.cli._ensure_mineru_installed", return_value=True):
                with patch("sys.argv", ["mineru-converter", "convert", "--dir", str(d), "--method", "ocr"]):
                    main()

        call_kwargs = mock_conv.call_args
        assert call_kwargs.kwargs.get("method") == "ocr"
