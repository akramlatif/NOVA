"""Filesystem Sandboxing and Path Validation.

Restricts file operations strictly to approved root directories, preventing
directory traversal, UNC injection, and access to sensitive secrets.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Sequence, Union


class SecurityError(Exception):
    """Base exception for all security violations."""


class PathTraversalError(SecurityError):
    """Raised when an operation attempts to navigate outside the sandbox."""


class AccessDeniedError(SecurityError):
    """Raised when an operation targets a protected or sensitive file."""


class PathSandbox:
    """Enforces directory confinement and sensitive path blocking."""

    DEFAULT_SENSITIVE_PATTERNS = (
        ".env*",
        "*credentials*",
        "*secrets*",
        "*.pem",
        "*.key",
        "id_rsa*",
        ".git",
        ".git/*",
    )

    BLOCKED_WINDOWS_PREFIXES = (
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\Recovery",
    )

    def __init__(
        self,
        allowed_roots: Sequence[Union[str, Path]],
        sensitive_patterns: Sequence[str] = DEFAULT_SENSITIVE_PATTERNS,
    ) -> None:
        if not allowed_roots:
            raise ValueError("PathSandbox requires at least one allowed root.")
        self.allowed_roots: list[Path] = [
            Path(r).resolve() for r in allowed_roots
        ]
        self.sensitive_patterns: list[str] = list(sensitive_patterns)

    def is_within_sandbox(self, target: Path) -> bool:
        """Return True if target resides within at least one allowed root."""
        for root in self.allowed_roots:
            try:
                target.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def validate_path(
        self,
        raw_path: Union[str, Path],
        allow_write: bool = False,
    ) -> Path:
        """Validate, canonicalize, and confine a path within the sandbox.

        Raises:
            PathTraversalError: If path attempts to escape allowed roots.
            AccessDeniedError: If path matches sensitive file patterns or system directories.
        """
        path_str = str(raw_path).strip()
        if not path_str:
            raise PathTraversalError("Path cannot be empty.")

        # Guard against null byte injections
        if "\x00" in path_str:
            raise PathTraversalError("Null bytes in path are forbidden.")

        # Guard against Windows UNC paths (\\server\share)
        if path_str.startswith(r"\\") or path_str.startswith("//"):
            raise PathTraversalError("Network UNC paths are forbidden.")

        # Convert to Path and resolve symlinks/relative tokens
        candidate = Path(path_str)
        if not candidate.is_absolute():
            # Treat relative paths as relative to the primary allowed root
            candidate = self.allowed_roots[0] / candidate

        try:
            resolved = candidate.resolve()
        except (ValueError, OSError) as e:
            raise PathTraversalError(f"Could not resolve path {path_str!r}: {e}")

        # 1. System prefix check (e.g. C:\Windows)
        resolved_str = str(resolved)
        for prefix in self.BLOCKED_WINDOWS_PREFIXES:
            if resolved_str.lower().startswith(prefix.lower()):
                raise AccessDeniedError(
                    f"Access to protected system directory is forbidden: {prefix}"
                )

        # 2. Confinement check
        if not self.is_within_sandbox(resolved):
            raise PathTraversalError(
                f"Path {raw_path!r} resolves to {resolved}, which is outside "
                f"the permitted sandbox roots: {[str(r) for r in self.allowed_roots]}"
            )

        # 3. Sensitive file check
        file_name = resolved.name
        rel_str = str(resolved)
        for pattern in self.sensitive_patterns:
            if fnmatch.fnmatch(file_name.lower(), pattern.lower()) or fnmatch.fnmatch(rel_str.lower(), f"*{pattern.lower()}*"):
                raise AccessDeniedError(
                    f"Access to sensitive file or pattern is forbidden: {file_name!r}"
                )

        return resolved
