"""Automated unit and integration tests for Phase 6 File and System Management Agent."""

import csv
from pathlib import Path
import pytest

from local_agent.security.paths import PathSandbox, PathTraversalError, AccessDeniedError
from local_agent.security.terminal import TerminalAllowlist, BlockedCommandError
from local_agent.system.files import FileManager, FileOperationError
from local_agent.system.documents import DocumentProcessor, DocumentError
from local_agent.system.organizer import DownloadOrganizer
from local_agent.system.monitor import SystemMonitor
from local_agent.system.terminal import ControlledTerminal, TerminalExecutionError
from local_agent.tasks.registry import ToolRegistry, PermissionLevel
from local_agent.tasks.system_tools import register_system_management_tools
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.schemas import PlanStep, TaskPlan, TaskStatus


# ---------------------------------------------------------------------------
# File Operations Tests
# ---------------------------------------------------------------------------
class TestFileManager:
    """Verify secure filesystem operations, sandboxing, and duplicate detection."""

    @pytest.fixture
    def setup_fm(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        fm = FileManager(sandbox)
        return fm, sandbox, tmp_path

    def test_create_folder(self, setup_fm):
        fm, _, root = setup_fm
        res = fm.create_folder("docs/notes")
        assert res["created"] is True
        assert (root / "docs" / "notes").is_dir()

    def test_write_and_read_file(self, setup_fm):
        fm, _, root = setup_fm
        res = fm.write_file("hello.txt", "Hello NOVA!")
        assert res["success"] is True

        read_res = fm.read_file("hello.txt")
        assert read_res["content"] == "Hello NOVA!"
        assert read_res["size_bytes"] == len("Hello NOVA!")

    def test_write_overwrite_protection(self, setup_fm):
        fm, _, root = setup_fm
        fm.write_file("file.txt", "initial")
        with pytest.raises(FileOperationError, match="already exists"):
            fm.write_file("file.txt", "new content", overwrite=False)

        fm.write_file("file.txt", "new content", overwrite=True)
        assert fm.read_file("file.txt")["content"] == "new content"

    def test_copy_file(self, setup_fm):
        fm, _, root = setup_fm
        fm.write_file("source.txt", "copy me")
        fm.copy_file("source.txt", "backup.txt")
        assert (root / "backup.txt").is_file()
        assert (root / "source.txt").is_file()
        assert fm.read_file("backup.txt")["content"] == "copy me"

    def test_move_file(self, setup_fm):
        fm, _, root = setup_fm
        fm.write_file("move_me.txt", "moving")
        fm.create_folder("subfolder")
        fm.move_file("move_me.txt", "subfolder/moved.txt")
        assert not (root / "move_me.txt").exists()
        assert (root / "subfolder" / "moved.txt").is_file()

    def test_rename_file(self, setup_fm):
        fm, _, root = setup_fm
        fm.write_file("old_name.txt", "content")
        res = fm.rename_file("old_name.txt", "new_name.txt")
        assert res["success"] is True
        assert not (root / "old_name.txt").exists()
        assert (root / "new_name.txt").is_file()

    def test_search_files(self, setup_fm):
        fm, _, root = setup_fm
        fm.write_file("report_2026.pdf", "sample pdf content")
        fm.write_file("data.csv", "a,b,c")
        fm.write_file("notes.txt", "text")

        results = fm.search_files(query="report", extensions=[".pdf"])
        assert len(results) == 1
        assert results[0]["name"] == "report_2026.pdf"

    def test_find_duplicates(self, setup_fm):
        fm, _, root = setup_fm
        content = "identical duplicate data bytes for testing"
        fm.write_file("file1.txt", content)
        fm.write_file("file2.txt", content)
        fm.write_file("different.txt", "unique data")

        dups = fm.find_duplicates()
        assert len(dups) == 1
        assert dups[0]["count"] == 2
        assert len(dups[0]["sha256"]) == 64

    def test_delete_file_requires_confirmation(self, setup_fm):
        fm, _, root = setup_fm
        fm.write_file("delete_target.txt", "goodbye")
        with pytest.raises(FileOperationError, match="requires explicit user confirmation"):
            fm.delete_file("delete_target.txt", confirmed=False)

        res = fm.delete_file("delete_target.txt", confirmed=True)
        assert res["deleted"] is True
        assert not (root / "delete_target.txt").exists()

    def test_sandbox_path_traversal_blocked(self, setup_fm):
        fm, _, _ = setup_fm
        with pytest.raises(PathTraversalError):
            fm.read_file("../../secret.txt")

        with pytest.raises(AccessDeniedError):
            fm.read_file(".env")


# ---------------------------------------------------------------------------
# Document Processor Tests
# ---------------------------------------------------------------------------
class TestDocumentProcessor:
    """Verify document readers for TXT, MD, CSV, DOCX, XLSX, and PDF."""

    @pytest.fixture
    def setup_docs(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        docs = DocumentProcessor(sandbox)
        return docs, tmp_path

    def test_read_txt_and_md(self, setup_docs):
        docs, root = setup_docs
        txt_path = root / "sample.txt"
        txt_path.write_text("Plain text content line 1\nline 2", encoding="utf-8")
        txt_res = docs.read_document("sample.txt")
        assert txt_res["format"] == "txt"
        assert "line 2" in txt_res["text"]

        md_path = root / "guide.md"
        md_path.write_text("# Overview\nContent here\n## Section 2", encoding="utf-8")
        md_res = docs.read_document("guide.md")
        assert md_res["format"] == "markdown"
        assert "# Overview" in md_res["headings"]
        assert "## Section 2" in md_res["headings"]

    def test_read_csv(self, setup_docs):
        docs, root = setup_docs
        csv_path = root / "records.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Age", "Role"])
            writer.writerow(["Alice", "28", "Engineer"])
            writer.writerow(["Bob", "32", "Manager"])

        res = docs.read_document("records.csv")
        assert res["format"] == "csv"
        assert res["headers"] == ["Name", "Age", "Role"]
        assert len(res["rows_sample"]) == 2

    def test_read_docx(self, setup_docs):
        docs, root = setup_docs
        import docx
        doc = docx.Document()
        doc.add_heading("NOVA Architecture", level=1)
        doc.add_paragraph("First test paragraph in docx.")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "A1"
        table.cell(0, 1).text = "B1"
        docx_path = root / "test.docx"
        doc.save(str(docx_path))

        res = docs.read_document("test.docx")
        assert res["format"] == "docx"
        assert "First test paragraph" in res["text"]
        assert res["tables_count"] == 1

    def test_read_xlsx(self, setup_docs):
        docs, root = setup_docs
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Summary"
        ws.append(["Product", "Qty", "Price"])
        ws.append(["Widget", 10, 5.5])
        xlsx_path = root / "data.xlsx"
        wb.save(str(xlsx_path))

        res = docs.read_document("data.xlsx")
        assert res["format"] == "xlsx"
        assert res["active_sheet"] == "Summary"
        assert len(res["rows_sample"]) == 2
        assert res["rows_sample"][0] == ["Product", "Qty", "Price"]

    def test_read_pdf(self, setup_docs):
        docs, root = setup_docs
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        pdf_path = root / "blank.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)

        res = docs.read_document("blank.pdf")
        assert res["format"] == "pdf"
        assert res["total_pages"] == 1


