"""Browser Tool Adapters for NOVA's Task Planner and Tool Registry.

Exposes high-level browser actions to the Agent Orchestrator with explicit
permission tiers, timeouts, and error handling.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from local_agent.browser.agent import BrowserAgent
from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec


def register_browser_tools(
    registry: ToolRegistry,
    agent: Optional[BrowserAgent] = None,
) -> BrowserAgent:
    """Register all Phase 4 Browser Automation tools into the registry."""
    browser_agent = agent or BrowserAgent()

    # 1. Navigation
    registry.register(ToolSpec(
        name="browser_navigate",
        description="Navigate the browser to a public website URL.",
        handler=lambda url: browser_agent.navigate(url),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=25.0,
        input_schema={"url": "string (http/https)"},
        output_schema={"url": "string", "title": "string", "status_code": "int"},
        error_notes="Raises BrowserControllerError on network failure or SSRF violation.",
    ))

    # 2. Click
    registry.register(ToolSpec(
        name="browser_click",
        description="Click an element using accessible roles (role=button:Search) or CSS selector.",
        handler=lambda selector: browser_agent.click(selector),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"selector": "string (e.g. 'role=button:Search' or '#submit')"},
        output_schema={"action": "click", "success": "bool"},
        error_notes="Raises BrowserControllerError if element not found.",
    ))

    # 3. Fill input
    registry.register(ToolSpec(
        name="browser_fill",
        description="Type text into an input field or search box using accessible locators.",
        handler=lambda selector, text: browser_agent.fill(selector, text),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"selector": "string", "text": "string"},
        output_schema={"action": "fill", "success": "bool"},
        error_notes="Raises BrowserControllerError if element not found or not editable.",
    ))

    # 4. Scroll
    registry.register(ToolSpec(
        name="browser_scroll",
        description="Scroll page up or down.",
        handler=lambda direction="down", amount=600: browser_agent.scroll(direction, amount),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={"direction": "optional string ('down' or 'up')", "amount": "optional int"},
        output_schema={"action": "scroll", "success": "bool"},
        error_notes="Cannot fail under normal conditions.",
    ))

    # 5. Extract text
    registry.register(ToolSpec(
        name="browser_extract_text",
        description="Extract visible text and title from the active web page.",
        handler=lambda max_chars=6000: browser_agent.extract_visible_text(max_chars),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"max_chars": "optional int"},
        output_schema={"title": "string", "text": "string", "char_count": "int"},
        error_notes="Raises BrowserControllerError if page is unreachable.",
    ))

    # 6. Find links
    registry.register(ToolSpec(
        name="browser_find_links",
        description="Locate links on the page matching an optional keyword.",
        handler=lambda query=None, max_results=15: browser_agent.find_links(query, max_results),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"query": "optional string", "max_results": "optional int"},
        output_schema={"count": "int", "links": "list of dicts"},
        error_notes="Raises BrowserControllerError if page is unreachable.",
    ))

    # 7. Download
    registry.register(ToolSpec(
        name="browser_download",
        description="Click an element to trigger and verify a file download into the sandbox.",
        handler=lambda trigger_selector, suggested_name=None: browser_agent.download_file(
            trigger_selector, suggested_name
        ),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=40.0,
        input_schema={"trigger_selector": "string", "suggested_name": "optional string"},
        output_schema={"filename": "string", "path": "string", "size_bytes": "int", "sha256": "string"},
        error_notes="Raises BrowserControllerError on download timeout or blocked file type.",
    ))

    # 8. Interactive session (Human-Assisted Login / MFA)
    registry.register(ToolSpec(
        name="browser_interactive_session",
        description="Launch headed browser window to allow user to complete manual login, MFA, or CAPTCHA.",
        handler=lambda url, instructions, wait_seconds=30: browser_agent.interactive_user_session(
            url, instructions, wait_seconds
        ),
        permission_level=PermissionLevel.SENSITIVE,
        timeout_seconds=120.0,
        input_schema={"url": "string", "instructions": "string", "wait_seconds": "optional int"},
        output_schema={"status": "completed", "final_url": "string"},
        error_notes="Requires human confirmation before launching.",
    ))

    # 9. Close
    registry.register(ToolSpec(
        name="browser_close",
        description="Close active browser session and release memory.",
        handler=lambda: browser_agent.controller.stop() or {"status": "closed"},
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={},
        output_schema={"status": "string"},
        error_notes="Cannot fail.",
    ))

    return browser_agent
