"""Pydantic schemas for the NOVA FastAPI backend."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "NOVA"
    version: str = "1.0.0"
    ollama_ready: bool = False


class SystemStatusResponse(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    disk_percent: float
    disk_free_gb: float
    active_tasks: int
    running_agents: List[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    speak_response: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    response_type: str = "conversation"
    detected_intent: str = "unknown"
    required_tools: List[str] = Field(default_factory=list)
    execution_plan: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    spoken: bool = False


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageModel(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class TaskSubmitRequest(BaseModel):
    instruction: str
    conversation_id: Optional[str] = None
    auto_execute: bool = True


class TaskStatusResponse(BaseModel):
    task_id: str
    instruction: str
    status: str
    current_step: int
    total_steps: int
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None


class ApprovalItem(BaseModel):
    id: str
    task_id: Optional[str] = None
    action_type: str
    description: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None


class MemoryEntryRequest(BaseModel):
    category: str = "general"
    key: str
    content: str
    confidence: float = 1.0


class PreferenceRequest(BaseModel):
    category: str = "general"
    key: str
    value: str


class SpeakRequest(BaseModel):
    text: str
    rate: Optional[int] = None
    voice_index: Optional[int] = None


class ListenRequest(BaseModel):
    duration: float = 5.0
    adjust_noise: bool = False


class WakeWordToggleRequest(BaseModel):
    enabled: bool
    consent: bool = False


class SettingsResponse(BaseModel):
    ollama_url: str
    model_name: str
    data_dir: str
    download_dir: str
    voice_enabled: bool
    memory_enabled: bool
    auto_execute_tasks: bool


# ---------------------------------------------------------------------------
# Phase 10 — Remote Access & Pairing Models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    username: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class PairingCodeResponse(BaseModel):
    code: str
    expires_in_seconds: int = 300
    device_name: str


class PairConfirmRequest(BaseModel):
    code: str


class PairConfirmResponse(BaseModel):
    device_id: str
    device_name: str
    status: str
    access_token: str


class DeviceModel(BaseModel):
    device_id: str
    device_name: str
    os: str
    status: str
    last_seen_seconds_ago: int
    capabilities: List[str] = Field(default_factory=list)


class RemoteTaskRequest(BaseModel):
    device_id: Optional[str] = "local-agent-win11"
    instruction: str
    auto_execute: bool = True


class RemoteTaskResponse(BaseModel):
    task_id: str
    device_id: str
    instruction: str
    status: str
    dispatched_at: str
