"""Screen Observer for NOVA — Phase 5.

Provides screenshot-based observation to verify whether desktop
actions succeeded. The observer captures the screen, compares
expected state against visible state, and reports confidence.

IMPORTANT: This is NOT autonomous "vision-AI" that claims to
understand arbitrary UIs. It provides structured capture and
basic heuristic checks. The human user is asked for help when
the interface state is ambiguous.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class ScreenObserver:
    """Screenshot-based observation system for desktop action verification."""

    def __init__(
        self,
        screenshot_dir: Optional[Path] = None,
        max_screenshots: int = 20,
    ) -> None:
        self.screenshot_dir = (
            Path(screenshot_dir) if screenshot_dir
            else Path(__file__).resolve().parents[2] / "data" / "screenshots"
        )
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.max_screenshots = max_screenshots
        self._history: List[Dict[str, Any]] = []

    def capture(
        self,
        label: str = "",
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[str, Any]:
        """Capture a timestamped screenshot and add it to observation history.

        Args:
            label: Human-readable label (e.g., 'after_click_save').
            region: Optional (x, y, width, height) for partial capture.

        Returns:
            Dict with path, dimensions, hash, and metadata.
        """
        ts = time.strftime("%Y%m%d_%H%M%S")
        label_clean = label.replace(" ", "_")[:50] if label else "obs"
        filename = f"{ts}_{label_clean}.png"
        dest = self.screenshot_dir / filename

        try:
            import pyautogui
            if region:
                img = pyautogui.screenshot(region=region)
            else:
                img = pyautogui.screenshot()
        except Exception as e:
            logger.warning("Screen grab unavailable (%s), using fallback canvas", e)
            width, height = (region[2], region[3]) if region else (1920, 1080)
            img = Image.new("RGB", (width, height), color=(40, 44, 52))

        try:
            img.save(str(dest))
            width, height = img.size

            # Compute hash for change-detection
            img_bytes = img.tobytes()
            img_hash = hashlib.md5(img_bytes).hexdigest()
            img.close()
        except Exception as e:
            raise RuntimeError(f"Screen capture failed: {e}") from e

        record = {
            "path": str(dest),
            "filename": filename,
            "label": label,
            "width": width,
            "height": height,
            "hash": img_hash,
            "timestamp": ts,
        }

        self._history.append(record)
        # Limit stored history
        if len(self._history) > self.max_screenshots:
            self._history = self._history[-self.max_screenshots:]

        return record

    def did_screen_change(
        self,
        label_before: str = "before",
        label_after: str = "after",
        region: Optional[Tuple[int, int, int, int]] = None,
        wait_seconds: float = 1.0,
    ) -> Dict[str, Any]:
        """Capture before and after screenshots, report whether the screen changed.

        This is a heuristic: it uses pixel hash comparison to determine
        whether a visible change occurred. It does NOT understand what changed.

        Args:
            label_before: Label for the 'before' screenshot.
            label_after: Label for the 'after' screenshot.
            region: Optional region to focus on.
            wait_seconds: Delay between captures.

        Returns:
            Dict with before/after hashes and whether change was detected.
        """
        before = self.capture(label=label_before, region=region)
        time.sleep(wait_seconds)
        after = self.capture(label=label_after, region=region)

        changed = before["hash"] != after["hash"]
        return {
            "changed": changed,
            "before_hash": before["hash"],
            "after_hash": after["hash"],
            "before_path": before["path"],
            "after_path": after["path"],
            "confidence": "high" if changed else "uncertain",
            "note": (
                "Screen content changed between captures."
                if changed
                else "No visible change detected. The action may not have had a visible effect, "
                     "or the change may be too subtle. Consider asking the user to verify."
            ),
        }

    def verify_window_title(
        self,
        expected_title: str,
    ) -> Dict[str, Any]:
        """Check if any visible window title matches the expected string.

        Uses pygetwindow for reliable window title enumeration rather than
        attempting OCR on a screenshot.
        """
        import pygetwindow as gw
        all_windows = gw.getAllWindows()
        matched = [
            w.title for w in all_windows
            if expected_title.lower() in w.title.lower() and w.title.strip()
        ]
        found = len(matched) > 0
        return {
            "expected": expected_title,
            "found": found,
            "matching_titles": matched[:5],
            "confidence": "high" if found else "low",
            "note": (
                f"Window with title matching {expected_title!r} is visible."
                if found
                else f"No window matching {expected_title!r} found. "
                     "The application may not have opened or the title may differ."
            ),
        }

    def request_human_help(self, reason: str) -> Dict[str, Any]:
        """Signal that NOVA needs the user to verify the current screen state.

        This is called when automated verification is insufficient
        (e.g., ambiguous UI, dialog box, unexpected popup).
        """
        screenshot = self.capture(label="help_requested")
        return {
            "action": "request_human_help",
            "reason": reason,
            "screenshot": screenshot["path"],
            "note": (
                f"NOVA cannot confidently determine the screen state. "
                f"Reason: {reason}. "
                f"A screenshot has been saved at {screenshot['path']}. "
                f"Please verify the current state and advise."
            ),
        }

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Return the recent screenshot observation history."""
        return list(self._history)

    def cleanup_old_screenshots(self, keep_last: int = 10) -> Dict[str, Any]:
        """Remove old screenshots, keeping only the most recent ones."""
        all_pngs = sorted(self.screenshot_dir.glob("*.png"))
        removed = []
        for f in all_pngs[:-keep_last] if len(all_pngs) > keep_last else []:
            try:
                f.unlink()
                removed.append(f.name)
            except OSError:
                pass
        return {"removed_count": len(removed), "removed": removed}
