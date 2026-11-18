"""Safe Terminal Command Execution Tool for NOVA.

Executes only allowlisted, non-destructive CLI commands within sandboxed
timeouts and bounded output buffers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from local_agent.security.terminal import TerminalAllowlist, BlockedCommandError


class TerminalToolError(Exception):
    """Base exception for terminal tool failures."""


def terminal_run(
    allowlist: TerminalAllowlist,
    command: str,
    working_dir: Optional[str] = None,
    timeout_seconds: float = 20.0,
    max_output_chars: int = 50000,
) -> Dict[str, Any]:
    """Execute an allowlisted CLI command safely.

    Args:
        allowlist: Active TerminalAllowlist instance enforcing permissions.
        command: Command line string to execute.
        working_dir: Optional working directory for the process.
        timeout_seconds: Hard execution cutoff (default 20s).
        max_output_chars: Output truncation limit (default 50 KB).

    Raises:
        TerminalToolError: On validation failure, timeout, or OS execution error.
    """
    try:
        base_cmd, args = allowlist.validate_command(command)
    except BlockedCommandError as e:
        raise TerminalToolError(f"Permission denied: {e}") from e

    cwd_path = Path(working_dir).resolve() if working_dir else None
    if cwd_path and not cwd_path.is_dir():
        raise TerminalToolError(f"Working directory does not exist: {working_dir}")

    full_cmd = [base_cmd, *args]
    try:
        proc = subprocess.run(
            full_cmd,
            cwd=str(cwd_path) if cwd_path else None,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as e:
        raise TerminalToolError(
            f"Command timed out after {timeout_seconds} seconds: {command}"
        ) from e
    except OSError as e:
        raise TerminalToolError(f"Failed to execute command {command!r}: {e}") from e

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    truncated = False

    if len(stdout) > max_output_chars:
        stdout = stdout[:max_output_chars] + "\n... [Output Truncated]"
        truncated = True

    if len(stderr) > max_output_chars:
        stderr = stderr[:max_output_chars] + "\n... [Stderr Truncated]"
        truncated = True

    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": truncated,
        "success": proc.returncode == 0,
    }
