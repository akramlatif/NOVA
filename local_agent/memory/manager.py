"""High-Level Memory Manager for NOVA — Phase 7.

Orchestrates Short-Term, Long-Term, and Task memory with duplicate detection,
relevance retrieval, TTL expiration, privacy validation, and prompt formatting.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from local_agent.memory.privacy import PrivacyScrubber, PrivacyViolationError
from local_agent.memory.schema import MemoryCategory, MemoryEntry
from local_agent.memory.store import MemoryStore


class MemoryManager:
    """Unified memory manager supporting short-term, long-term, and task memory."""

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        db_path: Optional[Path | str] = None,
        enabled: bool = True,
    ) -> None:
        if store:
            self.store = store
        elif db_path:
            self.store = MemoryStore(db_path)
        else:
            default_path = Path(__file__).resolve().parents[2] / "data" / "nova_memory.db"
            self.store = MemoryStore(default_path)

        self.enabled = enabled

        # Short-term in-memory state
        self._active_task: Optional[Dict[str, Any]] = None
        self._active_conversation_id: Optional[str] = None

    # ------------------------------------------------------------------ Configuration
    def enable(self) -> None:
        """Enable memory retrieval and storage."""
        self.enabled = True

    def disable(self) -> None:
        """Disable memory retrieval and storage for private sessions."""
        self.enabled = False

    def close(self) -> None:
        """Close the underlying SQLite database connection."""
        if hasattr(self, "store") and self.store:
            self.store.close()

    # ------------------------------------------------------------------ Long-Term Memory (Store & Recall)
    def remember(
        self,
        key: str,
        content: str,
        category: Union[MemoryCategory, str] = MemoryCategory.FACT,
        ttl_seconds: Optional[int] = None,
        confidence: float = 1.0,
    ) -> Optional[int]:
        """Store a verified memory with duplicate checking and privacy validation."""
        if not self.enabled:
            return None

        # 1. Privacy gate: reject API keys, credentials, and passwords
        PrivacyScrubber.validate_memory_content(key, content)

        cat_enum = MemoryCategory(category) if isinstance(category, str) else category

        # 2. Duplicate detection: check if exact memory exists
        existing = self.store.get_memory(category=cat_enum.value, key=key)
        if existing and existing.content.strip() == content.strip():
            # Update access and return existing ID without duplicate insert
            return existing.id

        expires_at = None
        if ttl_seconds is not None and ttl_seconds > 0:
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=ttl_seconds)

        entry = MemoryEntry(
            category=cat_enum,
            key=key,
            content=content,
            confidence=confidence,
            expires_at=expires_at,
        )
        return self.store.save_memory(entry)

    def recall(
        self,
        query: str,
        category: Optional[Union[MemoryCategory, str]] = None,
        limit: int = 5,
    ) -> List[MemoryEntry]:
        """Retrieve relevant memories matching query text."""
        if not self.enabled or not query.strip():
            return []

        cat_str = category.value if isinstance(category, MemoryCategory) else category
        return self.store.search_memories(query=query, category=cat_str, limit=limit)

    def get_context_for_prompt(self, user_request: str, limit: int = 5) -> str:
        """Format relevant long-term memories into markdown context for LLM prompt."""
        if not self.enabled:
            return ""

        words = [w.strip() for w in user_request.split() if len(w.strip()) > 3]
        collected: Dict[int, MemoryEntry] = {}

        # Search overall and per significant keyword
        for entry in self.store.search_memories(query=user_request[:50], limit=limit):
            if entry.id is not None:
                collected[entry.id] = entry

        for word in words[:4]:
            if len(collected) >= limit:
                break
            for entry in self.store.search_memories(query=word, limit=3):
                if entry.id is not None and entry.id not in collected:
                    collected[entry.id] = entry

        if not collected:
            # Fallback: include general preferences
            prefs = self.store.list_preferences(limit=5)
            if prefs:
                lines = [f"- [Preference] {k}: {v}" for k, v in prefs.items()]
                return "### User Preferences\n" + "\n".join(lines)
            return ""

        lines = []
        for entry in list(collected.values())[:limit]:
            lines.append(f"- [{entry.category.value.capitalize()}] {entry.key}: {entry.content}")

        return "### Relevant Persistent Memories\n" + "\n".join(lines)

    # ------------------------------------------------------------------ Preferences
    def set_preference(self, key: str, value: str, category: str = "general") -> None:
        """Save a user preference (scrubbing secrets)."""
        if not self.enabled:
            return
        PrivacyScrubber.validate_memory_content(key, value)
        self.store.set_preference(key, value, category=category)

    def get_preference(self, key: str, category: str = "general") -> Optional[str]:
        """Retrieve a user preference value."""
        if not self.enabled:
            return None
        return self.store.get_preference(key, category=category)

    def list_preferences(self, category: Optional[str] = None) -> Dict[str, str]:
        """List all active preferences."""
        if not self.enabled:
            return {}
        return self.store.list_preferences(category=category)

    # ------------------------------------------------------------------ Short-Term Memory (Active Task & Conversation)
    def set_active_conversation(self, conv_id: str) -> None:
        """Set currently active conversation ID."""
        self._active_conversation_id = conv_id

    def get_active_conversation(self) -> Optional[str]:
        return self._active_conversation_id

    def set_active_task(self, task_id: str, request: str, intent: Optional[str] = None) -> None:
        """Register the currently executing active task in short-term memory."""
        self._active_task = {
            "task_id": task_id,
            "request": request,
            "intent": intent,
            "steps": [],
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.store.record_task(task_id, request, intent_summary=intent, status="running")

    def get_active_task(self) -> Optional[Dict[str, Any]]:
        """Get currently running task state."""
        return self._active_task

    def record_step_result(
        self,
        task_id: str,
        step_id: int,
        tool_name: str,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> None:
        """Log a step in both short-term memory and the persistent execution log."""
        if self._active_task and self._active_task.get("task_id") == task_id:
            self._active_task["steps"].append({
                "step_id": step_id,
                "tool": tool_name,
                "status": status,
                "error": error,
            })
        self.store.add_task_step_log(task_id, step_id, tool_name, status, output, error, duration_ms)

    def complete_active_task(self, task_id: str, summary: str, status: str = "completed") -> None:
        """Mark active task finished and clear short-term reference."""
        self.store.update_task_status(task_id, status=status, summary=summary)
        if self._active_task and self._active_task.get("task_id") == task_id:
            self._active_task = None

    # ------------------------------------------------------------------ Task Memory (Historical Recall)
    def remember_task_outcome(
        self,
        task_id: str,
        user_request: str,
        status: str,
        summary: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record task history and save relevant lessons learned."""
        if not self.enabled:
            return

        self.store.record_task(task_id, user_request, status=status)
        self.store.update_task_status(task_id, status=status, summary=summary, error=error)

        # If failed, store a task memory entry to assist future planning
        if status == "failed" and error:
            safe_error = PrivacyScrubber.scrub_text(error)[:200]
            self.remember(
                key=f"task_failure_{task_id[:8]}",
                content=f"Request '{user_request[:60]}' failed: {safe_error}",
                category=MemoryCategory.TASK,
                ttl_seconds=86400 * 7,  # Remember failures for 7 days
            )

    def recall_task_history(self, limit: int = 10, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve historical task records."""
        if not self.enabled:
            return []
        return self.store.get_task_history(limit=limit, status=status)

    # ------------------------------------------------------------------ Inspection & Deletion
    def inspect_memories(self, category: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List active memories for user inspection."""
        entries = self.store.list_memories(category=category, limit=limit)
        return [
            {
                "id": e.id,
                "category": e.category.value,
                "key": e.key,
                "content": e.content,
                "confidence": e.confidence,
                "access_count": e.access_count,
                "expires_at": e.expires_at.isoformat() if e.expires_at else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

    def forget(self, memory_id: int) -> bool:
        """Delete a single memory by ID."""
        return self.store.delete_memory(memory_id)

    def forget_key(self, category: str, key: str) -> bool:
        """Delete a memory by category and key."""
        return self.store.delete_memory_by_key(category=category, key=key)

    def clear_all_in_category(self, category: str) -> int:
        """Purge all memories under a specific category."""
        return self.store.clear_category(category)

    def cleanup_expired(self) -> int:
        """Purge all expired memories across the store."""
        return self.store.purge_expired()
