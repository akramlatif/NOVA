"""Integration and unit tests for NOVA FastAPI backend."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.state import state
from local_agent.schemas import NovaResponse, ResponseType, Intent


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["app"] == "NOVA"
    assert "ollama_ready" in data


def test_system_status_endpoint(client):
    res = client.get("/api/system/status")
    assert res.status_code == 200
    data = res.json()
    assert "cpu_percent" in data
    assert "ram_percent" in data
    assert "disk_percent" in data
    assert "active_tasks" in data


def test_conversations_flow(client):
    # 1. Create
    res = client.post("/api/conversations", json={"title": "Test Thread"})
    assert res.status_code == 200
    conv = res.json()
    conv_id = conv["id"]
    assert conv["title"] == "Test Thread"

    # 2. List
    res = client.get("/api/conversations")
    assert res.status_code == 200
    items = res.json()
    assert any(c["id"] == conv_id for c in items)

    # 3. Get Details
    res = client.get(f"/api/conversations/{conv_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == conv_id
    assert "messages" in detail

    # 4. Delete
    res = client.delete(f"/api/conversations/{conv_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"

    # 5. Verify 404 after delete
    res = client.get(f"/api/conversations/{conv_id}")
    assert res.status_code == 404


def test_chat_endpoint_mocked(client):
    mock_resp = NovaResponse(
        response_type=ResponseType.CONVERSATION,
        user_message="Hello NOVA",
        detected_intent=Intent.CHAT,
        requested_action="Hello! I am NOVA, your computer assistant.",
        required_tools=[],
        execution_plan=[],
        requires_confirmation=False,
    )
    with patch.object(state.engine, "chat", return_value=mock_resp):
        res = client.post("/api/chat", json={"message": "Hello NOVA"})
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == "Hello! I am NOVA, your computer assistant."
        assert data["response_type"] == "conversation"
        assert "conversation_id" in data


def test_task_submission_and_retrieval(client):
    # Submit task without auto_execute so it stays in queued state
    res = client.post("/api/tasks", json={"instruction": "Search for documentation", "auto_execute": False})
    assert res.status_code == 200
    task_data = res.json()
    task_id = task_data["task_id"]
    assert task_data["status"] == "queued"

    # List tasks
    res = client.get("/api/tasks")
    assert res.status_code == 200
    tasks = res.json()
    assert any(t["task_id"] == task_id for t in tasks)

    # Get single task
    res = client.get(f"/api/tasks/{task_id}")
    assert res.status_code == 200
    assert res.json()["task_id"] == task_id

    # Cancel task
    res = client.post(f"/api/tasks/{task_id}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_approvals_flow(client):
    # Register approval
    app_id = state.request_approval(
        action_type="delete_file",
        description="User requested deletion of old cache",
        payload={"path": "C:/temp/cache.tmp"},
    )

    # List approvals
    res = client.get("/api/approvals")
    assert res.status_code == 200
    approvals = res.json()
    assert any(a["id"] == app_id for a in approvals)

    # Approve
    res = client.post(f"/api/approvals/{app_id}/decision", json={"approved": True})
    assert res.status_code == 200
    assert res.json()["decision"] is True

    # Resolved approval is removed from pending
    res = client.get("/api/approvals")
    assert not any(a["id"] == app_id for a in res.json())


def test_memory_and_preferences_endpoints(client):
    # Memory add
    res = client.post("/api/memory", json={"key": "fav_editor", "content": "VS Code", "category": "preference"})
    assert res.status_code == 200

    # Memory get
    res = client.get("/api/memory?query=VS Code")
    assert res.status_code == 200
    mems = res.json()
    assert any(m["key"] == "fav_editor" for m in mems)

    # Memory forget
    res = client.delete("/api/memory/fav_editor")
    assert res.status_code == 200

    # Preference set & get
    res = client.post("/api/preferences", json={"category": "ui", "key": "theme", "value": "dark"})
    assert res.status_code == 200
    assert res.json()["status"] == "saved"

    res = client.get("/api/preferences?category=ui")
    assert res.status_code == 200
    prefs = res.json()
    assert any(p["key"] == "theme" and p["value"] == "dark" for p in prefs)


def test_voice_endpoints(client):
    # Status
    res = client.get("/api/voice/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_listening" in data
    assert "speech_rate" in data

    # Speak (mocked)
    with patch.object(state.voice_controller, "speak", return_value=True):
        res = client.post("/api/voice/speak", json={"text": "Test speech synthesis"})
        assert res.status_code == 200
        assert res.json()["success"] is True

    # Wake word toggle without consent fails
    res = client.post("/api/voice/wakeword", json={"enabled": True, "consent": False})
    assert res.status_code == 400


def test_settings_endpoints(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    settings = res.json()
    assert "ollama_url" in settings
    assert "model_name" in settings

    # Update settings
    res = client.post("/api/settings", json={"memory_enabled": True})
    assert res.status_code == 200
    assert res.json()["status"] == "updated"
