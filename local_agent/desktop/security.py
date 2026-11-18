"""Desktop Security Module for NOVA — Phase 5.

Enforces the security rules for desktop automation:
  1. Standard user privileges only — never escalate.
  2. Explicit permission required for sensitive interactions.
  3. Applications restricted to the approved allowlist.
  4. Never silently capture sensitive screens.
  5. Emergency stop halts all automation instantly.
  6. All actions logged to the security audit trail.
"""

from __future__ import annotations

import ctypes
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from local_agent.security.audit import SecurityAuditLogger

logger = logging.getLogger(__name__)


class EmergencyStop(Exception):
    """Raised when the emergency stop is triggered during an operation."""


class DesktopSecurity:
    """Security enforcement layer for all desktop automation actions."""

    # Window titles that should never be captured or interacted with
    SENSITIVE_WINDOW_PATTERNS = [
        "password",
        "credential",
        "sign in",
        "log in",
        "login",
        "two-factor",
        "2fa",
        "authenticator",
        "security key",
        "windows security",
        "user account control",
        "certificate",
        "private key",
        "keepass",
        "1password",
        "bitwarden",
        "lastpass",
    ]

    def __init__(
        self,
        audit_logger: Optional[SecurityAuditLogger] = None,
        log_dir: Optional[Path] = None,
    ) -> None:
        log_path = log_dir or Path(__file__).resolve().parents[2] / "logs"
        self.audit = audit_logger or SecurityAuditLogger(
            log_path / "desktop_audit.jsonl"
        )

    def is_admin(self) -> bool:
        """Check if NOVA is running with administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def verify_standard_user(self) -> Dict[str, Any]:
        """Verify NOVA is running as standard user, not admin."""
        admin = self.is_admin()
        if admin:
            logger.warning(
                "NOVA is running with administrator privileges. "
                "Desktop automation should run as standard user."
            )
        return {
            "is_admin": admin,
            "safe": not admin,
            "note": (
                "Running as standard user — safe for desktop automation."
                if not admin
                else "WARNING: Running as administrator. Some actions may "
                     "have elevated access. Consider running as standard user."
            ),
        }

    def is_sensitive_window(self, title: str) -> bool:
        """Check if a window title matches sensitive patterns."""
        lower_title = title.lower()
        return any(pattern in lower_title for pattern in self.SENSITIVE_WINDOW_PATTERNS)

    def check_screenshot_safety(self, window_title: str = "") -> Dict[str, Any]:
        """Check if it is safe to take a screenshot based on the active window."""
        sensitive = self.is_sensitive_window(window_title)
        if sensitive:
            self.audit.log(
                action="screenshot_blocked",
                resource=f"window:{window_title}",
                permission_level="SENSITIVE",
                success=False,
                error="Sensitive window detected — screenshot blocked",
            )
        return {
            "safe": not sensitive,
            "window_title": window_title,
            "note": (
                "Safe to capture."
                if not sensitive
                else f"Screenshot blocked: window title {window_title!r} matches "
                     "a sensitive pattern. NOVA will not capture credential or "
                     "authentication screens."
            ),
        }

    def log_action(
        self,
        action: str,
        resource: str,
        permission_level: str = "SAFE",
        success: bool = True,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a desktop automation action to the audit trail."""
        self.audit.log(
            action=action,
            resource=resource,
            permission_level=permission_level,
            success=success,
            error=error,
            details=details,
        )

    def requires_approval(self, action: str, target: str = "") -> bool:
        """Determine if an action needs explicit user approval.

        Actions that modify system state, interact with sensitive
        applications, or involve credential entry require confirmation.
        """
        # Sensitive action patterns
        sensitive_actions = {
            "launch_terminal",
            "launch_cmd",
            "type_password",
            "hotkey_delete",
            "close_all",
            "interact_sensitive_window",
        }
        if action in sensitive_actions:
            return True
        if self.is_sensitive_window(target):
            return True
        return False
