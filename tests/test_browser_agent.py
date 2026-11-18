"""Automated unit and integration tests for Phase 4 Browser Automation Agent."""

import pytest
from pathlib import Path

from local_agent.browser.controller import BrowserController, BrowserControllerError
from local_agent.browser.downloads import DownloadManager, DownloadError
from local_agent.browser.agent import BrowserAgent
from local_agent.tasks.registry import ToolRegistry, PermissionLevel
from local_agent.tasks.browser_tools import register_browser_tools
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.schemas import PlanStep, TaskPlan, TaskStatus


# ---------------------------------------------------------------------------
# Download Manager Tests
# ---------------------------------------------------------------------------
class TestDownloadManager:
    """Verify download sanitization, type allowlists, and verification."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> DownloadManager:
        return DownloadManager(download_dir=tmp_path / "downloads")

    def test_sanitize_filename(self, manager: DownloadManager):
        # Path traversal stripped
        assert manager.sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
        # Windows invalid characters replaced
        assert manager.sanitize_filename('report:2026*final?.pdf') == "report_2026_final_.pdf"

    def test_validate_file_type_allows_documents(self, manager: DownloadManager):
        assert manager.validate_file_type("research_paper.pdf") == ".pdf"
        assert manager.validate_file_type("data.csv") == ".csv"
        assert manager.validate_file_type("archive.zip") == ".zip"

    def test_validate_file_type_blocks_executables(self, manager: DownloadManager):
        blocked = ["malware.exe", "script.bat", "installer.msi", "payload.ps1"]
        for name in blocked:
            with pytest.raises(DownloadError, match="strictly forbidden"):
                manager.validate_file_type(name)

    def test_unique_path_resolution(self, manager: DownloadManager, tmp_path: Path):
        file1 = manager.resolve_unique_path("report.pdf")
        file1.write_text("file 1 content", encoding="utf-8")

        file2 = manager.resolve_unique_path("report.pdf")
        assert file2.name == "report (1).pdf"

    def test_verify_download(self, manager: DownloadManager, tmp_path: Path):
        test_file = manager.download_dir / "sample.txt"
        test_file.write_text("verified download content", encoding="utf-8")

        res = manager.verify_download(test_file)
        assert res["verified"] is True
        assert res["size_bytes"] == len("verified download content")
        assert len(res["sha256"]) == 64


# ---------------------------------------------------------------------------
# Browser Controller & Agent Tests
# ---------------------------------------------------------------------------
class TestBrowserAgent:
    """Verify real Playwright navigation, page interaction, and locators."""

    @pytest.fixture
    def agent(self, tmp_path: Path) -> BrowserAgent:
        temp_dir = tmp_path / "browser_downloads"
        dl_mgr = DownloadManager(download_dir=temp_dir)
        controller = BrowserController(headless=True)
        agent = BrowserAgent(controller=controller, download_manager=dl_mgr)
        yield agent
        agent.controller.stop()

    def test_navigate_and_extract_text(self, agent: BrowserAgent):
        # Test navigation to a local data URL to be 100% network-independent and fast
        html_content = (
            "<html><head><title>NOVA Test Page</title></head>"
            "<body><h1>Welcome to NOVA</h1><p>Automated test paragraph.</p>"
            "<a href='https://example.com/docs'>Documentation Link</a></body></html>"
        )
        data_url = f"data:text/html,{html_content}"
        res = agent.controller.navigate(data_url)
        assert res["title"] == "NOVA Test Page"
        assert res["success"] is True

        extracted = agent.extract_visible_text()
        assert "Welcome to NOVA" in extracted["text"]
        assert "Automated test paragraph." in extracted["text"]

    def test_accessible_locators_fill_and_click(self, agent: BrowserAgent):
        form_html = (
            "<html><body>"
            "<form onsubmit='event.preventDefault(); document.getElementById(\"out\").innerText = \"Submitted: \" + document.getElementById(\"q\").value;'>"
            "<label for='q'>Search Query:</label><input id='q' name='q' type='text'/>"
            "<button type='submit'>Run Search</button>"
            "</form><div id='out'></div></body></html>"
        )
        data_url = f"data:text/html,{form_html}"
        agent.controller.navigate(data_url)

        # Fill input using accessible label
        agent.fill("label=Search Query:", "Playwright Automation")

        # Click using semantic button role
        agent.click("role=button:Run Search")

        extracted = agent.extract_visible_text()
        assert "Submitted: Playwright Automation" in extracted["text"]

    def test_find_links(self, agent: BrowserAgent):
        links_html = (
            "<html><body>"
            "<a href='https://python.org/downloads'>Python Downloads</a>"
            "<a href='https://python.org/doc'>Official Docs</a>"
            "<a href='https://example.com'>Example</a>"
            "</body></html>"
        )
        data_url = f"data:text/html,{links_html}"
        agent.controller.navigate(data_url)

        links = agent.find_links(query="python")
        assert len(links["links"]) == 2
        assert any("Downloads" in l["text"] for l in links["links"])

    def test_ssrf_navigation_blocked(self, agent: BrowserAgent):
        with pytest.raises(Exception, match="forbidden"):
            agent.navigate("http://localhost:8080/admin")

        with pytest.raises(Exception, match="forbidden"):
            agent.navigate("http://127.0.0.1:11434")

    def test_failed_url_navigation(self, agent: BrowserAgent):
        with pytest.raises(Exception):
            agent.navigate("http://127.0.0.1:9999")

    def test_browser_crash_or_restart_recovery(self, agent: BrowserAgent):
        agent.controller.stop()
        assert agent.controller._browser is None
        html_page = "data:text/html,<h1>Recovered</h1>"
        res = agent.controller.navigate(html_page)
        assert res["success"] is True


# ---------------------------------------------------------------------------
# Orchestrator Integration with Browser Agent Tools
# ---------------------------------------------------------------------------
class TestOrchestratorBrowserIntegration:
    """Verify that the Agent Orchestrator plans and executes multi-step browser tasks."""

    def test_orchestrator_multi_step_browser_task(self):
        registry = ToolRegistry()
        controller = BrowserController(headless=True)
        agent = BrowserAgent(controller=controller)
        register_browser_tools(registry, agent=agent)

        orch = Orchestrator(registry)

        # Multi-step task:
        # Step 1: Navigate to a page
        # Step 2: Extract text
        # Step 3: Close browser
        html_page = "data:text/html,<html><head><title>NOVA Demo</title></head><body><h1>Agent Orchestrator Browser Test</h1></body></html>"

        plan = TaskPlan(
            task_id="browser-task-1",
            user_request="Navigate to demo page, extract content, and close browser",
            intent_summary="Web page content retrieval",
            expected_result="Page content extracted successfully",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Navigate to page",
                    tool_name="browser_navigate",
                    parameters={"url": html_page},
                ),
                PlanStep(
                    step_id=2,
                    description="Extract page text",
                    tool_name="browser_extract_text",
                    parameters={"max_chars": 2000},
                ),
                PlanStep(
                    step_id=3,
                    description="Close session",
                    tool_name="browser_close",
                    parameters={},
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

    def test_orchestrator_sensitive_browser_tool_requires_approval(self):
        registry = ToolRegistry()
        controller = BrowserController(headless=True)
        agent = BrowserAgent(controller=controller)
        register_browser_tools(registry, agent=agent)

        orch = Orchestrator(registry)
        plan = TaskPlan(
            task_id="sensitive-browser-task",
            user_request="Perform manual login",
            intent_summary="Authentication",
            expected_result="User logs in",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Manual login prompt",
                    tool_name="browser_interactive_session",
                    parameters={"url": "https://example.com/login", "instructions": "Please login"},
                )
            ],
            requires_approval=True,
        )

        orch.submit(plan)
        res = orch.run(plan.task_id)
        assert res.status == TaskStatus.WAITING_FOR_APPROVAL
        agent.controller.stop()
