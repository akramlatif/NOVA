# ==============================================================================
# NOVA — Built-in Tools (Phase 3)
# ------------------------------------------------------------------------------
# The ONLY tools connected in Phase 3 are deliberately trivial and safe:
# echo (returns its input) and clock (returns the time). This honors the
# master rule: "Do not connect real desktop-control tools until the
# orchestrator passes its tests."
#
# Real tools (files, browser, terminal, desktop) arrive in Phases 4-6 and
# must go through the same ToolSpec registration — they get NO special
# treatment from the orchestrator.
# ==============================================================================

from __future__ import annotations

from datetime import datetime, timezone

from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register the two safe demo tools. Explicit, reviewed registration."""

    def echo(text: str) -> str:
        """Return the given text unchanged. Test/verification helper."""
        return text

    def current_time() -> str:
        """Return the current UTC time in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    registry.register(ToolSpec(
        name="echo",
        description="Return the given text unchanged (test/verification helper).",
        handler=echo,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"text": "string — text to return"},
        output_schema={"returns": "string — same text"},
        error_notes="Cannot fail under normal use.",
    ))

    registry.register(ToolSpec(
        name="clock",
        description="Return the current UTC time in ISO format.",
        handler=current_time,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={},
        output_schema={"returns": "string — ISO timestamp"},
        error_notes="Cannot fail under normal use.",
    ))
