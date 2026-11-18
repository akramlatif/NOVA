"""SQLite Persistent Memory Store for NOVA — Phase 7."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from local_agent.memory.schema import (
    SQL_SCHEMA_DDL,
    MemoryCategory,
    MemoryEntry,
    UserPreference,
)

logger = logging.getLogger(__name__)


class MemoryStore:
    """Manages SQLite persistent storage for users, conversations, memories, preferences, and tasks."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database tables and ensure default user exists."""
        with self._conn:
            self._conn.executescript(SQL_SCHEMA_DDL)
            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                """
                INSERT OR IGNORE INTO users (id, username, display_name, created_at, updated_at)
                VALUES ('default_user', 'akramlatif', 'Akram Latif', ?, ?)
                """,
                (now, now),
            )

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()

    # ------------------------------------------------------------------ Memories CRUD
    def save_memory(self, entry: MemoryEntry) -> int:
        """Insert or update a persistent memory entry."""
        now = datetime.now(timezone.utc).isoformat()
        expires_str = entry.expires_at.isoformat() if entry.expires_at else None

        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO memories (user_id, category, key, content, confidence, access_count, last_accessed_at, expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, category, key) DO UPDATE SET
                    content = excluded.content,
                    confidence = excluded.confidence,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                RETURNING id
                """,
                (
                    entry.user_id,
                    entry.category.value if isinstance(entry.category, MemoryCategory) else str(entry.category),
                    entry.key,
                    entry.content,
                    entry.confidence,
                    entry.access_count,
                    entry.last_accessed_at.isoformat() if entry.last_accessed_at else None,
                    expires_str,
                    now,
                    now,
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_memory(self, category: str, key: str, user_id: str = "default_user") -> Optional[MemoryEntry]:
        """Fetch a specific memory by category and key."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """
            SELECT * FROM memories
            WHERE user_id = ? AND category = ? AND key = ?
              AND (expires_at IS NULL OR expires_at > ?)
            """,
            (user_id, category, key, now),
        )
        row = cur.fetchone()
        if not row:
            return None

        # Bump access metrics
        with self._conn:
            self._conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (now, row["id"]),
            )

        entry = self._row_to_memory(row)
        entry.access_count += 1
        entry.last_accessed_at = datetime.fromisoformat(now)
        return entry

    def search_memories(
        self,
        query: str,
        category: Optional[str] = None,
        user_id: str = "default_user",
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Search memories matching keywords in content or key, excluding expired items."""
        now = datetime.now(timezone.utc).isoformat()
        like_query = f"%{query}%"

        params: List[Any] = [user_id, now, like_query, like_query]
        cat_filter = ""
        if category:
            cat_filter = "AND category = ?"
            params.append(category)

        params.append(limit)

        sql = f"""
            SELECT * FROM memories
            WHERE user_id = ?
              AND (expires_at IS NULL OR expires_at > ?)
              AND (content LIKE ? OR key LIKE ?)
              {cat_filter}
            ORDER BY confidence DESC, access_count DESC, updated_at DESC
            LIMIT ?
        """
        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()

        # Update access count for returned items
        if rows:
            ids = [r["id"] for r in rows]
            placeholders = ",".join("?" for _ in ids)
            with self._conn:
                self._conn.execute(
                    f"UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id IN ({placeholders})",
                    [now] + ids,
                )

        return [self._row_to_memory(r) for r in rows]

    def list_memories(
        self,
        category: Optional[str] = None,
        user_id: str = "default_user",
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """List active memories."""
        now = datetime.now(timezone.utc).isoformat()
        params: List[Any] = [user_id, now]
        cat_filter = ""
        if category:
            cat_filter = "AND category = ?"
            params.append(category)

        params.append(limit)

        sql = f"""
            SELECT * FROM memories
            WHERE user_id = ?
              AND (expires_at IS NULL OR expires_at > ?)
              {cat_filter}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        cur = self._conn.execute(sql, params)
        return [self._row_to_memory(r) for r in cur.fetchall()]

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory record by ID."""
        with self._conn:
            cur = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    def delete_memory_by_key(self, category: str, key: str, user_id: str = "default_user") -> bool:
        """Delete a memory record by category and key."""
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM memories WHERE user_id = ? AND category = ? AND key = ?",
                (user_id, category, key),
            )
            return cur.rowcount > 0

    def clear_category(self, category: str, user_id: str = "default_user") -> int:
        """Remove all memories belonging to a category."""
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM memories WHERE user_id = ? AND category = ?",
                (user_id, category),
            )
            return cur.rowcount

    def purge_expired(self) -> int:
        """Delete expired memory entries."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            )
            return cur.rowcount

    # ------------------------------------------------------------------ Preferences
    def set_preference(self, key: str, value: str, category: str = "general", user_id: str = "default_user") -> None:
        """Store or update user preference."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO user_preferences (user_id, category, key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, category, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (user_id, category, key, value, now, now),
            )

    def get_preference(self, key: str, category: str = "general", user_id: str = "default_user") -> Optional[str]:
        """Fetch a specific preference value."""
        cur = self._conn.execute(
            "SELECT value FROM user_preferences WHERE user_id = ? AND category = ? AND key = ?",
            (user_id, category, key),
        )
        row = cur.fetchone()
        return row["value"] if row else None

    def list_preferences(self, category: Optional[str] = None, user_id: str = "default_user") -> Dict[str, str]:
        """Return dict of key-value preferences."""
        params: List[Any] = [user_id]
        cat_filter = ""
        if category:
            cat_filter = "AND category = ?"
            params.append(category)

        sql = f"SELECT key, value FROM user_preferences WHERE user_id = ? {cat_filter} ORDER BY key ASC"
        cur = self._conn.execute(sql, params)
        return {r["key"]: r["value"] for r in cur.fetchall()}

    # ------------------------------------------------------------------ Conversations & Messages
    def create_conversation(self, conv_id: str, title: Optional[str] = None, user_id: str = "default_user") -> None:
        """Register a conversation."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, user_id, title or "New Conversation", now, now),
            )

    def add_message(self, conv_id: str, role: str, content: str) -> int:
        """Append a message to a conversation."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                RETURNING id
                """,
                (conv_id, role, content, now),
            )
            # Update conversation timestamp
            self._conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_messages(self, conv_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent conversation messages."""
        cur = self._conn.execute(
            """
            SELECT id, role, content, created_at FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (conv_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------ Tasks & Logs
    def record_task(
        self,
        task_id: str,
        user_request: str,
        intent_summary: Optional[str] = None,
        expected_result: Optional[str] = None,
        status: str = "running",
        user_id: str = "default_user",
    ) -> None:
        """Record the start of a task."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO tasks (id, user_id, user_request, intent_summary, expected_result, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (task_id, user_id, user_request, intent_summary, expected_result, status, now, now),
            )

    def update_task_status(
        self,
        task_id: str,
        status: str,
        summary: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update task outcome."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                UPDATE tasks
                SET status = ?, summary = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, summary, error, now, task_id),
            )

    def add_task_step_log(
        self,
        task_id: str,
        step_id: int,
        tool_name: str,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> int:
        """Record execution log for a specific task step."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO task_execution_logs (task_id, step_id, tool_name, status, output, error, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (task_id, step_id, tool_name, status, output, error, duration_ms, now),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_task_history(self, limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch previous task results and failures."""
        params: List[Any] = []
        status_filter = ""
        if status:
            status_filter = "WHERE status = ?"
            params.append(status)

        params.append(limit)
        sql = f"SELECT * FROM tasks {status_filter} ORDER BY created_at DESC LIMIT ?"
        cur = self._conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------ Internal Helpers
    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> MemoryEntry:
        """Convert a database row into a MemoryEntry object."""
        exp = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
        last_acc = datetime.fromisoformat(row["last_accessed_at"]) if row["last_accessed_at"] else None
        return MemoryEntry(
            id=row["id"],
            user_id=row["user_id"],
            category=MemoryCategory(row["category"]) if row["category"] in MemoryCategory._value2member_map_ else MemoryCategory.FACT,
            key=row["key"],
            content=row["content"],
            confidence=row["confidence"],
            access_count=row["access_count"],
            last_accessed_at=last_acc,
            expires_at=exp,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
