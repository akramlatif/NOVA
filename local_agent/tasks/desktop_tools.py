"""Desktop Tool Adapters for NOVA's Task Planner and Tool Registry — Phase 5.

Exposes desktop automation actions to the Agent Orchestrator with explicit
permission tiers, timeouts, and error handling.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local_agent.desktop.controller import DesktopController
from local_agent.desktop.apps import AppManager
from local_agent.desktop.observer import ScreenObserver
from local_agent.desktop.security import DesktopSecurity
from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec


def register_desktop_tools(
    registry: ToolRegistry,
    controller: Optional[DesktopController] = None,
    app_manager: Optional[AppManager] = None,
    observer: Optional[ScreenObserver] = None,
    security: Optional[DesktopSecurity] = None,
) -> Dict[str, Any]:
    """Register all Phase 5 Desktop Automation tools into the registry.

    Returns:
        Dict containing all instantiated components for reference.
    """
    ctrl = controller or DesktopController()
    apps = app_manager or AppManager()
    obs = observer or ScreenObserver(screenshot_dir=ctrl.screenshot_dir)
    sec = security or DesktopSecurity()

    # 1. Launch application
    def _launch_app(app_key: str, extra_args: Optional[List[str]] = None) -> Dict[str, Any]:
        spec = apps.get_app(app_key)
        sec.log_action("launch_app", f"app:{spec.name}", "NORMAL")
        return apps.launch(app_key, extra_args)

    registry.register(ToolSpec(
        name="desktop_launch_app",
        description="Launch an approved application from the allowlist.",
        handler=_launch_app,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=10.0,
        input_schema={"app_key": "string (e.g. 'notepad', 'calculator', 'explorer')"},
        output_schema={"app": "string", "pid": "int", "success": "bool"},
        error_notes="Raises AppManagerError if app is not in approved list.",
    ))

    # 2. Close application
    def _close_app(app_key: str, force: bool = False) -> Dict[str, Any]:
        sec.log_action("close_app", f"app:{app_key}", "NORMAL")
        return apps.close(app_key, force)

    registry.register(ToolSpec(
        name="desktop_close_app",
        description="Close an application launched by NOVA.",
        handler=_close_app,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=10.0,
        input_schema={"app_key": "string", "force": "optional bool"},
        output_schema={"success": "bool"},
    ))

    # 3. List approved apps
    registry.register(ToolSpec(
        name="desktop_list_apps",
        description="List all approved applications NOVA can launch.",
        handler=lambda: apps.list_apps(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={},
        output_schema={"apps": "list of dicts"},
    ))

    # 4. Mouse click
    def _mouse_click(
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
    ) -> Dict[str, Any]:
        sec.log_action("mouse_click", f"({x},{y}) {button}", "SAFE")
        return ctrl.mouse_click(x, y, button, clicks)

    registry.register(ToolSpec(
        name="desktop_mouse_click",
        description="Click at screen coordinates or current mouse position.",
        handler=_mouse_click,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={
            "x": "optional int", "y": "optional int",
            "button": "optional string ('left','right','middle')",
            "clicks": "optional int",
        },
        output_schema={"x": "int", "y": "int", "success": "bool"},
    ))

    # 5. Mouse move
    def _mouse_move(x: int, y: int, duration: float = 0.3) -> Dict[str, Any]:
        sec.log_action("mouse_move", f"({x},{y})", "SAFE")
        return ctrl.mouse_move(x, y, duration)

    registry.register(ToolSpec(
        name="desktop_mouse_move",
        description="Move mouse cursor to absolute screen coordinates.",
        handler=_mouse_move,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"x": "int", "y": "int", "duration": "optional float"},
        output_schema={"x": "int", "y": "int", "success": "bool"},
    ))

    # 6. Type text
    def _type_text(text: str, interval: float = 0.03) -> Dict[str, Any]:
        sec.log_action("type_text", f"length:{len(text)}", "SAFE")
        return ctrl.type_text(text, interval)

    registry.register(ToolSpec(
        name="desktop_type_text",
        description="Type text into the currently focused application.",
        handler=_type_text,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"text": "string", "interval": "optional float"},
        output_schema={"length": "int", "success": "bool"},
    ))

    # 7. Press key
    def _press_key(key: str) -> Dict[str, Any]:
        sec.log_action("press_key", f"key:{key}", "SAFE")
        return ctrl.press_key(key)

    registry.register(ToolSpec(
        name="desktop_press_key",
        description="Press a single key (enter, tab, escape, f5, etc.).",
        handler=_press_key,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"key": "string"},
        output_schema={"key": "string", "success": "bool"},
    ))

    # 8. Keyboard shortcut
    def _hotkey(*keys: str) -> Dict[str, Any]:
        sec.log_action("hotkey", f"keys:{'+'.join(keys)}", "SAFE")
        return ctrl.hotkey(*keys)

    registry.register(ToolSpec(
        name="desktop_hotkey",
        description="Press a keyboard shortcut (e.g., ctrl+s, alt+f4, ctrl+c).",
        handler=_hotkey,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"keys": "variadic strings (e.g. 'ctrl', 's')"},
        output_schema={"keys": "list", "success": "bool"},
    ))

    # 9. Screenshot
    def _screenshot(filename: Optional[str] = None) -> Dict[str, Any]:
        active = ctrl.get_active_window()
        title = active.get("title", "")
        safety = sec.check_screenshot_safety(title)
        if not safety["safe"]:
            return safety
        sec.log_action("screenshot", f"window:{title}", "SAFE")
        return ctrl.take_screenshot(filename)

    registry.register(ToolSpec(
        name="desktop_screenshot",
        description="Take a screenshot of the current screen. Blocked if sensitive window.",
        handler=_screenshot,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={"filename": "optional string"},
        output_schema={"path": "string", "width": "int", "height": "int", "success": "bool"},
    ))

    # 10. Get active window
    registry.register(ToolSpec(
        name="desktop_active_window",
        description="Get information about the currently focused window.",
        handler=lambda: ctrl.get_active_window(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={},
        output_schema={"title": "string", "active": "bool"},
    ))

    # 11. List windows
    registry.register(ToolSpec(
        name="desktop_list_windows",
        description="List all visible windows with titles and positions.",
        handler=lambda: ctrl.list_windows(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={},
        output_schema={"windows": "list of dicts"},
    ))

    # 12. Focus / switch window
    def _focus_window(title_substring: str) -> Dict[str, Any]:
        sec.log_action("focus_window", f"title:{title_substring}", "SAFE")
        return ctrl.focus_window(title_substring)

    registry.register(ToolSpec(
        name="desktop_focus_window",
        description="Bring a window to the foreground by partial title match.",
        handler=_focus_window,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"title_substring": "string"},
        output_schema={"title": "string", "success": "bool"},
    ))

    # 13. Verify window opened (visual observation)
    def _verify_window(expected_title: str) -> Dict[str, Any]:
        return obs.verify_window_title(expected_title)

    registry.register(ToolSpec(
        name="desktop_verify_window",
        description="Check if a window with the expected title is visible.",
        handler=_verify_window,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"expected_title": "string"},
        output_schema={"found": "bool", "confidence": "string"},
    ))

    # 14. Observe screen change
    def _observe_change(
        label_before: str = "before",
        label_after: str = "after",
        wait_seconds: float = 1.0,
    ) -> Dict[str, Any]:
        return obs.did_screen_change(label_before, label_after, wait_seconds=wait_seconds)

    registry.register(ToolSpec(
        name="desktop_observe_change",
        description="Capture before/after screenshots to detect if screen state changed.",
        handler=_observe_change,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={
            "label_before": "optional string",
            "label_after": "optional string",
            "wait_seconds": "optional float",
        },
        output_schema={"changed": "bool", "confidence": "string"},
    ))

    # 15. Request human help
    def _request_help(reason: str) -> Dict[str, Any]:
        sec.log_action("request_human_help", reason, "SAFE")
        return obs.request_human_help(reason)

    registry.register(ToolSpec(
        name="desktop_request_help",
        description="Signal that NOVA needs user assistance to verify screen state.",
        handler=_request_help,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={"reason": "string"},
        output_schema={"screenshot": "string", "note": "string"},
    ))

    # 16. Emergency stop
    registry.register(ToolSpec(
        name="desktop_emergency_stop",
        description="Immediately halt all desktop automation actions.",
        handler=lambda: ctrl.emergency_stop(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=2.0,
        input_schema={},
        output_schema={"active": "bool"},
    ))

    # 17. Screen size
    registry.register(ToolSpec(
        name="desktop_screen_size",
        description="Return the screen resolution.",
        handler=lambda: ctrl.screen_size(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=2.0,
        input_schema={},
        output_schema={"width": "int", "height": "int"},
    ))

    return {
        "controller": ctrl,
        "app_manager": apps,
        "observer": obs,
        "security": sec,
    }
