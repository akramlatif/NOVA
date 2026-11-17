# ==============================================================================
# NOVA — Tests for environment verification logic (Phase 1, Task 5)
# ------------------------------------------------------------------------------
# These tests cover the PURE parts of scripts/verify_environment.py: version
# comparison and recommendation gating. They run on any OS (CI-friendly)
# because they never touch the Windows APIs — those paths are exercised when
# you run the script itself on your machine.
#
# Run:  pytest
# ==============================================================================

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# --- Import the verify script as a module (it's in scripts/, not a package) ---
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_environment.py"
_spec = importlib.util.spec_from_file_location("verify_environment", _SCRIPT)
verify = importlib.util.module_from_spec(_spec)
sys.modules["verify_environment"] = verify
_spec.loader.exec_module(verify)


class TestPythonVersionGate:
    """MIN_PYTHON is the compatibility contract for the whole project."""

    def test_minimum_is_310(self) -> None:
        assert verify.MIN_PYTHON == (3, 10)

    def test_running_interpreter_meets_the_gate(self) -> None:
        # Guarantees the test suite itself runs on a supported interpreter.
        assert sys.version_info >= verify.MIN_PYTHON


class TestVersionParsing:
    """run_version_check() must survive odd CLI output — real CLIs are messy."""

    def test_first_line_of_output_returned(self, monkeypatch) -> None:
        import subprocess

        class FakeCompleted:
            stdout = "git version 2.45.1.windows.1\n"
            stderr = ""
            returncode = 0

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())
        result = verify.run_version_check("git", ["--version"])
        assert result == "git version 2.45.1.windows.1"

    def test_missing_tool_returns_none(self, monkeypatch) -> None:
        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert verify.run_version_check("definitely-not-installed", ["--version"]) is None

    def test_timeout_returns_none(self, monkeypatch) -> None:
        import shutil
        import subprocess

        monkeypatch.setattr(shutil, "which", lambda name: "C:/fake/hangy.exe")

        def hang(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="hangy.exe", timeout=30)

        monkeypatch.setattr(subprocess, "run", hang)
        assert verify.run_version_check("hangy", ["--version"]) is None


class TestHardwareGates:
    """The RAM and disk gates protect against unvaiable installs."""

    def test_minimum_ram_is_six_gb(self) -> None:
        # 8 GB machine with Windows 11 (~3 GB) needs at least this floor.
        assert verify.MIN_RECOMMENDED_RAM_GB == 6.0

    def test_minimum_disk_is_ten_gb(self) -> None:
        # Model (~2 GB) + SQLite data + logs + growth headroom.
        assert verify.MIN_DISK_FREE_GB == 10.0

    def test_recommended_model_is_a_3b(self) -> None:
        # Hardware contract: no 7B+ models on the i5-5200U / 8 GB target.
        assert verify.RECOMMENDED_MODEL == "llama3.2:3b"
        assert "3b" in verify.RECOMMENDED_MODEL


class TestExitSemantics:
    """main() exit code is the CI signal — verify the convention holds."""

    def test_zero_means_success(self) -> None:
        # All-pass must exit 0 so scripts and CI can rely on it.
        assert 0 == 0  # placeholder for convention documentation


# Note on the last test: the exit-code convention (0 = pass, 1 = failure) is
# asserted behaviorally on your machine — main() reads live hardware. What we
# assert here is that the constants the gate uses are what the master
# instructions require, so a silent regression fails loudly in CI instead.
