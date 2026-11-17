# ==============================================================================
# NOVA — Task History (Phase 3)
# ------------------------------------------------------------------------------
# SQLite-backed record of every task and every step result. Auditable,
# durable, HDD-friendly. Mirrors Phase 2's store design: zero services,
# single file in data/ (git-ignored).
#
# The history NEVER triggers anything — it is a write-only ledger with read
# helpers, so it can be safely opened/read even while tasks run.
# ==============================================================================

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from local_agent.tasks.schemas import StepResult, TaskResult, TaskStatus


class TaskHistory:
    """Persistent record of task executions."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id              TEXT PRIMARY KEY,
                    user_request    TEXT NOT NULL,
                    intent_summary  TEXT,
                    expected_result TEXT,
                    status          TEXT NOT NULL,
                    summary         TEXT,
                    error           TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_steps (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    step_id         INTEGER NOT NULL,
                    tool_name       TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    output          TEXT,          -- JSON-encoded
                    error           TEXT,
                    attempts        INTEGER NOT NULL DEFAULT 1,
                    started_at      TEXT,
                    finished_at     TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_task_steps_task ON task_steps(task_id);
                """
            )

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ tasks
    def record_task(self, task_id: str, user_request: str, intent: str,
                    expected: str, status: TaskStatus) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks "
                "(id, user_request, intent_summary, expected_result, status, "
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (task_id, user_request, intent, expected, status.value, now, now),
            )

    def update_task_status(self, task_id: str, status: TaskStatus,
                           summary: Optional[str] = None,
                           error: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = ?, summary = ?, error = ?, "
                "updated_at = ? WHERE id = ?",
                (status.value, summary, error, now, task_id),
            )

    def record_step(self, task_id: str, result: StepResult) -> None:
        import json as _json
        with self._conn:
            self._conn.execute(
                "INSERT INTO task_steps "
                "(task_id, step_id, tool_name, status, output, error, attempts, "
                " started_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    task_id, result.step_id, result.tool_name, result.status.value,
                    _json.dumps(result.output, default=str) if result.output is not None else None,
                    result.error, result.attempts,
                    result.started_at.isoformat(),
                    result.finished_at.isoformat() if result.finished_at else None,
                ),
            )

    # ------------------------------------------------------------------ reads
    def get_task(self, task_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_recent_tasks(self, limit: int = 20) -> List[dict]:
        rows = self._conn.execute(
            "SELECT id, user_request, status, created_at, updated_at, summary, error "
            "FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_steps(self, task_id: str) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_id",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def store_final_result(self, result: TaskResult) -> None:
        """Persist a TaskResult at task end (status + per-step rows already
        written incrementally; this updates the task-level row)."""
        self.update_task_status(
            result.task_id, result.status, summary=result.summary,
            error=result.error,
        )