# ---------------------------------------------------------------------------
# Download Organizer Tests
# ---------------------------------------------------------------------------
class TestDownloadOrganizer:
    """Verify intelligent organization by type, date, and custom rules."""

    @pytest.fixture
    def setup_organizer(self, tmp_path: Path):
        downloads_dir = tmp_path / "downloads"
        downloads_dir.mkdir()
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        organizer = DownloadOrganizer(sandbox)
        return organizer, downloads_dir

    def test_organize_by_file_type(self, setup_organizer):
        org, d_dir = setup_organizer
        (d_dir / "report.pdf").write_text("pdf")
        (d_dir / "sheet.xlsx").write_text("xlsx")
        (d_dir / "photo.png").write_text("png")
        (d_dir / "script.py").write_text("py")

        # Plan preview
        plan = org.plan_organization(d_dir, strategy="type")
        summary = plan.summary()
        assert summary["total_files_to_move"] == 4
        assert "Documents" in summary["categories"]
        assert "Spreadsheets" in summary["categories"]
        assert "Images" in summary["categories"]
        assert "Code" in summary["categories"]

        # Execution
        res = org.execute_plan(plan)
        assert res["success"] is True
        assert res["moved_count"] == 4
        assert (d_dir / "Documents" / "report.pdf").is_file()
        assert (d_dir / "Spreadsheets" / "sheet.xlsx").is_file()
        assert (d_dir / "Images" / "photo.png").is_file()
        assert (d_dir / "Code" / "script.py").is_file()

    def test_organize_with_custom_rules(self, setup_organizer):
        org, d_dir = setup_organizer
        (d_dir / "assignment_cs101.pdf").write_text("cs")
        (d_dir / "math_homework.docx").write_text("math")

        custom_rules = {
            "ComputerScience": ["cs101"],
            "Mathematics": ["math"],
        }

        plan = org.plan_organization(d_dir, custom_rules=custom_rules)
        res = org.execute_plan(plan)
        assert res["success"] is True
        assert (d_dir / "ComputerScience" / "assignment_cs101.pdf").is_file()
        assert (d_dir / "Mathematics" / "math_homework.docx").is_file()


