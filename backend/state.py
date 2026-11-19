"""NOVA Backend Application State & Service Container."""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from local_agent.config import load_config
from local_agent.engine.nova_engine import NovaEngine
from local_agent.memory.manager import MemoryManager
from local_agent.tasks.planner import TaskPlanner
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.registry import ToolRegistry
from local_agent.tasks.builtin_tools import register_builtin_tools, register_safe_tools
from local_agent.tasks.voice_tools import register_voice_tools
from local_agent.tasks.memory_tools import register_memory_tools
from local_agent.voice.controller import VoiceController
from local_agent.system.monitor import SystemMonitor
from local_agent.browser.downloads import DownloadManager
from backend.auth import TokenManager, PasswordHasher, RateLimiter, AuditLogger, _get_server_secret
from backend.remote import DeviceManager
from backend.ws_manager import ws_hub

logger = logging.getLogger("nova.backend.state")


class AppState:
    """Singleton container managing all NOVA subsystems for the FastAPI server."""

    def __init__(self):
        self.config = load_config()
        self.data_dir = self.config.data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        # 1. Initialize Memory Manager
        db_path = os.path.join(self.data_dir, "nova_memory.db")
        self.memory_manager = MemoryManager(db_path=db_path)

        # 2. Initialize NovaEngine (AI Brain)
        self.engine = NovaEngine(
            config=self.config.llm,
            data_dir=self.data_dir,
            compact_prompt=True,
            memory_manager=self.memory_manager,
        )

        # 3. Initialize Tool Registry and register tools
        self.tool_registry = ToolRegistry()
        register_safe_tools(self.tool_registry)
        register_voice_tools(self.tool_registry)
        register_memory_tools(self.tool_registry)

        # 4. Initialize Task Planner & Orchestrator
        self.planner = TaskPlanner(
            provider=self.engine.provider,
            registry=self.tool_registry,
            memory_manager=self.memory_manager,
        )
        self.orchestrator = Orchestrator(
            registry=self.tool_registry,
        )

        # 5. Initialize Voice Controller
        self.voice_controller = VoiceController()

        # 6. Initialize System Monitor
        self.system_monitor = SystemMonitor()

        # 7. Initialize Download Manager
        self.download_dir = os.path.join(self.data_dir, "downloads")
        os.makedirs(self.download_dir, exist_ok=True)
        self.download_manager = DownloadManager(download_dir=self.download_dir)

        # 8. Security, Auth, and Device Pairing
        self.server_secret = _get_server_secret(self.data_dir)
        self.token_manager = TokenManager(self.server_secret)
        self.password_hasher = PasswordHasher()
        self.rate_limiter = RateLimiter(max_requests=120, window_seconds=60)
        log_dir = os.path.join(self.data_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.audit_logger = AuditLogger(os.path.join(log_dir, "audit.jsonl"))
        self.device_manager = DeviceManager(self.token_manager, self.audit_logger)
        self.ws_hub = ws_hub

        # User accounts (default local user seeded for pairing and dashboard login)
        self.users: Dict[str, Dict[str, Any]] = {
            "admin": {
                "username": "admin",
                "password_hash": self.password_hasher.hash_password("nova1234"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        }

        # Active Tasks & Approvals in-memory registry
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}

    def get_system_status(self) -> Dict[str, Any]:
        """Collect current system telemetry."""
        summary = self.system_monitor.get_system_summary()
        disks = self.system_monitor.get_disk_usage()
        disk_primary = disks[0] if disks else {"percent": 0.0, "free_gb": 0.0, "total_gb": 0.0}

        running_agents = []
        if self.active_tasks:
            running_agents.append("task_orchestrator")
        if self.voice_controller.wakeword.enabled:
            running_agents.append("voice_wakeword_listener")

        return {
            "cpu_percent": summary["cpu"]["percent"],
            "ram_percent": summary["ram"]["percent_used"],
            "ram_used_gb": summary["ram"]["used_gb"],
            "ram_total_gb": summary["ram"]["total_gb"],
            "disk_percent": disk_primary.get("percent", 0.0),
            "disk_free_gb": disk_primary.get("free_gb", 0.0),
            "active_tasks": len([t for t in self.active_tasks.values() if t.get("status") == "running"]),
            "running_agents": running_agents,
        }

    def request_approval(self, action_type: str, description: str, payload: Dict[str, Any], task_id: Optional[str] = None) -> str:
        """Register a pending approval requirement."""
        approval_id = str(uuid.uuid4())
        self.pending_approvals[approval_id] = {
            "id": approval_id,
            "task_id": task_id,
            "action_type": action_type,
            "description": description,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "decision": None,
        }
        return approval_id

    def resolve_approval(self, approval_id: str, approved: bool) -> bool:
        """Resolve a pending user approval."""
        if approval_id not in self.pending_approvals:
            return False
        self.pending_approvals[approval_id]["status"] = "resolved"
        self.pending_approvals[approval_id]["decision"] = approved
        return True


# Global state instance
state = AppState()
