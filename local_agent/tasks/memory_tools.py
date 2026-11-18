"""Memory Management Tool Adapters for NOVA's Task Planner and Tool Registry — Phase 7."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from local_agent.memory.manager import MemoryManager
from local_agent.memory.schema import MemoryCategory
from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec


def register_memory_tools(
    registry: ToolRegistry,
    manager: Optional[MemoryManager] = None,
) -> MemoryManager:
    """Register all Phase 7 Persistent Memory tools into the registry."""
    mem = manager or MemoryManager()

    # 1. Store memory
    def _remember(key: str, content: str, category: str = "fact", ttl_seconds: Optional[int] = None):
        mem_id = mem.remember(key, content, category=category, ttl_seconds=ttl_seconds)
        return {"action": "remember", "key": key, "category": category, "id": mem_id, "success": mem_id is not None}

    registry.register(ToolSpec(
        name="memory_remember",
        description="Store a persistent fact, project detail, or context into long-term memory.",
        handler=_remember,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=5.0,
        input_schema={"key": "string", "content": "string", "category": "optional string", "ttl_seconds": "optional int"},
        output_schema={"key": "string", "id": "int", "success": "bool"},
        error_notes="Raises PrivacyViolationError if content contains API keys or passwords.",
    ))

    # 2. Recall memory
    def _recall(query: str, category: Optional[str] = None, limit: int = 5):
        entries = mem.recall(query, category=category, limit=limit)
        return {
            "query": query,
            "count": len(entries),
            "results": [{"key": e.key, "category": e.category.value, "content": e.content} for e in entries],
        }

    registry.register(ToolSpec(
        name="memory_recall",
        description="Search persistent memories by query text or keyword.",
        handler=_recall,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"query": "string", "category": "optional string", "limit": "optional int"},
        output_schema={"count": "int", "results": "list of dicts"},
    ))

    # 3. Inspect memories
    def _inspect(category: Optional[str] = None, limit: int = 50):
        return {"memories": mem.inspect_memories(category=category, limit=limit)}

    registry.register(ToolSpec(
        name="memory_inspect",
        description="List active stored memories for user inspection.",
        handler=_inspect,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"category": "optional string", "limit": "optional int"},
        output_schema={"memories": "list of dicts"},
    ))

    # 4. Forget memory
    def _forget(category: str, key: str):
        success = mem.forget_key(category=category, key=key)
        return {"action": "forget", "category": category, "key": key, "success": success}

    registry.register(ToolSpec(
        name="memory_forget",
        description="Delete a specific persistent memory by category and key.",
        handler=_forget,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=5.0,
        input_schema={"category": "string", "key": "string"},
        output_schema={"action": "string", "success": "bool"},
    ))

    # 5. Set preference
    def _set_pref(key: str, value: str, category: str = "general"):
        mem.set_preference(key, value, category=category)
        return {"action": "set_preference", "key": key, "value": value, "success": True}

    registry.register(ToolSpec(
        name="memory_set_preference",
        description="Set a user preference (e.g., default browser, theme, project path).",
        handler=_set_pref,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=5.0,
        input_schema={"key": "string", "value": "string", "category": "optional string"},
        output_schema={"action": "string", "success": "bool"},
    ))

    # 6. Get preference
    def _get_pref(key: str, category: str = "general"):
        val = mem.get_preference(key, category=category)
        return {"key": key, "value": val, "found": val is not None}

    registry.register(ToolSpec(
        name="memory_get_preference",
        description="Retrieve a user preference by key.",
        handler=_get_pref,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"key": "string", "category": "optional string"},
        output_schema={"key": "string", "value": "string", "found": "bool"},
    ))

    return mem
