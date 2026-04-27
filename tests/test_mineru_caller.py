"""Tests for mineru_caller module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.mineru_caller import run_mineru, MineruError, MineruNotFoundError, _FORMAT_EXTRA_ARGS, check_mineru_available


def test_format_extra_args():
    """Verify format-specific extra args are configured."""
    assert ".xlsx" in _FORMAT_EXTRA_ARGS
    assert "--table" in _FORMAT_EXTRA_ARGS[".xlsx"]
    assert ".pdf" not in _FORMAT_EXTRA_ARGS


def test_mineru_not_found():
    """Test MineruNotFoundError when command doesn't exist."""
    with patch("scripts.mineru_caller.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(MineruNotFoundError):
            run_mineru(Path("/tmp/test.pdf"), Path("/tmp/out"))


def test_mineru_execution_error():
    """Test MineruExecutionError when command fails."""
    import subprocess as sp
    with patch("scripts.mineru_caller.subprocess.run") as mock_run:
        mock_run.side_effect = sp.CalledProcessError(1, "mineru", stderr="bad input")
        with pytest.raises(MineruError):
            run_mineru(Path("/tmp/test.pdf"), Path("/tmp/out"))


def test_run_mineru_success(tmp_path):
    """Test successful mineru invocation (mocked)."""
    output_dir = tmp_path / "output"

    with patch("scripts.mineru_caller.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        sub_dir = output_dir / "test_document" / "auto"
        sub_dir.mkdir(parents=True)
        (sub_dir / "test_document.md").write_text("# Title\n\nContent", encoding="utf-8")
        (sub_dir / "images").mkdir()
        (sub_dir / "images/img1.jpg").write_text("fake image", encoding="utf-8")

        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf", encoding="utf-8")

        result = run_mineru(input_file, output_dir)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "md_files" in result[0]
        assert "images_dir" in result[0]


def test_run_mineru_no_output():
    """Test error when mineru produces no output."""
    with patch("scripts.mineru_caller.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with pytest.raises(MineruError, match="No output"):
            run_mineru(Path("/tmp/test.pdf"), Path("/tmp/nonexistent_output"))


class TestRunMineruPageRange:
    """Test --pages parameter handling in run_mineru."""

    def test_pages_3_to_5(self, tmp_path):
        """--pages 3-5 should translate to -s 2 -e 4 (0-indexed)."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, start_page=2, end_page=4)

            cmd = mock_run.call_args[0][0]
            assert "-s" in cmd and "2" in cmd
            assert "-e" in cmd and "4" in cmd

    def test_pages_single(self, tmp_path):
        """Single page 3 should translate to -s 2 -e 2 (0-indexed)."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, start_page=2, end_page=2)

            cmd = mock_run.call_args[0][0]
            assert "-s" in cmd and "2" in cmd
            assert "-e" in cmd and "2" in cmd

    def test_no_pages(self, tmp_path):
        """No page range should not include -s or -e in command."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, start_page=None, end_page=None)

            cmd = mock_run.call_args[0][0]
            assert "-s" not in cmd
            assert "-e" not in cmd


class TestRunMineruMethod:
    """Test --method parameter handling."""

    def test_method_ocr(self, tmp_path):
        """--method ocr should add -m ocr to command."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, method="ocr")

            cmd = mock_run.call_args[0][0]
            idx = cmd.index("-m")
            assert cmd[idx + 1] == "ocr"

    def test_method_txt(self, tmp_path):
        """--method txt should add -m txt to command."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, method="txt")

            cmd = mock_run.call_args[0][0]
            idx = cmd.index("-m")
            assert cmd[idx + 1] == "txt"

    def test_method_none_uses_config_default(self, tmp_path):
        """When method=None, config value is used (auto is default, no -m flag needed)."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, method=None)

            cmd = mock_run.call_args[0][0]
            assert "-m" not in cmd

    def test_method_override_config(self, tmp_path):
        """When method=None but config says 'txt', -m txt should be added."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.load_config") as mock_config:
            mock_config.return_value = {
                "mineru": {"command": "mineru", "args": {"backend": "pipeline", "method": "txt", "language": "ch"}},
            }
            with patch("scripts.mineru_caller.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                sub_dir = output_dir / "test" / "auto"
                sub_dir.mkdir(parents=True)
                (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

                run_mineru(input_file, output_dir, method=None)

                cmd = mock_run.call_args[0][0]
                assert "-m" in cmd
                idx = cmd.index("-m")
                assert cmd[idx + 1] == "txt"


class TestRunMineruLang:
    """Test --lang parameter handling."""

    def test_lang_en(self, tmp_path):
        """--lang en should add -l en to command."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, lang="en")

            cmd = mock_run.call_args[0][0]
            idx = cmd.index("-l")
            assert cmd[idx + 1] == "en"

    def test_lang_ja(self, tmp_path):
        """--lang ja should add -l ja to command."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, lang="ja")

            cmd = mock_run.call_args[0][0]
            idx = cmd.index("-l")
            assert cmd[idx + 1] == "ja"

    def test_lang_ch_default(self, tmp_path):
        """Default language ch matches hardcoded default, so no -l flag added."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sub_dir = output_dir / "test" / "auto"
            sub_dir.mkdir(parents=True)
            (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

            run_mineru(input_file, output_dir, lang=None)

            cmd = mock_run.call_args[0][0]
            assert "-l" not in cmd

    def test_lang_override_config(self, tmp_path):
        """When lang=None but config says 'en', -l en should be added."""
        output_dir = tmp_path / "out"
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake", encoding="utf-8")

        with patch("scripts.mineru_caller.load_config") as mock_config:
            mock_config.return_value = {
                "mineru": {"command": "mineru", "args": {"backend": "pipeline", "method": "auto", "language": "en"}},
            }
            with patch("scripts.mineru_caller.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                sub_dir = output_dir / "test" / "auto"
                sub_dir.mkdir(parents=True)
                (sub_dir / "test.md").write_text("# Title", encoding="utf-8")

                run_mineru(input_file, output_dir, lang=None)

                cmd = mock_run.call_args[0][0]
                assert "-l" in cmd
                idx = cmd.index("-l")
                assert cmd[idx + 1] == "en"


class TestCheckMineruAvailable:
    """Test check_mineru_available function."""

    def test_available(self):
        """When mineru --version succeeds, returns (True, version)."""
        with patch("scripts.mineru_caller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="mineru, version 3.1.4")
            available, version = check_mineru_available()
            assert available is True
            assert "3.1.4" in version

    def test_not_found(self):
        """When mineru command is missing, returns (False, None)."""
        with patch("scripts.mineru_caller.subprocess.run", side_effect=FileNotFoundError()):
            available, version = check_mineru_available()
            assert available is False
            assert version is None

    def test_timeout(self):
        """When mineru --version times out, returns (False, None)."""
        import subprocess
        with patch("scripts.mineru_caller.subprocess.run", side_effect=subprocess.TimeoutExpired("mineru", 30)):
            available, version = check_mineru_available()
            assert available is False
            assert version is None

    def test_uses_config_command(self):
        """check_mineru_available uses mineru.command from config."""
        with patch("scripts.mineru_caller.load_config") as mock_config:
            mock_config.return_value = {
                "mineru": {"command": "/custom/path/mineru"},
            }
            with patch("scripts.mineru_caller.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="mineru, version 3.1.4")
                available, version = check_mineru_available()
                assert available is True
                cmd = mock_run.call_args[0][0]
                assert cmd[0] == "/custom/path/mineru"
