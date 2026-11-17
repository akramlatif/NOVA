# ==============================================================================
# NOVA — Environment Verification Script (Phase 1, Task 1 & 5)
# ------------------------------------------------------------------------------
# Purpose:
#   Inspects the development machine BEFORE anything is installed or changed.
#   Reports: Python, pip, git, node/npm, Ollama, RAM, storage, Windows version.
#
# Why this exists:
#   Master rules — "Inspect the development environment before installing
#   anything" and "Do not reinstall existing software unnecessarily."
#   This script is the inspection step, run before and after setup.
#
# Usage (PowerShell, from D:\NOVA):
#   python scripts\verify_environment.py
#
# Exit codes:  0 = all checks pass,  1 = one or more checks failed
# ==============================================================================

from __future__ import annotations

import ctypes
import platform
import re
import shutil
import subprocess
import sys

# ------------------------------------------------------------------ constants
MIN_PYTHON = (3, 10)        # NOVA uses modern typing syntax
MIN_DISK_FREE_GB = 10.0     # room for models + data + logs on D:
MIN_RECOMMENDED_RAM_GB = 6.0  # below this, local AI is not viable
RECOMMENDED_MODEL = "llama3.2:3b"  # sized for 8 GB RAM, no GPU


# ------------------------------------------------------------------ helpers
def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def run_version_check(name: str, args: list[str]) -> str | None:
    """Run a CLI tool and return its first line of output, or None if absent."""
    exe = shutil.which(name)
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else None


# ------------------------------------------------------------------ checks
def check_python() -> bool:
    print("Python:")
    version = sys.version_info
    ver_str = f"{version.major}.{version.minor}.{version.micro}"
    if version >= MIN_PYTHON:
        _ok(f"Python {ver_str} (need >= 3.10) at: {sys.executable}")
        return True
    _fail(f"Python {ver_str} found — 3.10+ required. Install from python.org "
          f"and tick 'Add python.exe to PATH' during setup.")
    return False


def check_pip() -> bool:
    print("pip:")
    result = run_version_check("pip", ["--version"])
    if result:
        _ok(result)
        return True
    # pip may exist as a module even if not on PATH
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            _ok(f"pip available as module: {out.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, OSError):
        pass
    _fail("pip not found. Fix with: python -m ensurepip --upgrade")
    return False


def check_git() -> bool:
    print("Git:")
    result = run_version_check("git", ["--version"])
    if result:
        m = re.search(r"(\d+)\.(\d+)", result)
        if m and (int(m.group(1)), int(m.group(2))) >= (2, 30):
            _ok(result)
            return True
        _warn(f"{result} — quite old; upgrade from git-scm.com if clone/push misbehave.")
        return True
    _fail("Git not found. Install from git-scm.com (Git Bash + Git CMD both fine).")
    return False


def check_node() -> bool:
    print("Node.js / npm (needed only in Phase 7-8):")
    node = run_version_check("node", ["--version"])
    npm = run_version_check("npm", ["--version"])
    if node:
        _ok(f"node {node}")
        _ok(f"npm  {npm}") if npm else _warn("npm missing — comes with node; reinstall Node.")
        return True
    _warn("Node.js not installed. Fine for now — needed only in Phase 7 (frontend tooling).")
    return True  # not a blocker for Phase 1


def check_windows() -> bool:
    print("Windows:")
    release = platform.release()          # e.g. "11"
    build = platform.version()            # e.g. "10.0.26100"
    ver = sys.getwindowsversion() if hasattr(sys, "getwindowsversion") else None
    if release == "11" or (ver and ver.build >= 22000):
        _ok(f"Windows {release} (build {build}) — supported.")
        return True
    _warn(f"Windows {release} detected (build {build}) — target is Windows 11; some automation APIs may differ.")
    return True


def check_ram() -> bool:
    print("System RAM:")
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total_gb = stat.ullTotalPhys / (1024 ** 3)
    avail_gb = stat.ullAvailPhys / (1024 ** 3)
    print(f"         total: {total_gb:.1f} GB   available: {avail_gb:.1f} GB")
    if total_gb >= MIN_RECOMMENDED_RAM_GB:
        _ok(f"{total_gb:.1f} GB total RAM — local AI viable.")
        if avail_gb >= 3.0:
            _ok(f"{avail_gb:.1f} GB free now — comfortable headroom.")
        else:
            _warn("Free RAM is low right now. Close memory-heavy apps before "
                  "running Ollama, or Windows will page to the HDD.")
        return True
    _fail(f"Only {total_gb:.1f} GB RAM — a 3B model plus Windows may thrash. "
          f"Consider cloud APIs instead of local models.")
    return False


def check_d_drive() -> bool:
    print("D: drive free space:")
    try:
        import ctypes.wintypes as wt
        free = ctypes.c_ulonglong()
        total = ctypes.c_ulonglong()
        _ = wt  # wintypes import confirms we're on Windows with proper ctypes
        if not ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            "D:\\", None, ctypes.byref(total), ctypes.byref(free)
        ):
            raise OSError("GetDiskFreeSpaceExW failed")
    except OSError as e:
        _warn(f"Could not query D: ({e}). Ensure D:\\NOVA is on a real drive.")
        return True
    free_gb = free.value / (1024 ** 3)
    print(f"         D: free space: {free_gb:.1f} GB")
    if free_gb >= MIN_DISK_FREE_GB:
        _ok(f"{free_gb:.1f} GB free on D: — enough for {RECOMMENDED_MODEL} "
            f"and future data/logs.")
        return True
    _fail(f"Only {free_gb:.1f} GB free on D: — below the {MIN_DISK_FREE_GB:.0f} GB "
          f"minimum for models + growth.")
    return False


def check_ollama() -> bool:
    print("Ollama (local AI runtime — Phase 2 dependency):")
    installed = run_version_check("ollama", ["--version"])
    if installed:
        _ok(f"Installed: {installed}")
        _ok(f"Planned model: {RECOMMENDED_MODEL} (~2 GB, CPU-friendly).")
        return True
    _warn("Ollama not installed yet. That is expected at this stage — "
          "install/configure in the Ollama setup step (docs/ENVIRONMENT_SETUP.md).")
    return True  # informational in Phase 1 — becomes a hard check in Phase 2


# ------------------------------------------------------------------ main
def main() -> int:
    print("=" * 66)
    print("NOVA — Environment Verification (Phase 1)")
    print("=" * 66)
    results = [
        check_python(),
        check_pip(),
        check_git(),
        check_node(),
        check_windows(),
        check_ram(),
        check_d_drive(),
        check_ollama(),
    ]
    failed = results.count(False)
    print("-" * 66)
    if failed == 0:
        print("RESULT: All checks passed. Ready for Phase 1 completion.")
        return 0
    print(f"RESULT: {failed} check(s) FAILED. Fix the [FAIL] lines above first.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
