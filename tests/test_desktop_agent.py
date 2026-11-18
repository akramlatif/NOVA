"""Automated unit and integration tests for Phase 5 Desktop Automation Agent.

Tests are designed to run in a CI/headless environment where possible,
using mocks for real mouse/keyboard/screen operations, while testing
all logic paths: allowlists, security, emergency stop, and orchestrator
integration.
"""

import os
import subprocess
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from local_agent.desktop.controller import DesktopController, DesktopControllerError
from local_agent.desktop.apps import AppManager, AppSpec, AppManagerError
from local_agent.desktop.observer import ScreenObserver
from local_agent.desktop.security import DesktopSecurity, EmergencyStop
from local_agent.tasks.registry import ToolRegistry, PermissionLevel
from local_agent.tasks.desktop_tools import register_desktop_tools
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.schemas import PlanStep, TaskPlan, TaskStatus


# ---------------------------------------------------------------------------
# Application Manager Tests
# ---------------------------------------------------------------------------
class TestAppManager:
    """Verify application allowlisting, launching, and lifecycle."""

    @pytest.fixture
    def manager(self) -> AppManager:
        return AppManager()

    def test_default_apps_in_allowlist(self, manager: AppManager):
        apps = manager.list_apps()
        keys = [a["key"] for a in apps]
        assert "notepad" in keys
        assert "calculator" in keys
        assert "explorer" in keys

    def test_is_approved_accepts_known_apps(self, manager: AppManager):
        assert manager.is_approved("notepad")
        assert manager.is_approved("calculator")
        assert manager.is_approved("NOTEPAD")  # case-insensitive

    def test_is_approved_rejects_unknown_apps(self, manager: AppManager):
        assert not manager.is_approved("malware")
        assert not manager.is_approved("format")
        assert not manager.is_approved("regedit")

    def test_get_app_raises_on_unapproved(self, manager: AppManager):
        with pytest.raises(AppManagerError, match="not in the approved list"):
            manager.get_app("virus.exe")

    def test_register_custom_app(self, manager: AppManager):
        custom = AppSpec(name="Custom Tool", exe_path="custom.exe")
        manager.register_app("custom", custom)
        assert manager.is_approved("custom")
        spec = manager.get_app("custom")
        assert spec.name == "Custom Tool"

    def test_launch_notepad_and_close(self, manager: AppManager):
        """Test real Notepad launch and close — harmless application."""
        result = manager.launch("notepad", wait_seconds=1.5)
        assert result["success"] is True
        assert result["app"] == "Notepad"
        assert result["pid"] > 0
        assert manager.is_running("notepad")

        close_result = manager.close("notepad")
        assert close_result["success"] is True
        # Give OS time to clean up
        time.sleep(0.5)
        assert not manager.is_running("notepad")

    def test_launch_nonexistent_exe_raises(self, manager: AppManager):
        manager.register_app("fake", AppSpec(name="Fake", exe_path="nonexistent_binary_xyz.exe"))
        with pytest.raises(AppManagerError, match="Executable not found"):
            manager.launch("fake")

    def test_terminal_requires_approval(self, manager: AppManager):
        spec = manager.get_app("terminal")
        assert spec.requires_approval is True

    def test_close_all(self, manager: AppManager):
        manager.launch("notepad", wait_seconds=1.0)
        result = manager.close_all()
        assert result["success"] is True
        time.sleep(0.5)
        assert not manager.is_running("notepad")


