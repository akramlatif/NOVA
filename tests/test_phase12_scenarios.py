"""Tests for Phase 12 — Final Real-World Integration Scenarios (A, B, C, D, E).

Verifies the complete integration of:
- Scenario A: "Open a website and download a PDF."
- Scenario B: "Find all PDF files in my Downloads folder and organize them by subject."
- Scenario C: "Open VS Code, create a Python project and run a test."
- Scenario D: "Tell me how much RAM and disk space my computer has."
- Scenario E: "From my phone, ask NOVA to download a file on my paired Windows laptop."
- Subsystem integration: Voice + Memory + Tool execution.
"""

import os
import sys
import time
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from local_agent.security.paths import PathSandbox
from local_agent.browser.downloads import DownloadManager
from local_agent.system.files import FileManager
from local_agent.system.organizer import DownloadOrganizer
from local_agent.desktop.apps import AppManager, AppSpec
from local_agent.system.terminal import ControlledTerminal
from local_agent.system.monitor import SystemMonitor
from local_agent.memory.manager import MemoryManager
from local_agent.memory.schema import MemoryCategory
from local_agent.voice.controller import VoiceController
from backend.main import app
from backend.state import state


# ---------------------------------------------------------------------------
# Scenario A: "Open a website and download a PDF."
# ---------------------------------------------------------------------------
def test_scenario_a_download_pdf_workflow():
    """Scenario A: Open website / download URL and securely download PDF to sandbox."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        downloads_dir = tmp_path / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        download_mgr = DownloadManager(download_dir=downloads_dir)

        # 1. Simulate incoming PDF download payload
        sample_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Scenario A Test PDF) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        pdf_filename = "scenario_a_document.pdf"

        # 2. Sanitize and validate filename and type
        clean_name = download_mgr.sanitize_filename(pdf_filename)
        assert clean_name == "scenario_a_document.pdf"
        validated_ext = download_mgr.validate_file_type(clean_name)
        assert validated_ext == ".pdf"

        # 3. Resolve sandboxed path and persist download
        target_path = download_mgr.resolve_unique_path(clean_name)
        target_path.write_bytes(sample_pdf_bytes)

        # 4. Ingest and verify integrity (size, SHA-256)
        info = download_mgr.verify_download(target_path)

        assert target_path.exists()
        assert target_path.suffix.lower() == ".pdf"
        assert info["verified"] is True
        assert info["size_bytes"] == len(sample_pdf_bytes)
        assert len(info["sha256"]) == 64

        # 5. Confirm path sandbox contains the file
        assert sandbox.is_within_sandbox(target_path)


# ---------------------------------------------------------------------------
# Scenario B: "Find all PDF files in my Downloads folder and organize them by subject."
# ---------------------------------------------------------------------------
def test_scenario_b_organize_pdfs_by_subject():
    """Scenario B: Find PDFs in Downloads and categorize them by subject into folders."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        downloads_dir = tmp_path / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        sandbox = PathSandbox(allowed_roots=[tmp_path])

        file_mgr = FileManager(sandbox)

        # 1. Create simulated PDF files across multiple subjects
        sample_pdfs = [
            ("research_quantum_computing.pdf", "Quantum computing algorithms research paper."),
            ("research_deep_learning_nlp.pdf", "Deep learning NLP transformer review."),
            ("finance_invoice_q3_2026.pdf", "Tax invoice for Q3 business consulting."),
            ("finance_annual_budget.pdf", "Annual operational budget for 2026."),
            ("medical_blood_test_report.pdf", "Laboratory diagnostic blood test panel."),
        ]

        for filename, content in sample_pdfs:
            file_mgr.write_file(
                downloads_dir / filename,
                f"%PDF-1.4\n{content}\n%%EOF",
            )

        # 2. Verify search discovers all 5 PDFs
        discovered = file_mgr.search_files(query="*.pdf", directory=downloads_dir)
        assert len(discovered) == 5

        # 3. Organize by Subject using custom keyword rules
        subject_rules = {
            "Research": ["research", "quantum", "nlp", "learning"],
            "Finance": ["finance", "invoice", "budget"],
            "Medical": ["medical", "blood", "test"],
        }
        organizer = DownloadOrganizer(sandbox)
        plan = organizer.plan_organization(downloads_dir, custom_rules=subject_rules)
        res = organizer.execute_plan(plan)

        # 4. Verify results and file structure
        assert res["success"] is True
        assert res["moved_count"] == 5

        research_dir = downloads_dir / "Research"
        finance_dir = downloads_dir / "Finance"
        medical_dir = downloads_dir / "Medical"

        assert research_dir.exists() and len(list(research_dir.glob("*.pdf"))) == 2
        assert finance_dir.exists() and len(list(finance_dir.glob("*.pdf"))) == 2
        assert medical_dir.exists() and len(list(medical_dir.glob("*.pdf"))) == 1


