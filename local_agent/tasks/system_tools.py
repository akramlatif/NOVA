"""System and File Management Tool Adapters for NOVA — Phase 6.

Exposes file operations, document readers, download organization,
system monitoring, and controlled terminal execution to the Agent Orchestrator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from local_agent.security.paths import PathSandbox
from local_agent.system.files import FileManager
from local_agent.system.documents import DocumentProcessor
from local_agent.system.organizer import DownloadOrganizer
from local_agent.system.monitor import SystemMonitor
from local_agent.system.terminal import ControlledTerminal
from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec


def register_system_management_tools(
    registry: ToolRegistry,
    sandbox: Optional[PathSandbox] = None,
    file_manager: Optional[FileManager] = None,
    doc_processor: Optional[DocumentProcessor] = None,
    organizer: Optional[DownloadOrganizer] = None,
    monitor: Optional[SystemMonitor] = None,
    terminal: Optional[ControlledTerminal] = None,
) -> Dict[str, Any]:
    """Register all Phase 6 File and System Management tools into ToolRegistry."""
    sb = sandbox or PathSandbox(allowed_roots=[Path.cwd()])
    files = file_manager or FileManager(sb)
    docs = doc_processor or DocumentProcessor(sb)
    org = organizer or DownloadOrganizer(sb, file_manager=files)
    mon = monitor or SystemMonitor()
    term = terminal or ControlledTerminal(working_dir=sb.allowed_roots[0])

    # 1. File Search
    registry.register(ToolSpec(
        name="file_search",
        description="Search for files by name pattern, extension, or size inside sandboxed directories.",
        handler=lambda query, directory=None, recursive=True, extensions=None: files.search_files(
            query=query, directory=directory, recursive=recursive, extensions=extensions
        ),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"query": "string", "directory": "optional string", "recursive": "optional bool"},
        output_schema={"count": "int", "results": "list of dicts"},
    ))

    # 2. Folder Creation
    registry.register(ToolSpec(
        name="file_create_folder",
        description="Create a new folder securely inside the sandbox.",
        handler=lambda folder_path: files.create_folder(folder_path),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=5.0,
        input_schema={"folder_path": "string"},
        output_schema={"action": "string", "path": "string", "created": "bool"},
    ))

    # 3. File Read
    registry.register(ToolSpec(
        name="file_read",
        description="Read the contents of a text file up to a size limit.",
        handler=lambda file_path, max_bytes=100000: files.read_file(file_path, max_bytes),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={"file_path": "string", "max_bytes": "optional int"},
        output_schema={"path": "string", "content": "string", "truncated": "bool"},
    ))

    # 4. File Write
    registry.register(ToolSpec(
        name="file_write",
        description="Create or overwrite a file with given text content.",
        handler=lambda file_path, content, overwrite=False: files.write_file(file_path, content, overwrite),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=10.0,
        input_schema={"file_path": "string", "content": "string", "overwrite": "optional bool"},
        output_schema={"action": "string", "path": "string", "success": "bool"},
    ))

    # 5. File Copy
    registry.register(ToolSpec(
        name="file_copy",
        description="Copy a file to another location inside the sandbox.",
        handler=lambda source_path, destination_path, overwrite=False: files.copy_file(
            source_path, destination_path, overwrite
        ),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=15.0,
        input_schema={"source_path": "string", "destination_path": "string", "overwrite": "optional bool"},
        output_schema={"action": "string", "source": "string", "destination": "string", "success": "bool"},
    ))

    # 6. File Move
    registry.register(ToolSpec(
        name="file_move",
        description="Move a file to another location inside the sandbox.",
        handler=lambda source_path, destination_path, overwrite=False: files.move_file(
            source_path, destination_path, overwrite
        ),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=15.0,
        input_schema={"source_path": "string", "destination_path": "string", "overwrite": "optional bool"},
        output_schema={"action": "string", "source": "string", "destination": "string", "success": "bool"},
    ))

    # 7. File Rename
    registry.register(ToolSpec(
        name="file_rename",
        description="Rename a file in-place inside the sandbox.",
        handler=lambda file_path, new_name: files.rename_file(file_path, new_name),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=5.0,
        input_schema={"file_path": "string", "new_name": "string"},
        output_schema={"action": "string", "old_name": "string", "new_name": "string", "success": "bool"},
    ))

    # 8. File Find Duplicates
    registry.register(ToolSpec(
        name="file_find_duplicates",
        description="Identify duplicate files by matching size and computing SHA-256 hashes.",
        handler=lambda directory=None, recursive=True: files.find_duplicates(directory, recursive),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=20.0,
        input_schema={"directory": "optional string", "recursive": "optional bool"},
        output_schema={"duplicates": "list of dicts"},
    ))

    # 9. File Delete (Confirmed)
    registry.register(ToolSpec(
        name="file_delete",
        description="Permanently delete a file. Requires confirmed=True and human approval.",
        handler=lambda file_path, confirmed=False: files.delete_file(file_path, confirmed),
        permission_level=PermissionLevel.SENSITIVE,
        timeout_seconds=10.0,
        input_schema={"file_path": "string", "confirmed": "bool"},
        output_schema={"action": "string", "path": "string", "deleted": "bool"},
    ))

    # 10. Universal Document Reader
    registry.register(ToolSpec(
        name="document_read",
        description="Read and parse text/data from PDF, DOCX, XLSX, CSV, Markdown, or TXT documents.",
        handler=lambda file_path, max_chars=10000: docs.read_document(file_path, max_chars),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"file_path": "string", "max_chars": "optional int"},
        output_schema={"format": "string", "filename": "string", "text": "string"},
    ))

    # 11. Download Organization (Preview)
    registry.register(ToolSpec(
        name="downloads_organize_preview",
        description="Preview how a folder of downloads will be organized by type, date, or project.",
        handler=lambda directory, strategy="type", custom_rules=None: org.plan_organization(
            directory, strategy, custom_rules
        ).summary(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=10.0,
        input_schema={"directory": "string", "strategy": "optional string ('type','date','project')"},
        output_schema={"total_files_to_move": "int", "categories": "list"},
    ))

    # 12. Download Organization (Execute)
    def _exec_org(directory: str, strategy: str = "type", custom_rules: Optional[Dict[str, Sequence[str]]] = None):
        plan = org.plan_organization(directory, strategy, custom_rules)
        return org.execute_plan(plan)

    registry.register(ToolSpec(
        name="downloads_organize_execute",
        description="Execute organization moves for a directory based on strategy (type, date, project).",
        handler=_exec_org,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=25.0,
        input_schema={"directory": "string", "strategy": "optional string"},
        output_schema={"moved_count": "int", "success": "bool"},
    ))

    # 13. System Metrics Summary
    registry.register(ToolSpec(
        name="system_metrics_summary",
        description="Get current CPU %, RAM usage, OS details, architecture, and system uptime.",
        handler=lambda: mon.get_system_summary(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={},
        output_schema={"os": "string", "cpu": "dict", "ram": "dict", "uptime": "string"},
    ))

    # 14. Disk Usage
    registry.register(ToolSpec(
        name="system_disk_usage",
        description="Report storage space (total, used, free GB) for partitions or target folder.",
        handler=lambda path=None: mon.get_disk_usage(path),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"path": "optional string"},
        output_schema={"partitions": "list of dicts"},
    ))

    # 15. List Processes
    registry.register(ToolSpec(
        name="system_list_processes",
        description="List running system processes sorted by memory or CPU usage.",
        handler=lambda top_n=15, sort_by="memory", filter_name=None: mon.list_processes(top_n, sort_by, filter_name),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"top_n": "optional int", "sort_by": "optional string", "filter_name": "optional string"},
        output_schema={"processes": "list of dicts"},
    ))

    # 16. Controlled Terminal Execution
    registry.register(ToolSpec(
        name="terminal_execute_controlled",
        description="Run an allowlisted terminal command safely with buffer bounds and sanitized environment.",
        handler=lambda command_line, timeout_seconds=20.0: term.execute(command_line, timeout_seconds),
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=25.0,
        input_schema={"command_line": "string", "timeout_seconds": "optional float"},
        output_schema={"exit_code": "int", "stdout": "string", "stderr": "string"},
    ))

    return {
        "sandbox": sb,
        "files": files,
        "docs": docs,
        "organizer": org,
        "monitor": mon,
        "terminal": term,
    }
