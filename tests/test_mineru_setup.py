"""Tests for mineru_setup module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.mineru_setup import (
    install_mineru_auto,
    show_manual_instructions,
)


class TestInstallMineruAuto:
    """Test automatic MinerU installation."""

    def test_install_creates_venv(self):
        """install_mineru_auto should create a venv directory."""
        with patch("scripts.mineru_setup.subprocess.run") as mock_run:
            # venv creation succeeds
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            with patch("scripts.mineru_setup._SKILL_DIR", Path("/tmp/test_skill")):
                with patch("scripts.mineru_setup._update_config_command"):
                    result = install_mineru_auto(use_all=True)

            assert result is True
            calls = [c[0][0] for c in mock_run.call_args_list]
            assert any("venv" in str(c) for c in calls)

    def test_install_creates_correct_pip_command(self):
        """install_mineru_auto[all] should install mineru[all], not mineru[core]."""
        with patch("scripts.mineru_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            with patch("scripts.mineru_setup._SKILL_DIR", Path("/tmp/test_skill")):
                with patch("scripts.mineru_setup._update_config_command"):
                    install_mineru_auto(use_all=True)

            calls = [c[0][0] for c in mock_run.call_args_list]
            pip_call = calls[1]  # second call is pip install
            assert "mineru[all]" in " ".join(pip_call)

    def test_install_core_when_requested(self):
        """install_mineru_auto[core] should install mineru[core]."""
        with patch("scripts.mineru_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            with patch("scripts.mineru_setup._SKILL_DIR", Path("/tmp/test_skill")):
                with patch("scripts.mineru_setup._update_config_command"):
                    install_mineru_auto(use_all=False)

            calls = [c[0][0] for c in mock_run.call_args_list]
            pip_call = calls[1]
            assert "mineru[core]" in " ".join(pip_call)

    def test_install_fails_on_venv_error(self):
        """If venv creation fails, returns False."""
        with patch("scripts.mineru_setup.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout="", stderr="venv error"),
            ]

            with patch("scripts.mineru_setup._SKILL_DIR", Path("/tmp/test_skill")):
                with patch("scripts.mineru_setup._update_config_command"):
                    result = install_mineru_auto()

            assert result is False


class TestUpdateConfigCommand:
    """Test _update_config_command."""

    def test_updates_config_yaml(self, tmp_path):
        """_update_config_command should update config.yaml with new mineru path."""
        import yaml
        cfg = tmp_path / "config.yaml"
        existing_config = {
            "output_dir": "./raw",
            "mineru": {"command": "mineru", "args": {"backend": "pipeline"}},
        }
        with open(cfg, "w") as f:
            yaml.dump(existing_config, f)

        from scripts.mineru_setup import _update_config_command
        _update_config_command(cfg, "/some/path/.mineru_venv/bin/mineru")

        with open(cfg, "r") as f:
            updated = yaml.safe_load(f)

        assert updated["mineru"]["command"] == "/some/path/.mineru_venv/bin/mineru"
        # Other keys should be preserved
        assert updated["output_dir"] == "./raw"


class TestShowManualInstructions:
    """Test show_manual_instructions."""

    def test_returns_text(self):
        """show_manual_instructions should return a non-empty string."""
        result = show_manual_instructions()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_install_commands(self):
        """Output should contain key installation commands."""
        result = show_manual_instructions()
        assert "venv" in result
        assert "pip install" in result
        assert "mineru" in result
        assert "mineru --version" in result
