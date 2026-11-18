"""Terminal Command Allowlist and Safety Enforcement.

Ensures NOVA only executes pre-approved, non-destructive CLI commands,
blocking arbitrary shell injection, disk formatting, and privilege escalation.
"""

from __future__ import annotations

import re
import shlex
from typing import Sequence
from local_agent.security.paths import SecurityError


class BlockedCommandError(SecurityError):
    """Raised when an unapproved or dangerous shell command is requested."""


class TerminalAllowlist:
    """Enforces strict allowlisting and blocked pattern detection for terminal tools."""

    DEFAULT_ALLOWED_COMMANDS = {
        "dir",
        "echo",
        "type",
        "git",
        "python",
        "py",
        "pytest",
        "where",
        "whoami",
        "hostname",
        "ver",
    }

    BLOCKED_PATTERNS = (
        r"\bformat\b",
        r"\bdel\s+/[sS]\b",
        r"\brmdir\s+/[sS]\b",
        r"\breg\b",
        r"\bpowershell.*-enc",
        r"\bInvoke-Expression\b",
        r"\biex\b",
        r"\bcurl.*\|\s*(?:sh|bash|cmd|powershell)\b",
        r"\bshutdown\b",
        r"\btaskkill\s+/[fF]\b",
        r"\bnet\s+user\b",
        r"\bdiskpart\b",
        r";\s*rm\b",
        r"\|\s*rm\b",
    )

    def __init__(
        self,
        allowed_commands: Sequence[str] | set[str] | None = None,
    ) -> None:
        self.allowed_commands: set[str] = (
            set(allowed_commands) if allowed_commands is not None
            else set(self.DEFAULT_ALLOWED_COMMANDS)
        )

    def validate_command(self, cmd_line: str) -> tuple[str, list[str]]:
        """Validate and parse a command line string.

        Returns:
            Tuple of (base_command, argument_list)

        Raises:
            BlockedCommandError: If command is not allowlisted or matches blocked patterns.
        """
        raw = cmd_line.strip()
        if not raw:
            raise BlockedCommandError("Command line cannot be empty.")

        # 1. Check against blocked malicious patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, raw, re.IGNORECASE):
                raise BlockedCommandError(
                    f"Command contains prohibited or destructive pattern: {pattern}"
                )

        # 2. Tokenize command arguments safely for Windows
        try:
            tokens = shlex.split(raw, posix=False)
        except ValueError as e:
            raise BlockedCommandError(f"Could not parse command string: {e}")

        if not tokens:
            raise BlockedCommandError("No executable command found.")

        base_cmd = tokens[0].lower().rstrip(".exe")

        # 3. Allowlist gate
        if base_cmd not in self.allowed_commands:
            raise BlockedCommandError(
                f"Command '{base_cmd}' is not in the approved command allowlist. "
                f"Allowed: {sorted(list(self.allowed_commands))}"
            )

        # 4. Specific guardrails for allowed utilities (e.g. Git destructive flags)
        if base_cmd == "git":
            args_str = " ".join(tokens[1:]).lower()
            if "--force" in args_str or "-f " in args_str:
                raise BlockedCommandError("Force push/modify via Git is forbidden.")
            if "clean -fdx" in args_str or "reset --hard" in args_str:
                raise BlockedCommandError("Destructive Git operations are forbidden.")

        return tokens[0], tokens[1:]
