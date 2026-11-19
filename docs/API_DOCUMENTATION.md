# NOVA — API Documentation (v1.0.0)

The NOVA Backend provides a local-first REST and WebSocket API built with **FastAPI**. By default, it binds to `http://127.0.0.1:8000`.

Interactive Swagger UI documentation is available locally at:
👉 `http://127.0.0.1:8000/docs`

---

## 1. Authentication & Session Management

All authenticated endpoints require an `Authorization: Bearer <TOKEN>` header.

### `POST /api/auth/register`
Create a new user account.
- **Request Body**:
  ```json
  {
    "username": "user",
    "password": "StrongPassword123!"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "username": "user",
    "created_at": "2026-11-19T20:00:00Z"
  }
  ```

### `POST /api/auth/login`
Authenticate and obtain an access token.
- **Request Body**:
  ```json
  {
    "username": "admin",
    "password": "nova1234"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 3600
  }
  ```

---

## 2. Conversation & Chat

### `POST /api/chat`
Submit a message to the AI Brain.
- **Headers**: `Authorization: Bearer <TOKEN>`
- **Request Body**:
  ```json
  {
    "message": "Organize my Downloads folder by subject.",
    "conversation_id": "optional-uuid"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "conversation_id": "c-1234",
    "response_type": "plan",
    "content": "I have created an execution plan to organize your Downloads folder.",
    "plan": {
      "task_id": "task-5678",
      "steps": [...]
    }
  }
  ```

### `GET /api/conversations`
List previous conversations.
- **Response** (200 OK): Array of conversation objects.

---

## 3. Task Management & Orchestration

### `GET /api/tasks`
List all queued, active, and completed tasks.

### `GET /api/tasks/{task_id}`
Retrieve detailed status and step execution logs for a task.
- **Response** (200 OK):
  ```json
  {
    "task_id": "task-5678",
    "instruction": "Download this PDF to my laptop",
    "status": "completed",
    "steps": [
      {
        "step_id": 1,
        "tool_name": "browser_download",
        "status": "completed",
        "output": {"filename": "document.pdf", "sha256": "..."}
      }
    ]
  }
  ```

### `POST /api/tasks/{task_id}/cancel`
Cancel an active task (Emergency Stop).

### `POST /api/tasks/{task_id}/approve`
Approve a pending sensitive step waiting in `waiting_for_approval` state.

---

## 4. Device Pairing & Remote Access

### `POST /api/devices/pair/request`
Generate a temporary 6-character pairing code with a 5-minute TTL on the Windows host.
- **Response** (200 OK):
  ```json
  {
    "code": "NOVA-8492",
    "expires_in_seconds": 300
  }
  ```

### `POST /api/devices/pair/confirm`
Pair a remote browser or mobile phone with the host machine using the code.
- **Request Body**:
  ```json
  {
    "code": "NOVA-8492",
    "device_name": "iPhone 15 Pro"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "device_id": "dev-9012",
    "device_name": "iPhone 15 Pro",
    "status": "online",
    "access_token": "eyJhbGciOi..."
  }
  ```

### `POST /api/remote/task`
Dispatch a task instruction from an authorized remote device.
- **Headers**: `Authorization: Bearer <REMOTE_TOKEN>`
- **Request Body**:
  ```json
  {
    "device_id": "local-agent-win11",
    "instruction": "Download https://example.com/spec.pdf to my laptop",
    "auto_execute": false
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "task_id": "task-remote-101",
    "status": "queued",
    "device_id": "local-agent-win11",
    "instruction": "Download https://example.com/spec.pdf to my laptop",
    "dispatched_at": "2026-11-19T20:15:00Z"
  }
  ```

---

## 5. System Status & Telemetry

### `GET /api/system/status`
Returns live system metrics.
- **Response** (200 OK):
  ```json
  {
    "status": "healthy",
    "cpu_percent": 14.2,
    "memory_used_gb": 4.12,
    "memory_total_gb": 8.00,
    "memory_percent": 51.5,
    "disk_free_gb": 182.4,
    "active_tasks": 0,
    "connected_devices": 1
  }
  ```

---

## 6. Real-Time WebSockets

### `WS /ws`
Bi-directional real-time feed for task status updates, agent progress events, and approval prompts.

**Client Messages:**
- Heartbeat: `{"type": "ping"}`

**Server Events:**
- Task update: `{"event": "task_progress", "task_id": "...", "status": "running", "step": 1}`
- Approval requested: `{"event": "approval_required", "task_id": "...", "step": 2, "action": "delete_file"}`
