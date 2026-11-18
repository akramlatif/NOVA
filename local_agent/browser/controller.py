"""Browser Controller for NOVA.

Manages Playwright browser lifecycles, Chromium process instances, tabs,
navigation, and timeout controls with low-overhead flags optimized for
dual-core CPUs and bounded memory hosts.

Enforces thread-affinity via a dedicated single-threaded browser executor,
ensuring seamless compatibility with multithreaded task orchestrators.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, TypeVar
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BrowserControllerError(Exception):
    """Base exception for browser controller errors."""


class BrowserController:
    """Controls browser instances and tab sessions using a thread-affine executor."""

    RESOURCE_CONSCIOUS_ARGS = [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--mute-audio",
    ]

    def __init__(
        self,
        headless: bool = True,
        default_timeout_ms: int = 20000,
        preferred_channel: Optional[str] = "chrome",
        user_data_dir: Optional[str] = None,
    ) -> None:
        self.headless = headless
        self.default_timeout_ms = default_timeout_ms
        self.preferred_channel = preferred_channel
        self.user_data_dir = user_data_dir

        # Dedicated single-thread executor guaranteeing Playwright thread affinity
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="NOVA-Browser")

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._active_page: Optional[Page] = None

    def execute(
        self,
        action: Callable[[Page], T],
        timeout_seconds: Optional[float] = None,
    ) -> T:
        """Execute a page operation strictly on the dedicated browser thread."""
        def _runner() -> T:
            self._ensure_started()
            assert self._active_page is not None
            return action(self._active_page)

        # Allow extra headroom for cold-starting browser processes on HDD / low-power hardware
        cold_start_buffer = 30.0 if not (self._browser and self._browser.is_connected()) else 10.0
        timeout = timeout_seconds or (self.default_timeout_ms / 1000.0 + cold_start_buffer)
        try:
            future = self._executor.submit(_runner)
            return future.result(timeout=timeout)
        except Exception as e:
            if isinstance(e, (PlaywrightTimeoutError, PlaywrightError)):
                raise BrowserControllerError(f"Browser action failed: {e}") from e
            raise

    def _ensure_started(self) -> None:
        """Internal: Initialize Playwright on the browser worker thread."""
        if self._browser and self._browser.is_connected() and self._active_page:
            return

        self._playwright = sync_playwright().start()
        launch_args = list(self.RESOURCE_CONSCIOUS_ARGS)

        channels_to_try = [self.preferred_channel, "msedge", None]
        last_error = None

        for channel in channels_to_try:
            try:
                kwargs: Dict[str, Any] = {
                    "headless": self.headless,
                    "args": launch_args,
                }
                if channel:
                    kwargs["channel"] = channel

                self._browser = self._playwright.chromium.launch(**kwargs)
                logger.info("Launched browser via channel: %s (version: %s)", channel, self._browser.version)
                break
            except Exception as e:
                last_error = e
                continue

        if not self._browser:
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            raise BrowserControllerError(f"Failed to launch Chromium browser: {last_error}")

        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 NOVA/0.1",
            accept_downloads=True,
        )
        self._context.set_default_timeout(self.default_timeout_ms)
        self._active_page = self._context.new_page()

    def start(self) -> None:
        """Explicitly initialize the browser on its dedicated worker thread."""
        def _start():
            self._ensure_started()
        self._executor.submit(_start).result(timeout=self.default_timeout_ms / 1000.0 + 30.0)

    def stop(self) -> None:
        """Close browser processes and contexts on the dedicated thread."""
        def _stop():
            try:
                if self._context:
                    self._context.close()
                if self._browser:
                    self._browser.close()
                if self._playwright:
                    self._playwright.stop()
            except Exception as e:
                logger.warning("Error during browser stop: %s", e)
            finally:
                self._active_page = None
                self._context = None
                self._browser = None
                self._playwright = None

        if self._executor:
            future = self._executor.submit(_stop)
            try:
                future.result(timeout=10.0)
            except Exception:
                pass

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate active page to the specified URL."""
        def _nav(page: Page) -> Dict[str, Any]:
            try:
                response = page.goto(url, timeout=self.default_timeout_ms, wait_until="domcontentloaded")
                status = response.status if response else 200
                return {
                    "url": page.url,
                    "title": page.title(),
                    "status_code": status,
                    "success": status < 400,
                }
            except PlaywrightTimeoutError as e:
                raise BrowserControllerError(f"Navigation timed out after {self.default_timeout_ms}ms: {url}") from e
            except PlaywrightError as e:
                raise BrowserControllerError(f"Failed to load URL {url!r}: {e}") from e

        return self.execute(_nav)

    def new_tab(self, url: Optional[str] = None) -> None:
        """Open a new tab on the dedicated browser thread."""
        def _new_tab(page: Page) -> None:
            assert self._context is not None
            self._active_page = self._context.new_page()
            if url:
                self._active_page.goto(url, timeout=self.default_timeout_ms)

        self.execute(_new_tab)

    def close_current_tab(self) -> None:
        """Close current tab on the dedicated browser thread."""
        def _close_tab(page: Page) -> None:
            if self._active_page:
                self._active_page.close()
            if self._context and self._context.pages:
                self._active_page = self._context.pages[-1]
            else:
                self._active_page = None

        self.execute(_close_tab)

    def list_tabs(self) -> List[Dict[str, str]]:
        """List all open tabs."""
        def _tabs(page: Page) -> List[Dict[str, str]]:
            if not self._context:
                return []
            return [
                {"index": str(i), "title": p.title(), "url": p.url}
                for i, p in enumerate(self._context.pages)
            ]

        return self.execute(_tabs)
