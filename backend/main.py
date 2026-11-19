"""FastAPI Server for NOVA — Localhost only.

Provides REST and WebSocket endpoints for NOVA's React & Tauri desktop application.
"""

import os
import uuid
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models import (
    HealthResponse,
    SystemStatusResponse,
    ChatRequest,
    ChatResponse,
    CreateConversationRequest,
    ConversationSummary,
    TaskSubmitRequest,
    TaskStatusResponse,
    ApprovalItem,
    ApprovalDecisionRequest,
    MemoryEntryRequest,
    PreferenceRequest,
    SpeakRequest,
    ListenRequest,
    WakeWordToggleRequest,
    SettingsResponse,
)
from backend.state import state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nova.backend")

app = FastAPI(
    title="NOVA Local Assistant API",
    description="Localhost-only API for NOVA Desktop and Web UI",
    version="1.0.0",
)

# Strict CORS: only localhost / 127.0.0.1 / Tauri webviews
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "tauri://localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 1. System & Health
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint."""
    ollama_ok = state.engine.is_ready()
    return HealthResponse(
        status="ok",
        app="NOVA",
        version="1.0.0",
        ollama_ready=ollama_ok,
    )


@app.get("/api/system/status", response_model=SystemStatusResponse)
def get_system_status():
    """Fetch real-time CPU, RAM, Disk, and agent activity."""
    return state.get_system_status()


# ---------------------------------------------------------------------------
# 2. Conversations & Chat
# ---------------------------------------------------------------------------

@app.get("/api/conversations", response_model=List[ConversationSummary])
def list_conversations():
    """List all stored conversations with message counts."""
    rows = state.engine.store._conn.execute(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) as msg_count
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        """
    ).fetchall()

    results = []
    for r in rows:
        results.append(
            ConversationSummary(
                id=r["id"],
                title=r["title"] or "Untitled Conversation",
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                message_count=r["msg_count"],
            )
        )
    return results


@app.post("/api/conversations", response_model=ConversationSummary)
def create_conversation(req: CreateConversationRequest):
    """Start a new conversation thread."""
    conv_id = state.engine.store.new_conversation(title=req.title or "New Conversation")
    now = datetime.now(timezone.utc).isoformat()
    return ConversationSummary(
        id=conv_id,
        title=req.title or "New Conversation",
        created_at=now,
        updated_at=now,
        message_count=0,
    )


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    """Get full message history of a conversation."""
    if not state.engine.store.exists(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_row = state.engine.store._conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
        (conv_id,),
    ).fetchone()
    msg_rows = state.engine.store._conn.execute(
        "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (conv_id,),
    ).fetchall()

    messages = [
        {
            "id": str(r["id"]),
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"],
        }
        for r in msg_rows
    ]

    return {
        "id": conv_row["id"],
        "title": conv_row["title"],
        "created_at": conv_row["created_at"],
        "updated_at": conv_row["updated_at"],
        "messages": messages,
    }


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a conversation."""
    if not state.engine.store.exists(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    state.engine.store.delete_conversation(conv_id)
    return {"status": "deleted", "id": conv_id}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a user message to NOVA's AI engine."""
    conv_id = req.conversation_id
    if not conv_id or not state.engine.store.exists(conv_id):
        conv_id = state.engine.store.new_conversation(
            title=req.message[:30] + ("..." if len(req.message) > 30 else "")
        )

    # Engine chat execution with persistent memory integration
    nova_resp = state.engine.chat(conversation_id=conv_id, user_message=req.message)
    spoken = False

    msg_text = nova_resp.requested_action or (
        nova_resp.execution_plan[0] if nova_resp.execution_plan else "Message received."
    )

    if req.speak_response and msg_text:
        spoken = state.voice_controller.speak(msg_text)

    return ChatResponse(
        conversation_id=conv_id,
        message=msg_text,
        response_type=nova_resp.response_type.value if hasattr(nova_resp.response_type, "value") else str(nova_resp.response_type),
        detected_intent=nova_resp.detected_intent.value if hasattr(nova_resp.detected_intent, "value") else str(nova_resp.detected_intent),
        required_tools=nova_resp.required_tools,
        execution_plan=nova_resp.execution_plan,
        requires_confirmation=nova_resp.requires_confirmation,
        spoken=spoken,
    )