# ---------------------------------------------------------------------------
# Desktop Controller Tests
# ---------------------------------------------------------------------------
class TestDesktopController:
    """Verify controller primitives: mouse, keyboard, screenshots, emergency stop."""

    @pytest.fixture
    def ctrl(self, tmp_path: Path) -> DesktopController:
        return DesktopController(screenshot_dir=tmp_path / "screenshots")

    def test_screen_size_returns_positive_dimensions(self, ctrl: DesktopController):
        size = ctrl.screen_size()
        assert size["width"] > 0
        assert size["height"] > 0

    def test_mouse_position_returns_coordinates(self, ctrl: DesktopController):
        pos = ctrl.mouse_position()
        assert "x" in pos
        assert "y" in pos
        assert isinstance(pos["x"], int)
        assert isinstance(pos["y"], int)

    def test_take_screenshot(self, ctrl: DesktopController):
        result = ctrl.take_screenshot(filename="test_capture.png")
        assert result["success"] is True
        assert Path(result["path"]).exists()
        assert result["width"] > 0
        assert result["height"] > 0

    def test_out_of_bounds_mouse_move_rejected(self, ctrl: DesktopController):
        with pytest.raises(DesktopControllerError, match="out of screen bounds"):
            ctrl.mouse_move(-100, -100)

    def test_invalid_mouse_button_rejected(self, ctrl: DesktopController):
        with pytest.raises(DesktopControllerError, match="Invalid mouse button"):
            ctrl.mouse_click(button="invalid")

    def test_empty_text_rejected(self, ctrl: DesktopController):
        with pytest.raises(DesktopControllerError, match="Cannot type empty text"):
            ctrl.type_text("")

    def test_empty_hotkey_rejected(self, ctrl: DesktopController):
        with pytest.raises(DesktopControllerError, match="No keys provided"):
            ctrl.hotkey()

    def test_emergency_stop_blocks_actions(self, ctrl: DesktopController):
        ctrl.emergency_stop()
        assert ctrl.is_stopped is True
        with pytest.raises(DesktopControllerError, match="Emergency stop"):
            ctrl.take_screenshot()
        with pytest.raises(DesktopControllerError, match="Emergency stop"):
            ctrl.mouse_move(100, 100)

    def test_emergency_stop_reset_allows_actions(self, ctrl: DesktopController):
        ctrl.emergency_stop()
        ctrl.reset_emergency_stop()
        assert ctrl.is_stopped is False
        # Should work now
        result = ctrl.take_screenshot(filename="after_reset.png")
        assert result["success"] is True

    def test_get_active_window(self, ctrl: DesktopController):
        result = ctrl.get_active_window()
        # May or may not have an active window in test env, but should not crash
        assert "title" in result

    def test_list_windows(self, ctrl: DesktopController):
        windows = ctrl.list_windows()
        assert isinstance(windows, list)
        # In a Windows desktop environment, there should be at least one window
        # but we don't assert count since tests may run headless


# ---------------------------------------------------------------------------
# Screen Observer Tests
# ---------------------------------------------------------------------------
class TestScreenObserver:
    """Verify screenshot-based observation and change detection."""

    @pytest.fixture
    def observer(self, tmp_path: Path) -> ScreenObserver:
        return ScreenObserver(screenshot_dir=tmp_path / "observations")

    def test_capture_creates_file(self, observer: ScreenObserver):
        result = observer.capture(label="test_capture")
        assert Path(result["path"]).exists()
        assert result["width"] > 0
        assert result["height"] > 0
        assert len(result["hash"]) == 32  # MD5 hex digest

    def test_history_records_captures(self, observer: ScreenObserver):
        observer.capture(label="first")
        observer.capture(label="second")
        assert len(observer.history) == 2

    def test_history_capped_at_max(self, observer: ScreenObserver):
        observer.max_screenshots = 3
        for i in range(5):
            observer.capture(label=f"cap_{i}")
        assert len(observer.history) == 3

    def test_verify_window_title_format(self, observer: ScreenObserver):
        result = observer.verify_window_title("NonExistentAppXYZ123")
        assert result["found"] is False
        assert result["confidence"] == "low"
        assert "No window matching" in result["note"]

    def test_request_human_help(self, observer: ScreenObserver):
        result = observer.request_human_help("UI is ambiguous after clicking save")
        assert result["action"] == "request_human_help"
        assert Path(result["screenshot"]).exists()
        assert "NOVA cannot confidently determine" in result["note"]

    def test_cleanup_old_screenshots(self, observer: ScreenObserver):
        for i in range(5):
            observer.capture(label=f"cleanup_{i}")
        result = observer.cleanup_old_screenshots(keep_last=2)
        remaining = list(observer.screenshot_dir.glob("*.png"))
        assert len(remaining) == 2


# ---------------------------------------------------------------------------
# Desktop Security Tests
# ---------------------------------------------------------------------------
class TestDesktopSecurity:
    """Verify security enforcement: sensitive windows, privilege checks, audit."""

    @pytest.fixture
    def security(self, tmp_path: Path) -> DesktopSecurity:
        from local_agent.security.audit import SecurityAuditLogger
        audit = SecurityAuditLogger(tmp_path / "test_desktop_audit.jsonl")
        return DesktopSecurity(audit_logger=audit)

    def test_sensitive_window_patterns(self, security: DesktopSecurity):
        assert security.is_sensitive_window("Windows Security")
        assert security.is_sensitive_window("Sign In - Google Chrome")
        assert security.is_sensitive_window("KeePass - Database")
        assert security.is_sensitive_window("Enter Password")
        assert not security.is_sensitive_window("Notepad")
        assert not security.is_sensitive_window("Calculator")
        assert not security.is_sensitive_window("Visual Studio Code")

    def test_screenshot_blocked_for_sensitive_window(self, security: DesktopSecurity):
        result = security.check_screenshot_safety("Enter Password - Chrome")
        assert result["safe"] is False
        assert "blocked" in result["note"].lower()

    def test_screenshot_allowed_for_safe_window(self, security: DesktopSecurity):
        result = security.check_screenshot_safety("Untitled - Notepad")
        assert result["safe"] is True

    def test_requires_approval_for_sensitive_actions(self, security: DesktopSecurity):
        assert security.requires_approval("launch_terminal")
        assert security.requires_approval("close_all")
        assert not security.requires_approval("mouse_click")

    def test_requires_approval_for_sensitive_window_target(self, security: DesktopSecurity):
        assert security.requires_approval("type_text", target="Login - Chrome")

    def test_audit_logging(self, security: DesktopSecurity):
        security.log_action("test_action", "test_resource", "SAFE", True)
        records = security.audit.read_records()
        assert len(records) == 1
        assert records[0].action == "test_action"

    def test_privilege_check_returns_dict(self, security: DesktopSecurity):
        result = security.verify_standard_user()
        assert "is_admin" in result
        assert "safe" in result


