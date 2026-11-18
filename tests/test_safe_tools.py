"""Automated unit and integration tests for Phase 4 Safe Core Tools."""

import pytest
from pathlib import Path
import httpx

from local_agent.security import PathSandbox, TerminalAllowlist
from local_agent.tasks.file_tools import (
    file_read,
    file_write,
    file_list,
    file_search,
    file_info,
    FileToolError,
)
from local_agent.tasks.web_tools import (
    web_fetch_text,
    web_search,
    WebToolError,
)
from local_agent.tasks.terminal_tools import (
    terminal_run,
    TerminalToolError,
)
from local_agent.tasks.registry import ToolRegistry
from local_agent.tasks.builtin_tools import register_safe_tools
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.schemas import PlanStep, TaskPlan, TaskStatus


# ---------------------------------------------------------------------------
# Filesystem Tool Tests
# ---------------------------------------------------------------------------
class TestFileTools:
    """Test sandboxed filesystem tools."""

    @pytest.fixture
    def sandbox(self, tmp_path: Path) -> PathSandbox:
        return PathSandbox(allowed_roots=[tmp_path])

    def test_file_write_and_read_roundtrip(self, sandbox: PathSandbox, tmp_path: Path):
        write_res = file_write(sandbox, "test.txt", "Hello NOVA!")
        assert write_res["created"] is True
        assert write_res["bytes_written"] > 0

        read_res = file_read(sandbox, "test.txt")
        assert read_res["content"] == "Hello NOVA!"
        assert read_res["truncated"] is False

    def test_file_write_overwrite_protection(self, sandbox: PathSandbox, tmp_path: Path):
        file_write(sandbox, "doc.txt", "Initial content")

        # Overwrite=False must fail
        with pytest.raises(FileToolError, match="already exists"):
            file_write(sandbox, "doc.txt", "New content", overwrite=False)

        # Overwrite=True succeeds
        res = file_write(sandbox, "doc.txt", "Updated content", overwrite=True)
        assert res["overwritten"] is True
        assert file_read(sandbox, "doc.txt")["content"] == "Updated content"

    def test_file_read_nonexistent_raises(self, sandbox: PathSandbox):
        with pytest.raises(FileToolError, match="File not found"):
            file_read(sandbox, "missing.txt")

    def test_file_read_outside_sandbox_raises(self, sandbox: PathSandbox, tmp_path: Path):
        with pytest.raises(FileToolError, match="Permission denied"):
            file_read(sandbox, "../outside.txt")

    def test_file_list(self, sandbox: PathSandbox, tmp_path: Path):
        file_write(sandbox, "a.txt", "content a")
        file_write(sandbox, "b.py", "content b")
        (tmp_path / "sub").mkdir()
        file_write(sandbox, "sub/c.txt", "content c")

        listing = file_list(sandbox, directory=".", pattern="*.txt", recursive=False)
        names = [e["name"] for e in listing["entries"]]
        assert "a.txt" in names
        assert "b.py" not in names

        recursive_listing = file_list(sandbox, directory=".", pattern="*.txt", recursive=True)
        rec_names = [e["name"] for e in recursive_listing["entries"]]
        assert "a.txt" in rec_names
        assert "c.txt" in rec_names

    def test_file_search_by_name_and_content(self, sandbox: PathSandbox):
        file_write(sandbox, "notes.txt", "Artificial Intelligence research")
        file_write(sandbox, "code.py", "print('hello world')")

        # Search by filename
        res1 = file_search(sandbox, query="code")
        assert any(m["name"] == "code.py" for m in res1["matches"])

        # Search by content
        res2 = file_search(sandbox, query="Artificial Intelligence")
        assert any(m["name"] == "notes.txt" for m in res2["matches"])

    def test_file_info(self, sandbox: PathSandbox):
        file_write(sandbox, "info_test.txt", "data")
        info = file_info(sandbox, "info_test.txt")
        assert info["exists"] is True
        assert info["is_file"] is True
        assert info["size_bytes"] == 4