# ---------------------------------------------------------------------------
# 3. Tasks & Orchestration
# ---------------------------------------------------------------------------

def _run_task_background(task_id: str, instruction: str):
    """Background worker executing task orchestrator."""
    state.active_tasks[task_id]["status"] = "planning"
    try:
        plan = state.planner.plan(instruction)
        state.active_tasks[task_id]["steps"] = [
            {"index": s.index, "action": s.action, "params": s.params, "description": s.description, "status": "pending"}
            for s in plan.steps
        ]
        state.active_tasks[task_id]["total_steps"] = len(plan.steps)
        state.active_tasks[task_id]["status"] = "running"

        result = state.orchestrator.execute_plan(plan)
        state.active_tasks[task_id]["status"] = "completed" if result.success else "failed"
        state.active_tasks[task_id]["result"] = result.summary
        state.active_tasks[task_id]["error"] = result.error if not result.success else None
    except Exception as e:
        logger.exception("Task execution error")
        state.active_tasks[task_id]["status"] = "failed"
        state.active_tasks[task_id]["error"] = str(e)


@app.post("/api/tasks", response_model=TaskStatusResponse)
def submit_task(req: TaskSubmitRequest, bg: BackgroundTasks):
    """Submit a complex goal for task planning and execution."""
    task_id = str(uuid.uuid4())
    state.active_tasks[task_id] = {
        "task_id": task_id,
        "instruction": req.instruction,
        "status": "queued",
        "current_step": 0,
        "total_steps": 0,
        "steps": [],
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if req.auto_execute:
        bg.add_task(_run_task_background, task_id, req.instruction)

    return TaskStatusResponse(
        task_id=task_id,
        instruction=req.instruction,
        status="queued",
        current_step=0,
        total_steps=0,
    )


@app.get("/api/tasks", response_model=List[TaskStatusResponse])
def list_tasks():
    """List recent tasks."""
    return [
        TaskStatusResponse(
            task_id=t["task_id"],
            instruction=t["instruction"],
            status=t["status"],
            current_step=t["current_step"],
            total_steps=t["total_steps"],
            steps=t.get("steps", []),
            result=t.get("result"),
            error=t.get("error"),
        )
        for t in reversed(list(state.active_tasks.values()))
    ]


@app.get("/api/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str):
    """Fetch status and steps for a specific task."""
    if task_id not in state.active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    t = state.active_tasks[task_id]
    return TaskStatusResponse(
        task_id=t["task_id"],
        instruction=t["instruction"],
        status=t["status"],
        current_step=t["current_step"],
        total_steps=t["total_steps"],
        steps=t.get("steps", []),
        result=t.get("result"),
        error=t.get("error"),
    )


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    """Cancel an ongoing task."""
    if task_id not in state.active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    state.active_tasks[task_id]["status"] = "cancelled"
    return {"status": "cancelled", "task_id": task_id}


# ---------------------------------------------------------------------------
# 4. Approvals (Human-in-the-loop)
# ---------------------------------------------------------------------------

@app.get("/api/approvals", response_model=List[ApprovalItem])
def list_pending_approvals():
    """List all actions awaiting human approval."""
    return [
        ApprovalItem(
            id=a["id"],
            task_id=a.get("task_id"),
            action_type=a["action_type"],
            description=a["description"],
            payload=a.get("payload", {}),
            created_at=a["created_at"],
        )
        for a in state.pending_approvals.values()
        if a.get("status") == "pending"
    ]


@app.post("/api/approvals/{approval_id}/decision")
def submit_approval_decision(approval_id: str, req: ApprovalDecisionRequest):
    """Approve or reject a pending security/automation action."""
    if approval_id not in state.pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found")
    resolved = state.resolve_approval(approval_id, req.approved)
    return {"approval_id": approval_id, "resolved": resolved, "decision": req.approved}


# ---------------------------------------------------------------------------
# 5. Memory & Preferences
# ---------------------------------------------------------------------------

@app.get("/api/memory")
def get_memories(query: Optional[str] = None, category: Optional[str] = None):
    """Search or list memories."""
    if query:
        memories = state.memory_manager.recall(query, category=category)
    else:
        memories = state.memory_manager.inspect_memories(category=category)
    return memories


@app.post("/api/memory")
def add_memory(req: MemoryEntryRequest):
    """Explicitly store a new memory."""
    success = state.memory_manager.remember(
        key=req.key,
        content=req.content,
        category=req.category,
        confidence=req.confidence,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Memory rejected (possibly blocked by privacy scrubber)")
    return {"status": "stored", "key": req.key}


@app.delete("/api/memory/{key}")
def delete_memory(key: str, category: str = "preference"):
    """Forget a specific memory key."""
    deleted = state.memory_manager.forget_key(category=category, key=key)
    return {"status": "deleted" if deleted else "not_found", "key": key}


@app.get("/api/preferences")
def get_preferences(category: Optional[str] = None):
    """Retrieve saved preferences."""
    prefs = state.memory_manager.list_preferences(category=category)
    return [{"key": k, "value": v} for k, v in prefs.items()]


@app.post("/api/preferences")
def set_preference(req: PreferenceRequest):
    """Set a user preference."""
    state.memory_manager.set_preference(
        key=req.key,
        value=req.value,
        category=req.category,
    )
    return {"status": "saved", "key": req.key, "value": req.value}


# ---------------------------------------------------------------------------
# 6. Voice Controls
# ---------------------------------------------------------------------------

@app.get("/api/voice/status")
def voice_status():
    """Retrieve speech recognition and TTS engine status."""
    return state.voice_controller.get_status()


@app.post("/api/voice/speak")
def voice_speak(req: SpeakRequest):
    """Speak text aloud using SAPI5."""
    if req.rate:
        state.voice_controller.tts.set_rate(req.rate)
    if req.voice_index is not None:
        state.voice_controller.tts.set_voice(req.voice_index)
    success = state.voice_controller.speak(req.text)
    return {"success": success, "text": req.text}


@app.post("/api/voice/listen")
def voice_listen(req: ListenRequest):
    """Listen for speech from microphone."""
    text = state.voice_controller.listen(duration=req.duration, adjust_noise=req.adjust_noise)
    return {"transcript": text, "has_text": bool(text.strip())}


@app.post("/api/voice/wakeword")
def toggle_wakeword(req: WakeWordToggleRequest):
    """Enable or disable wake-word listening with explicit consent."""
    if req.enabled:
        try:
            state.voice_controller.enable_wake_word(consent=req.consent)
            return {"status": "enabled", "listening": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        state.voice_controller.disable_wake_word()
        return {"status": "disabled", "listening": False}


# ---------------------------------------------------------------------------
# 7. Downloads & Settings
# ---------------------------------------------------------------------------

@app.get("/api/downloads")
def list_downloads():
    """List completed or active downloads."""
    return state.download_manager.list_downloads()


@app.get("/api/settings", response_model=SettingsResponse)
def get_settings():
    """Retrieve assistant settings."""
    return SettingsResponse(
        ollama_url=str(state.config.llm.host),
        model_name=state.config.llm.model_name,
        data_dir=str(state.data_dir),
        download_dir=str(state.download_dir),
        voice_enabled=True,
        memory_enabled=state.memory_manager.enabled,
        auto_execute_tasks=True,
    )


@app.post("/api/settings")
def update_settings(req: Dict[str, Any]):
    """Update runtime settings."""
    if "memory_enabled" in req:
        if req["memory_enabled"]:
            state.memory_manager.enable()
        else:
            state.memory_manager.disable()
    return {"status": "updated", "settings": req}


# ---------------------------------------------------------------------------
# 8. Static Frontend Assets Mount (for Desktop Webview & Local UI)
# ---------------------------------------------------------------------------
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Endpoint not found")
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend index not found")
