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


def register_safe_tools(
    registry: ToolRegistry,
    sandbox: Optional[Any] = None,
    allowlist: Optional[Any] = None,
) -> None:
    """Register all Phase 4 safe tools: filesystem, web, and terminal."""
    from pathlib import Path
    from local_agent.security.paths import PathSandbox
    from local_agent.security.terminal import TerminalAllowlist
    from local_agent.tasks.file_tools import (
        file_read,
        file_write,
        file_list,
        file_search,
        file_info,
    )
    from local_agent.tasks.web_tools import web_search, web_fetch_text
    from local_agent.tasks.terminal_tools import terminal_run

    # Always ensure baseline builtins are registered
    if "echo" not in registry:
        register_builtin_tools(registry)

    # Defaults if not injected
    project_root = Path(__file__).resolve().parents[2]
    active_sandbox = sandbox or PathSandbox(allowed_roots=[project_root])
    active_allowlist = allowlist or TerminalAllowlist()

    # --- Filesystem tools ---
    registry.register(ToolSpec(
        name="file_read",
        description="Read content of a file within the sandbox (bounded to 64 KB).",
        handler=lambda path, max_bytes=65536: file_read(active_sandbox, path, max_bytes),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"path": "string", "max_bytes": "optional int"},
        output_schema={"content": "string", "size_bytes": "int", "truncated": "bool"},
        error_notes="Raises FileToolError on path escape, missing file, or read failure.",
    ))

    registry.register(ToolSpec(
        name="file_write",
        description="Write text to a file inside the sandbox. Overwrites require approval.",
        handler=lambda path, content, overwrite=False: file_write(active_sandbox, path, content, overwrite),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=10.0,
        input_schema={"path": "string", "content": "string", "overwrite": "optional bool"},
        output_schema={"bytes_written": "int", "created": "bool"},
        error_notes="Raises FileToolError on escape or unconfirmed overwrite.",
    ))

    registry.register(ToolSpec(
        name="file_list",
        description="List files in a directory within the sandbox.",
        handler=lambda directory=".", pattern="*", recursive=False, max_results=100: file_list(
            active_sandbox, directory, pattern, recursive, max_results
        ),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"directory": "optional string", "pattern": "optional string", "recursive": "optional bool"},
        output_schema={"count": "int", "entries": "list of dicts"},
        error_notes="Raises FileToolError on escape or missing directory.",
    ))

    registry.register(ToolSpec(
        name="file_search",
        description="Search files by name or text content within the sandbox.",
        handler=lambda query, directory=".", max_matches=50: file_search(
            active_sandbox, directory, query, max_matches
        ),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={"query": "string", "directory": "optional string"},
        output_schema={"matches": "list of dicts", "count": "int"},
        error_notes="Raises FileToolError on empty query or escape.",
    ))

    registry.register(ToolSpec(
        name="file_info",
        description="Get metadata for a path inside the sandbox.",
        handler=lambda path: file_info(active_sandbox, path),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"path": "string"},
        output_schema={"exists": "bool", "size_bytes": "int", "is_file": "bool"},
        error_notes="Raises FileToolError on escape.",
    ))

    # --- Web tools ---
    registry.register(ToolSpec(
        name="web_search",
        description="Search the web using DuckDuckGo without API keys.",
        handler=lambda query, max_results=5: web_search(query, max_results),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"query": "string", "max_results": "optional int"},
        output_schema={"results": "list of dicts", "count": "int"},
        error_notes="Raises WebToolError on network error.",
    ))

    registry.register(ToolSpec(
        name="web_fetch_text",
        description="Fetch text content of a public web page with HTML stripped.",
        handler=lambda url, max_length=4000: web_fetch_text(url, max_length),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"url": "string (http/https)", "max_length": "optional int"},
        output_schema={"text": "string", "content_length": "int"},
        error_notes="Raises WebToolError on SSRF attempt, HTTP error, or timeout.",
    ))

    # --- Terminal tool ---
    registry.register(ToolSpec(
        name="terminal_run",
        description="Run an allowlisted CLI command safely.",
        handler=lambda command, working_dir=None, timeout_seconds=20.0: terminal_run(
            active_allowlist, command, working_dir, timeout_seconds
        ),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=25.0,
        input_schema={"command": "string", "working_dir": "optional string"},
        output_schema={"stdout": "string", "stderr": "string", "returncode": "int", "success": "bool"},
        error_notes="Raises TerminalToolError on unapproved command or timeout.",
    ))
