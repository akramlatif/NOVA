"""Security Audit Logging.

Maintains an immutable, append-only ledger of security-relevant operations,
including tool executions, resource access, and approval statuses.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """Structured audit trail entry."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str = Field(..., description="Tool name or system operation")
    resource: str = Field(..., description="Target file path, command, or URL")
    permission_level: str = Field(..., description="SAFE, NORMAL, or SENSITIVE")
    approval_status: str = Field(
        default="unprompted",
        description="'approved', 'declined', or 'unprompted'"
    )
    success: bool
    error: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class SecurityAuditLogger:
    """Writes audit events to an append-only JSONL log file."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(log_path).resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: str,
        resource: str,
        permission_level: str,
        success: bool,
        approval_status: str = "unprompted",
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Create and write an audit event entry."""
        record = AuditRecord(
            action=action,
            resource=resource,
            permission_level=permission_level,
            approval_status=approval_status,
            success=success,
            error=error,
            details=details or {},
        )
        line = record.model_dump_json() + "\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)
        return record

    def read_records(self, limit: int = 50) -> List[AuditRecord]:
        """Read the most recent audit records."""
        if not self.log_path.exists():
            return []
        records: List[AuditRecord] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(AuditRecord.model_validate_json(line))
                    except Exception:
                        continue
        return records[-limit:]
