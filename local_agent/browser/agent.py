"""Browser Automation Agent for NOVA.

Provides high-level accessible website interaction, text extraction,
sandboxed downloads, and user-assisted authentication mechanisms.
All actions execute thread-safely via BrowserController.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from local_agent.browser.controller import BrowserController, BrowserControllerError
from local_agent.browser.downloads import DownloadManager, DownloadError
from local_agent.tasks.web_tools import _validate_safe_url

logger = logging.getLogger(__name__)


class BrowserAgent:
    """Autonomous agent for web navigation, form interaction, and file downloads."""

    def __init__(
        self,
        controller: Optional[BrowserController] = None,
        download_manager: Optional[DownloadManager] = None,
    ) -> None:
        self.controller = controller or BrowserController(headless=True)
        self.download_manager = download_manager or DownloadManager(
            download_dir=Path(__file__).resolve().parents[2] / "data" / "downloads"
        )

    def _locate(self, page: Page, selector: str) -> Locator:
        """Find an element using accessible roles and locators before falling back to CSS."""
        raw = selector.strip()

        # 1. Exact or partial text match
        if raw.startswith("text="):
            return page.get_by_text(raw[5:])

        # 2. Semantic role match if specified as 'role=button:Submit'
        if raw.startswith("role="):
            parts = raw[5:].split(":", 1)
            role_name = parts[0].strip()
            name_filter = parts[1].strip() if len(parts) > 1 else None
            return page.get_by_role(role_name, name=name_filter)  # type: ignore

        # 3. Label / Placeholder matches
        if raw.startswith("label="):
            return page.get_by_label(raw[6:])
        if raw.startswith("placeholder="):
            return page.get_by_placeholder(raw[12:])

        # 4. Standard CSS or XPath selector fallback
        return page.locator(raw)

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a verified public URL."""
        safe_url = _validate_safe_url(url)
        return self.controller.navigate(safe_url)

    def click(self, selector: str, timeout_ms: int = 10000) -> Dict[str, Any]:
        """Click an element using semantic or accessible locators."""
        def _click_action(page: Page) -> Dict[str, Any]:
            locator = self._locate(page, selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            locator.click(timeout=timeout_ms)
            return {"action": "click", "selector": selector, "success": True}

        return self.controller.execute(_click_action)

    def fill(self, selector: str, text: str, timeout_ms: int = 10000) -> Dict[str, Any]:
        """Fill an accessible input field or textbox."""
        def _fill_action(page: Page) -> Dict[str, Any]:
            locator = self._locate(page, selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            locator.fill(text, timeout=timeout_ms)
            return {"action": "fill", "selector": selector, "success": True}

        return self.controller.execute(_fill_action)

    def scroll(self, direction: str = "down", amount: int = 600) -> Dict[str, Any]:
        """Scroll the active page up or down."""
        def _scroll_action(page: Page) -> Dict[str, Any]:
            delta = amount if direction.lower() == "down" else -amount
            page.evaluate(f"window.scrollBy(0, {delta})")
            return {"action": "scroll", "direction": direction, "amount": amount, "success": True}

        return self.controller.execute(_scroll_action)

    def extract_visible_text(self, max_chars: int = 6000) -> Dict[str, Any]:
        """Extract clean, visible readable text from the current page."""
        def _extract_action(page: Page) -> Dict[str, Any]:
            text = page.evaluate("() => document.body ? document.body.innerText : ''")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)

            truncated = len(clean_text) > max_chars
            if truncated:
                clean_text = clean_text[:max_chars] + "\n... [Content Truncated for Context Limits]"

            return {
                "title": page.title(),
                "url": page.url,
                "text": clean_text,
                "char_count": len(clean_text),
                "truncated": truncated,
            }

        return self.controller.execute(_extract_action)

    def find_links(self, query: Optional[str] = None, max_results: int = 15) -> Dict[str, Any]:
        """Find interactive links on the page, optionally filtered by keyword."""
        def _links_action(page: Page) -> Dict[str, Any]:
            raw_links = page.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href
                }))"""
            )

            results: List[Dict[str, str]] = []
            q = (query or "").lower().strip()
            for link in raw_links:
                text = link.get("text", "")
                href = link.get("href", "")
                if not href or href.startswith("javascript:"):
                    continue
                if not q or q in text.lower() or q in href.lower():
                    results.append({"text": text or "[No Anchor Text]", "href": href})
                if len(results) >= max_results:
                    break

            return {
                "query": query,
                "count": len(results),
                "links": results,
            }

        return self.controller.execute(_links_action)

    def download_file(
        self,
        trigger_selector: str,
        suggested_name: Optional[str] = None,
        timeout_ms: int = 30000,
    ) -> Dict[str, Any]:
        """Trigger and verify a file download into the isolated downloads sandbox."""
        def _download_action(page: Page) -> Dict[str, Any]:
            locator = self._locate(page, trigger_selector).first

            with page.expect_download(timeout=timeout_ms) as download_info:
                locator.click()
            download = download_info.value

            filename = suggested_name or download.suggested_filename
            self.download_manager.validate_file_type(filename)
            dest_path = self.download_manager.resolve_unique_path(filename)

            download.save_as(str(dest_path))
            verification = self.download_manager.verify_download(dest_path)

            return {
                "action": "download",
                "status": "completed",
                "filename": verification["filename"],
                "path": verification["path"],
                "size_bytes": verification["size_bytes"],
                "sha256": verification["sha256"],
            }

        return self.controller.execute(_download_action, timeout_seconds=timeout_ms / 1000.0 + 10.0)

    def interactive_user_session(
        self,
        url: str,
        instructions: str,
        wait_seconds: int = 45,
    ) -> Dict[str, Any]:
        """Launch a headed browser window to allow user to complete manual login, MFA, or CAPTCHA."""
        safe_url = _validate_safe_url(url)
        was_headless = self.controller.headless
        if was_headless:
            self.controller.stop()
            self.controller.headless = False

        try:
            self.controller.navigate(safe_url)
            logger.info("Awaiting manual user completion: %s", instructions)
            time.sleep(wait_seconds)
            def _session_report(page: Page) -> Dict[str, Any]:
                return {
                    "action": "interactive_session",
                    "final_url": page.url,
                    "title": page.title(),
                    "status": "completed",
                    "instructions": instructions,
                }
            return self.controller.execute(_session_report)
        finally:
            if was_headless:
                self.controller.stop()
                self.controller.headless = True
