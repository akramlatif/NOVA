# ==============================================================================
# NOVA — Conversation Store (Phase 2, Task 4)
# ------------------------------------------------------------------------------
# SQLite-backed conversation history. Why SQLite: zero background service
# (master rule: avoid unnecessary services), single file on D:, HDD-friendly.
#
# Responsibilities (and NOTHING else):
#   * create conversations (UUID ids)
#   * append messages
#   * load history (with context limits)
#   * reset/clear
# It does NOT talk to the LLM and does NOT know what the messages mean.
# ==============================================================================

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from local_agent.llm.provider import ChatMessage

# Default context budget for a 3B model: system prompt + ~10 exchanges.
# Tokens are estimated at 4 chars/token — a deliberate, cheap approximation.
DEFAULT_MAX_TURNS = 20        # messages (both roles combined)
DEFAULT_MAX_CONTEXT_CHARS = 16_000


class ConversationStore:
    """Persistent, file-based conversation storage."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------ schema
    def _init_schema(self) -> None:
        """Create tables if missing. Idempotent — safe on every start."""
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id          TEXT PRIMARY KEY,
                    title        TEXT,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role            TEXT NOT NULL CHECK (role IN ('system','user','assistant')),
                    content         TEXT NOT NULL,
                    created_at      TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, id);
                """
            )

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self._conn.close()

    def new_conversation(self, title: Optional[str] = None) -> str:
        """Create a conversation, return its UUID."""
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                (conv_id, title, now, now),
            )
        return conv_id

    def exists(self, conversation_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return row is not None

    def delete_conversation(self, conversation_id: str) -> None:
        """Remove a conversation and its messages entirely."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )

    def reset_conversation(self, conversation_id: str) -> None:
        """Clear messages but keep the conversation shell (same id)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )

    # ------------------------------------------------------------------ messages
    def append_message(self, conversation_id: str, message: ChatMessage) -> None:
        """Store one message. Raises KeyError if the conversation doesn't exist."""
        if not self.exists(conversation_id):
            raise KeyError(f"Unknown conversation: {conversation_id}")
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) "
                "VALUES (?,?,?,?)",
                (conversation_id, message.role, message.content, now),
            )
            self._conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def load_history(
        self,
        conversation_id: str,
        max_turns: int = DEFAULT_MAX_TURNS,
        max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    ) -> List[ChatMessage]:
        """Load recent messages within BOTH context limits.

        Context management strategy (basic, Phase 2): keep the most recent
        messages that fit the turn budget, then trim further from the OLDEST
        side until under the char budget. Early messages are dropped — recent
        context matters most for a small local model.
        """
        if not self.exists(conversation_id):
            raise KeyError(f"Unknown conversation: {conversation_id}")

        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()

        messages = [ChatMessage(role=r["role"], content=r["content"]) for r in rows]

        # Limit 1: most recent N messages
        if len(messages) > max_turns:
            messages = messages[-max_turns:]

        # Limit 2: total character budget (oldest dropped first)
        while messages and sum(len(m.content) for m in messages) > max_chars:
            messages = messages[1:]

        return messages

    def message_count(self, conversation_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def build_context(
        system_prompt: str,
        history: Sequence[ChatMessage],
        new_user_message: str,
    ) -> List[ChatMessage]:
        """Assemble the exact message list sent to the LLM.

        Order: system prompt first (trusted), history second (user-owned
        data), new message last. This function owns that contract so no
        other module can smuggle a different system prompt in.
        """
        context = [ChatMessage(role="system", content=system_prompt)]
        context.extend(history)
        context.append(ChatMessage(role="user", content=new_user_message))
        return context
