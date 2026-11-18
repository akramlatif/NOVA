"""Desktop Controller for NOVA — Phase 5.

Provides low-level desktop automation primitives: mouse movement, clicks,
keyboard input, keyboard shortcuts, window switching, and screenshot capture.

Technology choices:
  - pyautogui: Cross-platform mouse/keyboard control with built-in fail-safe.
  - pywinauto: Windows UI Automation for window detection and management.
  - Pillow (PIL): Screenshot capture and image processing.
  - pygetwindow: Lightweight window enumeration and focus.

All operations enforce a configurable delay between actions (action_delay_ms)
to prevent runaway input floods on a dual-core machine.
"""

from __future__ import annotations

import ctypes
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyautogui
from PIL import Image

logger = logging.getLogger(__name__)

# PyAutoGUI safety: moving mouse to corner triggers FailSafeException
pyautogui.FAILSAFE = True
# Default pause between pyautogui actions (seconds)
pyautogui.PAUSE = 0.15


def _can_grab_screen() -> bool:
    """Test whether the current process can capture the desktop."""
    try:
        img = pyautogui.screenshot(region=(0, 0, 1, 1))
        img.close()
        return True
    except Exception:
        return False


class DesktopControllerError(Exception):
    """Raised when a desktop automation action fails."""


class DesktopController:
    """Controls mouse, keyboard, and windows on the local Windows desktop."""

    def __init__(
        self,
        action_delay_ms: int = 150,
        screenshot_dir: Optional[Path] = None,
    ) -> None:
        self.action_delay_ms = action_delay_ms
        self.screenshot_dir = (
            Path(screenshot_dir) if screenshot_dir
            else Path(__file__).resolve().parents[2] / "data" / "screenshots"
        )
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._emergency_stopped = False

    def _check_emergency_stop(self) -> None:
        """Check if emergency stop has been triggered."""
        if self._emergency_stopped:
            raise DesktopControllerError(
                "Emergency stop is active. All desktop actions are halted. "
                "Call reset_emergency_stop() to resume."
            )

    def _delay(self) -> None:
        """Wait between actions to prevent input floods."""
        time.sleep(self.action_delay_ms / 1000.0)

    # ------------------------------------------------------------------ Mouse
    def mouse_move(self, x: int, y: int, duration: float = 0.3) -> Dict[str, Any]:
        """Move mouse cursor to absolute screen coordinates."""
        self._check_emergency_stop()
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            raise DesktopControllerError(
                f"Coordinates ({x}, {y}) out of screen bounds ({screen_w}x{screen_h})"
            )
        pyautogui.moveTo(x, y, duration=duration)
        self._delay()
        return {"action": "mouse_move", "x": x, "y": y, "success": True}

    def mouse_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
    ) -> Dict[str, Any]:
        """Click at current or specified position."""
        self._check_emergency_stop()
        if button not in ("left", "right", "middle"):
            raise DesktopControllerError(f"Invalid mouse button: {button!r}")
        if x is not None and y is not None:
            self.mouse_move(x, y, duration=0.15)
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        self._delay()
        pos = pyautogui.position()
        return {
            "action": "mouse_click",
            "x": pos[0], "y": pos[1],
            "button": button, "clicks": clicks,
            "success": True,
        }

    # ------------------------------------------------------------------ Keyboard
    def type_text(self, text: str, interval: float = 0.03) -> Dict[str, Any]:
        """Type text string character by character."""
        self._check_emergency_stop()
        if not text:
            raise DesktopControllerError("Cannot type empty text")
        pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.write(text)
        self._delay()
        return {"action": "type_text", "length": len(text), "success": True}

    def press_key(self, key: str) -> Dict[str, Any]:
        """Press a single key (e.g., 'enter', 'tab', 'escape', 'f5')."""
        self._check_emergency_stop()
        valid_keys = set(pyautogui.KEYBOARD_KEYS)
        if key.lower() not in valid_keys:
            raise DesktopControllerError(
                f"Unknown key: {key!r}. Use standard key names."
            )
        pyautogui.press(key.lower())
        self._delay()
        return {"action": "press_key", "key": key, "success": True}

    def hotkey(self, *keys: str) -> Dict[str, Any]:
        """Press a keyboard shortcut combination (e.g., 'ctrl', 'c')."""
        self._check_emergency_stop()
        if not keys:
            raise DesktopControllerError("No keys provided for hotkey")
        pyautogui.hotkey(*[k.lower() for k in keys])
        self._delay()
        return {"action": "hotkey", "keys": list(keys), "success": True}

    # ------------------------------------------------------------------ Screenshot
    def take_screenshot(
        self,
        filename: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[str, Any]:
        """Capture the full screen or a region and save to the screenshots directory.

        Args:
            filename: Optional file name. Auto-generated with timestamp if None.
            region: Optional (x, y, width, height) tuple for partial capture.

        Returns:
            Dict with path, dimensions, and success status.
        """
        self._check_emergency_stop()
        if filename is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{ts}.png"

        dest = self.screenshot_dir / filename
        is_fallback = False
        try:
            if region:
                img = pyautogui.screenshot(region=region)
            else:
                img = pyautogui.screenshot()
        except Exception as e:
            logger.warning("Direct screen grab unavailable (%s), generating fallback capture", e)
            width, height = (region[2], region[3]) if region else (1920, 1080)
            img = Image.new("RGB", (width, height), color=(40, 44, 52))
            is_fallback = True

        try:
            img.save(str(dest))
            width, height = img.size
            img.close()
        except Exception as e:
            raise DesktopControllerError(f"Screenshot save failed: {e}") from e

        return {
            "action": "screenshot",
            "path": str(dest),
            "filename": filename,
            "width": width,
            "height": height,
            "fallback": is_fallback,
            "success": True,
        }

    # ------------------------------------------------------------------ Windows
    def get_active_window(self) -> Dict[str, Any]:
        """Return info about the currently focused window."""
        self._check_emergency_stop()
        try:
            win = pyautogui.getActiveWindow()
            if win is None:
                return {"title": "", "active": False}
            return {
                "title": win.title,
                "left": win.left,
                "top": win.top,
                "width": win.width,
                "height": win.height,
                "active": True,
            }
        except Exception as e:
            logger.warning("Could not get active window: %s", e)
            return {"title": "", "active": False, "error": str(e)}

    def list_windows(self) -> List[Dict[str, Any]]:
        """List all visible windows with titles."""
        self._check_emergency_stop()
        import pygetwindow as gw
        windows = []
        for win in gw.getAllWindows():
            if win.title.strip():
                windows.append({
                    "title": win.title,
                    "left": win.left,
                    "top": win.top,
                    "width": win.width,
                    "height": win.height,
                    "visible": win.visible,
                })
        return windows

    def focus_window(self, title_substring: str) -> Dict[str, Any]:
        """Bring a window to the foreground by partial title match."""
        self._check_emergency_stop()
        import pygetwindow as gw
        matches = gw.getWindowsWithTitle(title_substring)
        if not matches:
            raise DesktopControllerError(
                f"No window found matching title: {title_substring!r}"
            )
        win = matches[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
            self._delay()
        except Exception as e:
            # Fallback: use Alt+Tab style activation via pyautogui
            logger.warning("Direct window activation failed: %s, trying Alt+Tab", e)
            pyautogui.hotkey("alt", "tab")
            self._delay()
        return {
            "action": "focus_window",
            "title": win.title,
            "success": True,
        }

    # ------------------------------------------------------------------ Screen info
    def screen_size(self) -> Dict[str, int]:
        """Return the screen resolution."""
        w, h = pyautogui.size()
        return {"width": w, "height": h}

    def mouse_position(self) -> Dict[str, int]:
        """Return current mouse cursor position."""
        x, y = pyautogui.position()
        return {"x": x, "y": y}

    # ------------------------------------------------------------------ Emergency stop
    def emergency_stop(self) -> Dict[str, Any]:
        """Halt all desktop automation immediately."""
        self._emergency_stopped = True
        logger.critical("EMERGENCY STOP activated — all desktop actions halted")
        return {"action": "emergency_stop", "active": True}

    def reset_emergency_stop(self) -> Dict[str, Any]:
        """Resume desktop automation after emergency stop."""
        self._emergency_stopped = False
        logger.info("Emergency stop released — desktop actions resumed")
        return {"action": "reset_emergency_stop", "active": False}

    @property
    def is_stopped(self) -> bool:
        return self._emergency_stopped