# ---------------------------------------------------------------------------
# Web Tool Tests
# ---------------------------------------------------------------------------
class TestWebTools:
    """Test safe web searching and text extraction."""

    def test_ssrf_blocks_localhost_and_private_ips(self):
        with pytest.raises(WebToolError, match="forbidden"):
            web_fetch_text("http://localhost/admin")

        with pytest.raises(WebToolError, match="forbidden"):
            web_fetch_text("http://127.0.0.1:8000/keys")

        with pytest.raises(WebToolError, match="forbidden"):
            web_fetch_text("http://192.168.1.1/router")

        with pytest.raises(WebToolError, match="Unsupported URL scheme"):
            web_fetch_text("file:///etc/passwd")

    def test_web_fetch_text_strips_html_and_scripts(self):
        raw_html = (
            "<html><head><script>alert('xss')</script><style>body{color:red}</style></head>"
            "<body><h1>NOVA Documentation</h1><p>NOVA is a personal AI assistant.</p></body></html>"
        )
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text=raw_html))
        client = httpx.Client(transport=transport)

        res = web_fetch_text("https://example.com/docs", client=client)
        assert "alert('xss')" not in res["text"]
        assert "body{color:red}" not in res["text"]
        assert "NOVA Documentation" in res["text"]
        assert "NOVA is a personal AI assistant." in res["text"]

    def test_web_search_parses_duckduckgo_results(self):
        mock_html = (
            '<div class="results">'
            '<a class="result__url" href="https://example.com/ai">https://example.com/ai</a>'
            '<a class="result__snippet">An overview of artificial intelligence systems.</a>'
            '</div>'
        )
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text=mock_html))
        client = httpx.Client(transport=transport)

        res = web_search("artificial intelligence", max_results=3, client=client)
        assert res["count"] >= 1
        assert "artificial intelligence" in res["results"][0]["snippet"].lower()


# ---------------------------------------------------------------------------
# Terminal Tool Tests
# ---------------------------------------------------------------------------
class TestTerminalTools:
    """Test safe command execution."""

    @pytest.fixture
    def allowlist(self) -> TerminalAllowlist:
        return TerminalAllowlist()

    def test_allowed_command_executes_successfully(self, allowlist: TerminalAllowlist):
        res = terminal_run(allowlist, "python --version")
        assert res["returncode"] == 0
        assert "Python" in res["stdout"] or "Python" in res["stderr"]
        assert res["success"] is True

    def test_unregistered_command_fails_safely(self, allowlist: TerminalAllowlist):
        with pytest.raises(TerminalToolError, match="Permission denied"):
            terminal_run(allowlist, "powershell -enc JABzACAAPQAg...")

    def test_destructive_command_fails_safely(self, allowlist: TerminalAllowlist):
        with pytest.raises(TerminalToolError, match="Permission denied"):
            terminal_run(allowlist, "format C:")


# ---------------------------------------------------------------------------
# Orchestrator Integration with Safe Core Tools
# ---------------------------------------------------------------------------
class TestOrchestratorSafeToolsIntegration:
    """Test that the Phase 3 Orchestrator seamlessly executes Phase 4 tools."""

    def test_orchestrator_multi_step_file_pipeline(self, tmp_path: Path):
        registry = ToolRegistry()
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        allowlist = TerminalAllowlist()
        register_safe_tools(registry, sandbox=sandbox, allowlist=allowlist)

        orch = Orchestrator(registry)

        plan = TaskPlan(
            task_id="phase4-test-1",
            user_request="Create a summary file and verify its contents",
            intent_summary="Write and read back summary",
            expected_result="File exists with summary text",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Write summary text",
                    tool_name="file_write",
                    parameters={"path": "summary.txt", "content": "Phase 4 tools active"},
                ),
                PlanStep(
                    step_id=2,
                    description="Read back summary text",
                    tool_name="file_read",
                    parameters={"path": "summary.txt"},
                ),
                PlanStep(
                    step_id=3,
                    description="Check Python runtime version",
                    tool_name="terminal_run",
                    parameters={"command": "python --version"},
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

        # Verify the file actually was written to disk inside the sandbox
        assert (tmp_path / "summary.txt").read_text(encoding="utf-8") == "Phase 4 tools active"