# ---------------------------------------------------------------------------
# System Monitor Tests
# ---------------------------------------------------------------------------
class TestSystemMonitor:
    """Verify hardware inspection, RAM/CPU/Disk metrics, and process tables."""

    def test_system_summary(self):
        summary = SystemMonitor.get_system_summary()
        assert "cpu" in summary
        assert "ram" in summary
        assert "os" in summary
        assert summary["cpu"]["cores_logical"] > 0
        assert summary["ram"]["total_gb"] > 0
        assert "uptime" in summary

    def test_disk_usage(self):
        disks = SystemMonitor.get_disk_usage()
        assert isinstance(disks, list)
        assert len(disks) > 0
        assert "total_gb" in disks[0]
        assert "free_gb" in disks[0]

    def test_list_processes(self):
        procs = SystemMonitor.list_processes(top_n=5, sort_by="memory")
        assert isinstance(procs, list)
        assert len(procs) > 0
        assert "pid" in procs[0]
        assert "name" in procs[0]

    def test_get_process_info(self):
        import os
        current_pid = os.getpid()
        info = SystemMonitor.get_process_info(current_pid)
        assert info["pid"] == current_pid
        assert "python" in info["name"].lower()


# ---------------------------------------------------------------------------
# Controlled Terminal Tests
# ---------------------------------------------------------------------------
class TestControlledTerminal:
    """Verify command execution safety, allowlist enforcement, and environment scrubbing."""

    def test_allowed_command_executes(self, tmp_path: Path):
        term = ControlledTerminal(working_dir=tmp_path)
        res = term.execute("python --version")
        assert res["success"] is True
        assert "Python" in res["stdout"] or "Python" in res["stderr"]

    def test_blocked_command_raises(self, tmp_path: Path):
        term = ControlledTerminal(working_dir=tmp_path)
        with pytest.raises(BlockedCommandError):
            term.execute("format C:")
        with pytest.raises(BlockedCommandError):
            term.execute("powershell -enc aW52b2tl")
        with pytest.raises(BlockedCommandError):
            term.execute("del /s important.txt")


# ---------------------------------------------------------------------------
# Tool Registry & Orchestrator Integration
# ---------------------------------------------------------------------------
class TestOrchestratorSystemIntegration:
    """Verify that the Agent Orchestrator plans and executes multi-step system tasks."""

    def test_orchestrator_multi_step_file_pipeline(self, tmp_path: Path):
        registry = ToolRegistry()
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        register_system_management_tools(registry, sandbox=sandbox)

        orch = Orchestrator(registry)

        plan = TaskPlan(
            task_id="system-pipeline-1",
            user_request="Create project folder, write report, read it back, and check system status",
            intent_summary="File and system workflow",
            expected_result="Folder created, file written, read, and system metrics checked",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Create project directory",
                    tool_name="file_create_folder",
                    parameters={"folder_path": "project_alpha"},
                ),
                PlanStep(
                    step_id=2,
                    description="Write status file",
                    tool_name="file_write",
                    parameters={
                        "file_path": "project_alpha/status.txt",
                        "content": "Phase 6 system tools verified.",
                    },
                ),
                PlanStep(
                    step_id=3,
                    description="Read back status file",
                    tool_name="file_read",
                    parameters={"file_path": "project_alpha/status.txt"},
                ),
                PlanStep(
                    step_id=4,
                    description="Get system telemetry",
                    tool_name="system_metrics_summary",
                    parameters={},
                ),
            ],
            requires_approval=False,
        )

        orch.submit(plan)
        result = orch.run(plan.task_id)

        assert result.status == TaskStatus.COMPLETED
        assert result.verification["all_steps_completed"] is True
        assert result.verification["completed_step_count"] == 4
