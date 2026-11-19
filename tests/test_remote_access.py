"""Tests for Phase 10 — Web Dashboard, Device Pairing, Authentication, and Secure Remote Access."""

import time
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.state import state
from backend.auth import TokenManager, PasswordHasher, RateLimiter, AuditLogger


@pytest.fixture
def client():
    return TestClient(app)


def test_password_hasher():
    hasher = PasswordHasher()
    hashed = hasher.hash_password("SuperSecret123!")
    assert hashed != "SuperSecret123!"
    assert hasher.verify_password("SuperSecret123!", hashed) is True
    assert hasher.verify_password("WrongPassword", hashed) is False


def test_token_manager_expiration():
    mgr = TokenManager(b"test_secret_key_32_bytes_long!!")
    # Valid token
    token = mgr.create_token({"sub": "alice"}, ttl_seconds=10)
    payload = mgr.verify_token(token)
    assert payload is not None
    assert payload["sub"] == "alice"

    # Expired token
    expired_token = mgr.create_token({"sub": "bob"}, ttl_seconds=-5)
    assert mgr.verify_token(expired_token) is None


def test_rate_limiter():
    limiter = RateLimiter(max_requests=3, window_seconds=10)
    client_ip = "192.168.1.100"
    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    # 4th request in window should be blocked
    assert limiter.is_allowed(client_ip) is False


def test_auth_registration_and_login_flow(client):
    username = f"user_{int(time.time())}"
    password = "SecuredPassword2026!"

    # 1. Register
    reg_res = client.post("/api/auth/register", json={"username": username, "password": password})
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["username"] == username
    assert "access_token" in reg_data

    # 2. Login
    login_res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 3. Access protected route with Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == username

    # 4. Access protected route with bad token fails
    fail_res = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert fail_res.status_code == 401


def test_device_pairing_lifecycle(client):
    # 1. Request pairing code from Windows agent
    req_res = client.post("/api/devices/pair/request")
    assert req_res.status_code == 200
    pair_data = req_res.json()
    code = pair_data["code"]
    assert code.startswith("NOVA-")

    # 2. Confirm pairing from remote browser/phone
    confirm_res = client.post("/api/devices/pair/confirm", json={"code": code})
    assert confirm_res.status_code == 200
    confirmed = confirm_res.json()
    assert confirmed["status"] == "online"
    dev_id = confirmed["device_id"]
    token = confirmed["access_token"]
    assert token is not None

    # 3. List devices shows paired device
    list_res = client.get("/api/devices")
    assert list_res.status_code == 200
    devices = list_res.json()
    assert any(d["device_id"] == dev_id for d in devices)

    # 4. Reusing same code fails
    reuse_res = client.post("/api/devices/pair/confirm", json={"code": code})
    assert reuse_res.status_code == 400


def test_device_heartbeat(client):
    dev_id = "local-agent-win11"
    hb_res = client.post(f"/api/devices/{dev_id}/heartbeat")
    assert hb_res.status_code == 200
    assert hb_res.json()["online"] is True


def test_remote_task_dispatch(client):
    # Log in to get auth token
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "nova1234"})
    token = login_res.json()["access_token"]

    # Dispatch remote command (e.g. from phone: "Download report to my laptop")
    task_res = client.post(
        "/api/remote/task",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "device_id": "local-agent-win11",
            "instruction": "Download project documentation PDF to my laptop",
            "auto_execute": False,
        },
    )
    assert task_res.status_code == 200
    data = task_res.json()
    assert data["status"] == "queued"
    assert data["device_id"] == "local-agent-win11"
    assert "task_id" in data


@pytest.mark.anyio
async def test_websocket_hub_broadcasting():
    from unittest.mock import AsyncMock
    from backend.ws_manager import ConnectionManager

    manager = ConnectionManager()
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()

    # 1. Connect
    await manager.connect(mock_ws1, "client-1")
    await manager.connect(mock_ws2, "client-2")
    assert "client-1" in manager.active_connections
    assert "client-2" in manager.active_connections

    # 2. Broadcast
    await manager.broadcast("task_progress", {"task_id": "t-1", "status": "running"})
    assert mock_ws1.send_text.called
    assert mock_ws2.send_text.called

    # 3. Personal message
    mock_ws1.reset_mock()
    mock_ws2.reset_mock()
    sent = await manager.send_personal("client-1", "notification", {"msg": "hello"})
    assert sent is True
    assert mock_ws1.send_text.called
    assert not mock_ws2.send_text.called

    # 4. Disconnect
    manager.disconnect(mock_ws1, "client-1")
    assert "client-1" not in manager.active_connections