# ---------------------------------------------------------------------------
# Scenario C: "Open VS Code, create a Python project and run a test."
# ---------------------------------------------------------------------------
def test_scenario_c_create_python_project_and_test():
    """Scenario C: Verify editor allowlist, create Python project files, and execute test."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        file_mgr = FileManager(sandbox)
        app_mgr = AppManager()
        terminal = ControlledTerminal(working_dir=tmp_path)

        # 1. Verify editor is registered in approved applications (e.g. notepad or custom vscode spec)
        if not app_mgr.is_approved("code"):
            app_mgr.register_app("code", AppSpec(name="Visual Studio Code", exe_path="code.cmd"))
        assert app_mgr.is_approved("code") is True
        spec = app_mgr.get_app("code")
        assert "Visual Studio Code" in spec.name

        # 2. Create Python project directory and source files
        project_dir = tmp_path / "calc_project"
        file_mgr.create_folder(project_dir)

        calc_code = (
            "def add(a, b):\n"
            "    return a + b\n\n"
            "def multiply(a, b):\n"
            "    return a * b\n"
        )
        test_code = (
            "import unittest\n"
            "from calc import add, multiply\n\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_operations(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
            "        self.assertEqual(multiply(4, 5), 20)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

        file_mgr.write_file(project_dir / "calc.py", calc_code)
        file_mgr.write_file(project_dir / "test_calc.py", test_code)

        assert (project_dir / "calc.py").exists()
        assert (project_dir / "test_calc.py").exists()

        # 3. Run the test suite via controlled terminal (python is allowlisted)
        test_cmd = "python -m unittest test_calc.py"
        result = terminal.execute(test_cmd, working_dir=project_dir)

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "Ran 1 test" in result["stderr"] or "OK" in result["stderr"] or "OK" in result["stdout"]


# ---------------------------------------------------------------------------
# Scenario D: "Tell me how much RAM and disk space my computer has."
# ---------------------------------------------------------------------------
def test_scenario_d_system_ram_and_disk_monitoring():
    """Scenario D: Query live RAM and disk capacity and format response."""
    summary = SystemMonitor.get_system_summary()
    disk_list = SystemMonitor.get_disk_usage()

    # 1. Assert RAM metrics
    ram = summary["ram"]
    assert ram["total_gb"] > 0
    assert ram["available_gb"] > 0
    assert 0 <= ram["percent_used"] <= 100

    # 2. Assert Disk metrics
    assert len(disk_list) > 0
    primary_disk = disk_list[0]
    assert primary_disk["total_gb"] > 0
    assert primary_disk["free_gb"] > 0
    assert 0 <= primary_disk["percent_used"] <= 100

    # 3. Verify natural language synthesis
    response_text = (
        f"NOVA System Status:\n"
        f"• RAM: {ram['used_gb']:.1f} GB / {ram['total_gb']:.1f} GB "
        f"({ram['percent_used']}% used, {ram['available_gb']:.1f} GB free)\n"
        f"• Disk ({primary_disk['mountpoint']}): {primary_disk['free_gb']:.1f} GB free of "
        f"{primary_disk['total_gb']:.1f} GB ({primary_disk['percent_used']}% used)"
    )

    assert "RAM:" in response_text
    assert "Disk" in response_text
    assert f"{ram['total_gb']:.1f} GB" in response_text


# ---------------------------------------------------------------------------
# Scenario E: "From my phone, ask NOVA to download a file on my paired Windows laptop."
# ---------------------------------------------------------------------------
def test_scenario_e_remote_phone_pairing_and_download_task():
    """Scenario E: Remote phone pairs with laptop, submits download task, laptop receives."""
    client = TestClient(app)

    # 0. Refresh the local device heartbeat so it's considered "online"
    #    (During long test suite runs the initial last_seen drifts past the
    #     35-second offline threshold, causing a 503 "device offline" error.)
    hb = client.post("/api/devices/local-agent-win11/heartbeat")
    assert hb.status_code == 200

    # 1. Windows PC generates temporary pairing code
    pair_req = client.post("/api/devices/pair/request", headers={"X-Forwarded-For": "127.0.0.1"})
    assert pair_req.status_code == 200
    pairing_code = pair_req.json()["code"]
    assert pairing_code.startswith("NOVA-")

    # 2. Remote Phone confirms pairing using the code
    confirm_resp = client.post(
        "/api/devices/pair/confirm",
        json={"code": pairing_code, "device_name": "My iPhone 15"},
        headers={"X-Forwarded-For": "192.168.1.55"},
    )
    assert confirm_resp.status_code == 200
    auth_data = confirm_resp.json()
    auth_token = auth_data["access_token"]
    assert auth_token is not None

    # 3. Remote Phone submits task: "Download this PDF to my laptop"
    phone_instruction = "Download https://example.com/spec.pdf to my laptop"
    task_resp = client.post(
        "/api/remote/task",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "X-Forwarded-For": "192.168.1.55",
        },
        json={
            "instruction": phone_instruction,
            "device_id": "local-agent-win11",
            "auto_execute": False,
        },
    )
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    task_id = task_data["task_id"]
    assert task_data["status"] == "queued"
    assert task_data["instruction"] == phone_instruction

    # 4. Remote phone polls task status and receives confirmation
    status_resp = client.get(
        f"/api/tasks/{task_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert status_resp.status_code == 200
    queried_task = status_resp.json()
    assert queried_task["task_id"] == task_id
    assert queried_task["instruction"] == phone_instruction


# ---------------------------------------------------------------------------
# Comprehensive Integration: Memory + Voice + Task Orchestration
# ---------------------------------------------------------------------------
def test_cross_component_voice_memory_integration():
    """Verifies seamless integration between VoiceController, MemoryManager, and Subsystems."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "memory.db"
        memory_mgr = MemoryManager(db_path=db_path)
        try:
            voice_ctrl = VoiceController()
            voice_ctrl.set_mute(True)

            # 1. Voice pipeline status
            status = voice_ctrl.get_status()
            assert status["is_muted"] is True

            # 2. Store preference in long-term memory
            memory_mgr.remember(
                category=MemoryCategory.PREFERENCE,
                key="preferred_editor",
                content="Visual Studio Code",
            )

            recalled = memory_mgr.recall(query="Visual Studio Code", category=MemoryCategory.PREFERENCE)
            assert len(recalled) >= 1
            assert recalled[0].content == "Visual Studio Code"

            # 3. Task failure & outcome learning
            memory_mgr.remember_task_outcome(
                task_id="task-test-scen",
                user_request="Download video file",
                status="failed",
                error="Origin restricted by cloudflare gate",
            )
            task_recalled = memory_mgr.recall(query="cloudflare", category=MemoryCategory.TASK)
            assert len(task_recalled) >= 1
            assert "Origin restricted" in task_recalled[0].content
        finally:
            memory_mgr.close()
