# ==============================================================================
# NOVA — Tool Registry (Phase 3, Task 3)
# ------------------------------------------------------------------------------
# Every capability NOVA can invoke is a registered ToolSpec. The orchestrator
# can ONLY run tools from this registry — that is the allowlist boundary.
#
# Each tool declares:
#   name, description, input/output schema, permission level, timeout,
#   and an error-handling contract (typed errors, never bare exceptions).
#
# SECURITY: no tool is "auto-discovered". Registration is explicit, in code,
# reviewed by a human. The planner validates tool names against this registry
# BEFORE any plan exists; unknown tools are rejected at planning time.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

from local_agent.tasks.schemas import UnknownToolError


class PermissionLevel(IntEnum):
    """How dangerous a tool is. Higher = more restrictions.

    SAFE        - read-only or trivial; runs without confirmation
    NORMAL      - writes/changes state; runs without confirmation by default,
                  but the PLAN can still require it (e.g. downloads)
    SENSITIVE   - ALWAYS pauses for explicit user approval (terminal, deletes,
                  messaging, purchases, credentials, settings)
    """
    SAFE = 0
    NORMAL = 1
    SENSITIVE = 2


@dataclass(frozen=True)
class ToolSpec:
    """Full declaration of one tool. Immutable once registered."""
    name: str
    description: str
    handler: Callable[..., Any]
    permission_level: PermissionLevel
    timeout_seconds: float = 30.0
    input_schema: Optional[Dict[str, Any]] = None   # JSON-schema-style, docs/validation
    output_schema: Optional[Dict[str, Any]] = None
    error_notes: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("tool name must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive")


class ToolRegistry:
    """The explicit allowlist of executable capabilities."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    # ------------------------------------------------------------------ register
    def register(self, spec: ToolSpec) -> None:
        """Register a tool. Re-registration of the same name is an error —
        prevents accidental shadowing of a reviewed tool."""
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    # ------------------------------------------------------------------ lookup
    def get(self, name: str) -> ToolSpec:
        """Fetch a tool or raise UnknownToolError. This is the gate the
        planner uses — no plan may reference an unregistered tool."""
        try:
            return self._tools[name]
        except KeyError:
            raise UnknownToolError(
                f"Tool '{name}' is not registered. Available: "
                f"{sorted(self._tools)}"
            ) from None

    def has(self, name: str) -> bool:
        return name in self._tools

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return sorted(self._tools)

    def specs(self) -> List[ToolSpec]:
        return list(self._tools.values())

    # ------------------------------------------------------------------ summaries
    def catalog_for_planner(self) -> str:
        """Compact, planner-facing description of every tool: name,
        description, permission level, and input keys. This text goes into
        the planner prompt so the model only ever proposes real tools."""
        lines: List[str] = []
        for spec in self.specs():
            keys = ""
            if self._tools[spec.name].input_schema:
                keys = " | input keys: " + ", ".join(
                    sorted(self._tools[spec.name].input_schema)
                )
            lines.append(
                f"- {spec.name} (permission: {spec.permission_level.name}): "
                f"{spec.description}{keys}"
            )
        return "\n".join(lines)
