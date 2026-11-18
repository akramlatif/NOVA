"""Controlled Terminal Interface for NOVA — Phase 6.

Executes CLI commands strictly through an allowlist with input validation,
environment sanitization, buffer bounding, and hard timeouts.
Unrestricted arbitrary shell execution is strictly prohibited.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from local_agent.security.terminal import TerminalAllowlist, BlockedCommandError

logger = logging.getLogger(__name__)


class TerminalExecutionError(Exception):
    """Raised when a controlled command execution fails."""


class ControlledTerminal:
    """Safe terminal executor with strict allowlist and bounds."""

    # Environment keys that must never be leaked or passed to subprocesses
    STRIPPED_ENV_VARS = {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "PASSWORD",
        "SECRET",
        "PRIVATE_KEY",
    }

    def __init__(
        self,
        allowlist: Optional[TerminalAllowlist] = None,
        working_dir: Optional[Path] = None,
        max_output_bytes: int = 50 * 1024,  # 50 KB output ceiling
    ) -> None:
        self.allowlist = allowlist or TerminalAllowlist()
        self.working_dir = Path(working_dir).resolve() if working_dir else Path.cwd()
        self.max_output_bytes = max_output_bytes

    def execute(
        self,
        command_line: str,
        timeout_seconds: float = 20.0,
        working_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Validate and run an approved CLI command."""
        # Validate through TerminalAllowlist
        self.allowlist.validate_command(command_line)

        # Prepare sanitized environment
        clean_env = dict(os.environ)
        for var in self.STRIPPED_ENV_VARS:
            clean_env.pop(var, None)

        cwd = working_dir or self.working_dir
        start_time = time.time()

        try:
            # Use shell=False where possible, or controlled shell for Windows builtins like dir
            first_token = command_line.strip().split()[0].lower()
            needs_shell = first_token in {"dir", "type", "ver", "echo"}

            proc = subprocess.run(
                command_line if needs_shell else command_line.split(),
                shell=needs_shell,
                cwd=cwd,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                errors="replace",
            )
            duration = round(time.time() - start_time, 3)

            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            # Truncate if output exceeds limit
            truncated = len(stdout.encode("utf-8")) > self.max_output_bytes
            if truncated:
                stdout = stdout[:self.max_output_bytes] + "\n... [Output Truncated]"

            return {
                "command": command_line,
                "exit_code": proc.returncode,
                "success": proc.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "duration_seconds": duration,
                "truncated": truncated,
            }
        except subprocess.TimeoutExpired as e:
            raise TerminalExecutionError(
                f"Command timed out after {timeout_seconds} seconds: {command_line}"
            ) from e
        except OSError as e:
            raise TerminalExecutionError(
                f"Command execution failed: {e}"
            ) from e
