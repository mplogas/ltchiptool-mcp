import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ltchiptool_mcp.runner import (
    run_ltchiptool,
    run_dissect,
    run_list_boards,
    LtchiptoolNotFoundError,
)


class TestRunLtchiptool:
    def test_invokes_ltchiptool_with_correct_argv(self, tmp_path):
        with patch("shutil.which", return_value="/usr/bin/ltchiptool"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            run_ltchiptool(["flash", "info", "bk7231n", "-d", "/dev/ttyUSB0"], timeout=25)

        argv = mock_run.call_args[0][0]
        assert argv[0] == "/usr/bin/ltchiptool"
        assert argv[1:] == ["flash", "info", "bk7231n", "-d", "/dev/ttyUSB0"]

    def test_returns_stdout_returncode_duration(self):
        with patch("shutil.which", return_value="/usr/bin/ltchiptool"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="hello", stderr="warn"
            )
            result = run_ltchiptool(["flash", "info"], timeout=25)

        assert result["stdout"] == "hello"
        assert result["stderr"] == "warn"
        assert result["returncode"] == 0
        assert result["duration_s"] >= 0

    def test_raises_when_ltchiptool_missing(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(LtchiptoolNotFoundError):
                run_ltchiptool(["flash", "info"], timeout=25)

    def test_timeout_recorded_as_error_dict(self):
        with patch("shutil.which", return_value="/usr/bin/ltchiptool"), \
             patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ltchiptool", timeout=25)
            result = run_ltchiptool(["flash", "info"], timeout=25)

        assert result["returncode"] == -1
        assert "timeout" in result["error"].lower()


class TestRunDissect:
    def test_invokes_python_module_form(self, tmp_path):
        cmd_template = ["python", "-m", "bk7231tools", "dissect_dump", "-e"]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            run_dissect(
                cmd_template,
                output_dir=str(tmp_path),
                dump_path="/some/dump.bin",
                timeout=90,
            )

        argv = mock_run.call_args[0][0]
        # 'python' is substituted with the running interpreter
        import sys
        assert argv[0] == sys.executable
        assert argv[1:] == [
            "-m", "bk7231tools", "dissect_dump", "-e",
            "-O", str(tmp_path) + "/",
            "/some/dump.bin",
        ]


class TestRunListBoards:
    def test_invokes_ltchiptool_list_boards(self):
        with patch("shutil.which", return_value="/usr/bin/ltchiptool"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="(table here)", stderr=""
            )
            result = run_list_boards(timeout=10)

        argv = mock_run.call_args[0][0]
        assert argv == ["/usr/bin/ltchiptool", "list", "boards"]
        assert result["stdout"] == "(table here)"
