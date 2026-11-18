"""NOVA Desktop Automation Agent — Phase 5.

Provides controlled Windows desktop automation: application launching,
window management, mouse/keyboard input, screenshot capture, and
visual observation — all gated by an approved-application allowlist,
standard-user privileges, and audit logging.
"""

from local_agent.desktop.controller import DesktopController, DesktopControllerError
from local_agent.desktop.apps import AppManager, AppSpec
from local_agent.desktop.observer import ScreenObserver
from local_agent.desktop.security import DesktopSecurity, EmergencyStop

__all__ = [
    "DesktopController",
    "DesktopControllerError",
    "AppManager",
    "AppSpec",
    "ScreenObserver",
    "DesktopSecurity",
    "EmergencyStop",
]
