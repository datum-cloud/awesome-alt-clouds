# tests/test_shell.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib.shell import run_command


class TestRunCommandNoShell:
    def test_command_substitution_in_argument_is_not_executed(self, tmp_path):
        marker = tmp_path / "pwned"
        value = f"https://example.com/$(touch ${{IFS}}{marker})"
        assert run_command(["printf", "%s", value]) == value
        assert not marker.exists()

    def test_separator_and_pipe_stay_in_one_argument(self, tmp_path):
        marker = tmp_path / "pwned"
        value = f"a; touch {marker}; b | c"
        assert run_command(["printf", "%s", value]) == value
        assert not marker.exists()

    def test_returns_stripped_stdout(self):
        assert run_command(["printf", "  hello  "]) == "hello"

    def test_raw_stdout_when_strip_is_false(self):
        assert run_command(["printf", "  hi  "], strip=False) == "  hi  "