# ---------------------------------------------------------------------------
# Tool Registry Integration Tests
# ---------------------------------------------------------------------------
class TestDesktopToolRegistration:
    """Verify that all desktop tools register correctly into ToolRegistry."""

    def test_all_tools_registered(self):
        registry = ToolRegistry()
        components = register_desktop_tools(registry)
        expected_tools = [
            "desktop_launch_app",
            "desktop_close_app",
            "desktop_list_apps",
            "desktop_mouse_click",
            "desktop_mouse_move",
            "desktop_type_text",
            "desktop_press_key",
            "desktop_hotkey",
            "desktop_screenshot",
            "desktop_active_window",
            "desktop_list_windows",
            "desktop_focus_window",
            "desktop_verify_window",
            "desktop_observe_change",
            "desktop_request_help",
            "desktop_emergency_stop",
            "desktop_screen_size",
        ]
        for tool_name in expected_tools:
            assert registry.has(tool_name), f"Missing tool: {tool_name}"
        assert "controller" in components
        assert "app_manager" in components
        assert "observer" in components
        assert "security" in components

    def test_list_apps_via_registry(self):
        registry = ToolRegistry()
        register_desktop_tools(registry)
        tool = registry.get("desktop_list_apps")
        result = tool.handler()
        assert isinstance(result, list)
        keys = [a["key"] for a in result]
        assert "notepad" in keys


# ---------------------------------------------------------------------------
# Orchestrator Integration Tests
# ---------------------------------------------------------------------------
class TestOrchestratorDesktopIntegration:
    """Verify that the Agent Orchestrator plans and executes desktop tasks."""

    def test_orchestrator_launch_verify_close(self):
        """Multi-step: launch Notepad, verify window, close."""
        registry = ToolRegistry()
        components = register_desktop_tools(registry)

        orch = Orchestrator(registry)
        plan = TaskPlan(
            task_id="desktop-task-1",
            user_request="Open Notepad, verify it opened, then close it",
            intent_summary="Application lifecycle test",
            expected_result="Notepad opens and closes cleanly",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Launch Notepad",
                    tool_name="desktop_launch_app",
                    parameters={"app_key": "notepad"},
                ),
                PlanStep(
                    step_id=2,
                    description="Verify Notepad is visible",
                    tool_name="desktop_verify_window",
                    parameters={"expected_title": "Notepad"},
                ),
                PlanStep(
                    step_id=3,
                    description="Close Notepad",
                    tool_name="desktop_close_app",
                    parameters={"app_key": "notepad"},
                ),
            ],
            requires_approval=False,
        )

        orch.submit(plan)
        result = orch.run(plan.task_id)

        assert result.status == TaskStatus.COMPLETED
        assert result.verification is not None
        assert result.verification["all_steps_completed"] is True
        assert result.verification["completed_step_count"] == 3

    def test_orchestrator_screenshot_pipeline(self):
        """Multi-step: take screenshot, get screen size."""
        registry = ToolRegistry()
        register_desktop_tools(registry)

        orch = Orchestrator(registry)
        plan = TaskPlan(
            task_id="desktop-screenshot-task",
            user_request="Take a screenshot and report screen size",
            intent_summary="Screen observation",
            expected_result="Screenshot captured and screen size reported",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Get screen dimensions",
                    tool_name="desktop_screen_size",
                    parameters={},
                ),
                PlanStep(
                    step_id=2,
                    description="Take screenshot",
                    tool_name="desktop_screenshot",
                    parameters={"filename": "orchestrator_test.png"},
                ),
            ],
            requires_approval=False,
        )

        orch.submit(plan)
        result = orch.run(plan.task_id)

        assert result.status == TaskStatus.COMPLETED
        assert result.verification["completed_step_count"] == 2
