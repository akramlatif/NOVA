"""Application Manager for NOVA — Phase 5.

Maintains an explicit allowlist of applications NOVA is permitted to launch.
Every app has a known executable path, display name, and permission tier.
Applications NOT in the allowlist are unconditionally rejected.

Security principle: NOVA never launches arbitrary executables.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppSpec:
    """Declaration of one approved application."""
    name: str                        # Human-readable name (e.g., "Notepad")
    exe_path: str                    # Executable path or command
    description: str = ""
    args: List[str] = field(default_factory=list)
    requires_approval: bool = False  # Sensitive apps need user confirmation
    working_dir: Optional[str] = None


class AppManagerError(Exception):
    """Raised when an application launch or management operation fails."""


class AppManager:
    """Manages the allowlist of approved applications and their lifecycle."""

    # Default approved applications for Windows 11
    DEFAULT_APPS: Dict[str, AppSpec] = {
        "notepad": AppSpec(
            name="Notepad",
            exe_path="notepad.exe",
            description="Windows built-in text editor",
        ),
        "calculator": AppSpec(
            name="Calculator",
            exe_path="calc.exe",
            description="Windows calculator",
        ),
        "explorer": AppSpec(
            name="File Explorer",
            exe_path="explorer.exe",
            description="Windows File Explorer",
        ),
        "terminal": AppSpec(
            name="Windows Terminal",
            exe_path="wt.exe",
            description="Windows Terminal (PowerShell / CMD)",
            requires_approval=True,
        ),
        "cmd": AppSpec(
            name="Command Prompt",
            exe_path="cmd.exe",
            description="Legacy Windows Command Prompt",
            requires_approval=True,
        ),
    }

    # Well-known paths to auto-detect optional apps
    _OPTIONAL_DETECTIONS: List[Dict[str, Any]] = [
        {
            "key": "vscode",
            "name": "Visual Studio Code",
            "candidates": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
            "description": "Code editor",
            "requires_approval": False,
        },
        {
            "key": "chrome",
            "name": "Google Chrome",
            "candidates": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            "description": "Web browser",
            "requires_approval": False,
        },
        {
            "key": "edge",
            "name": "Microsoft Edge",
            "candidates": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "description": "Web browser",
            "requires_approval": False,
        },
    ]

    def __init__(self, extra_apps: Optional[Dict[str, AppSpec]] = None) -> None:
        self._apps: Dict[str, AppSpec] = dict(self.DEFAULT_APPS)
        self._detect_optional_apps()
        if extra_apps:
            self._apps.update(extra_apps)
        self._running: Dict[str, subprocess.Popen] = {}

    def _detect_optional_apps(self) -> None:
        """Auto-detect commonly installed applications."""
        for det in self._OPTIONAL_DETECTIONS:
            if det["key"] in self._apps:
                continue
            for candidate in det["candidates"]:
                if Path(candidate).exists():
                    self._apps[det["key"]] = AppSpec(
                        name=det["name"],
                        exe_path=candidate,
                        description=det["description"],
                        requires_approval=det.get("requires_approval", False),
                    )
                    logger.info("Auto-detected %s at %s", det["name"], candidate)
                    break

    def list_apps(self) -> List[Dict[str, Any]]:
        """Return the allowlist of approved applications."""
        return [
            {
                "key": key,
                "name": spec.name,
                "exe_path": spec.exe_path,
                "description": spec.description,
                "requires_approval": spec.requires_approval,
            }
            for key, spec in sorted(self._apps.items())
        ]

    def is_approved(self, app_key: str) -> bool:
        """Check if an app key is in the approved allowlist."""
        return app_key.lower() in self._apps

    def get_app(self, app_key: str) -> AppSpec:
        """Get app spec by key, or raise if not approved."""
        key = app_key.lower()
        if key not in self._apps:
            available = sorted(self._apps.keys())
            raise AppManagerError(
                f"Application {app_key!r} is not in the approved list. "
                f"Approved: {available}"
            )
        return self._apps[key]

    def register_app(self, key: str, spec: AppSpec) -> None:
        """Add a new app to the allowlist at runtime."""
        self._apps[key.lower()] = spec

    def launch(
        self,
        app_key: str,
        extra_args: Optional[List[str]] = None,
        wait_seconds: float = 2.0,
    ) -> Dict[str, Any]:
        """Launch an approved application.

        Args:
            app_key: Allowlist key (e.g., 'notepad', 'calculator').
            extra_args: Additional command-line arguments.
            wait_seconds: Time to wait for the process to stabilize.

        Returns:
            Dict with process info and success status.
        """
        spec = self.get_app(app_key)
        cmd = [spec.exe_path] + list(spec.args) + (extra_args or [])
        cwd = spec.working_dir

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            # Give the application time to initialize its window
            time.sleep(wait_seconds)

            if proc.poll() is not None:
                raise AppManagerError(
                    f"Application {spec.name!r} exited immediately with code {proc.returncode}"
                )

            self._running[app_key.lower()] = proc
            logger.info("Launched %s (PID %d)", spec.name, proc.pid)

            return {
                "action": "launch",
                "app": spec.name,
                "app_key": app_key.lower(),
                "pid": proc.pid,
                "success": True,
            }
        except FileNotFoundError:
            raise AppManagerError(
                f"Executable not found: {spec.exe_path!r}. "
                f"Is {spec.name} installed?"
            ) from None
        except OSError as e:
            raise AppManagerError(
                f"Failed to launch {spec.name}: {e}"
            ) from e

    def close(self, app_key: str, force: bool = False) -> Dict[str, Any]:
        """Close a running application by its key."""
        key = app_key.lower()
        proc = self._running.get(key)
        if proc is None or proc.poll() is not None:
            self._running.pop(key, None)
            return {"action": "close", "app_key": key, "success": True, "note": "already closed"}

        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3.0)
        except Exception as e:
            logger.warning("Error closing %s: %s", key, e)

        self._running.pop(key, None)
        return {"action": "close", "app_key": key, "success": True}

    def is_running(self, app_key: str) -> bool:
        """Check if an app launched by NOVA is still running."""
        key = app_key.lower()
        proc = self._running.get(key)
        if proc is None:
            return False
        if proc.poll() is not None:
            self._running.pop(key, None)
            return False
        return True

    def close_all(self) -> Dict[str, Any]:
        """Close all applications launched by NOVA."""
        closed = []
        for key in list(self._running.keys()):
            self.close(key)
            closed.append(key)
        return {"action": "close_all", "closed": closed, "success": True}
