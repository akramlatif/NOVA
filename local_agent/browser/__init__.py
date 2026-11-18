"""Browser Automation Agent for NOVA.

Engineered with Playwright for resilient, accessible web navigation,
interactive automation, and sandboxed download management.
"""

from local_agent.browser.controller import BrowserController, BrowserControllerError
from local_agent.browser.downloads import DownloadManager, DownloadError
from local_agent.browser.agent import BrowserAgent

__all__ = [
    "BrowserController",
    "BrowserControllerError",
    "DownloadManager",
    "DownloadError",
    "BrowserAgent",
]
