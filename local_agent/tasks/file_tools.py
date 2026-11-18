"""Safe Filesystem Tools for NOVA.

Performs sandboxed file operations strictly confined within approved roots.
Guards against unbounded file reads and protects sensitive files.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from local_agent.security.paths import PathSandbox, SecurityError


class FileToolError(Exception):
    """Base exception for file tool errors."""


def file_read(
    sandbox: PathSandbox,
    path: str,
    max_bytes: int = 65536,
) -> Dict[str, Any]:
    """Read file content safely within the sandbox.

    Args:
        sandbox: The active PathSandbox instance.
        path: Relative or absolute path to read.
        max_bytes: Maximum bytes to read (default 64 KB) to bound memory.
    """
    try:
        resolved = sandbox.validate_path(path)
    except SecurityError as e:
        raise FileToolError(f"Permission denied: {e}") from e

    if not resolved.exists():
        raise FileToolError(f"File not found: {path}")
    if not resolved.is_file():
        raise FileToolError(f"Path is not a regular file: {path}")

    file_size = resolved.stat().st_size
    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)
    except Exception as e:
        raise FileToolError(f"Failed to read file {path}: {e}") from e

    truncated = file_size > max_bytes
    return {
        "path": str(resolved),
        "content": content,
        "truncated": truncated,
        "size_bytes": file_size,
        "bytes_returned": len(content.encode("utf-8")),
    }


def file_write(
    sandbox: PathSandbox,
    path: str,
    content: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Write text content safely to a file within the sandbox.

    Args:
        sandbox: The active PathSandbox instance.
        path: Path to write.
        content: Text content to write.
        overwrite: If True, permits overwriting an existing file.
    """
    try:
        resolved = sandbox.validate_path(path, allow_write=True)
    except SecurityError as e:
        raise FileToolError(f"Permission denied: {e}") from e

    exists_already = resolved.exists()
    if exists_already and not overwrite:
        raise FileToolError(
            f"File already exists: {path}. Pass overwrite=True to replace."
        )

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise FileToolError(f"Failed to write file {path}: {e}") from e

    return {
        "path": str(resolved),
        "bytes_written": len(content.encode("utf-8")),
        "created": not exists_already,
        "overwritten": exists_already,
    }


def file_list(
    sandbox: PathSandbox,
    directory: str = ".",
    pattern: str = "*",
    recursive: bool = False,
    max_results: int = 100,
) -> Dict[str, Any]:
    """List directory contents matching a pattern within the sandbox."""
    try:
        resolved_dir = sandbox.validate_path(directory)
    except SecurityError as e:
        raise FileToolError(f"Permission denied: {e}") from e

    if not resolved_dir.exists():
        raise FileToolError(f"Directory not found: {directory}")
    if not resolved_dir.is_dir():
        raise FileToolError(f"Path is not a directory: {directory}")

    entries: List[Dict[str, Any]] = []
    iterator = resolved_dir.rglob(pattern) if recursive else resolved_dir.glob(pattern)

    truncated = False
    for item in iterator:
        # Check that individual matched items don't escape or target sensitive secrets
        try:
            sandbox.validate_path(item)
        except SecurityError:
            continue

        try:
            st = item.stat()
            entries.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size_bytes": st.st_size if item.is_file() else 0,
            })
        except (OSError, PermissionError):
            continue

        if len(entries) >= max_results:
            truncated = True
            break

    return {
        "directory": str(resolved_dir),
        "count": len(entries),
        "truncated": truncated,
        "entries": entries,
    }


def file_search(
    sandbox: PathSandbox,
    directory: str = ".",
    query: str = "",
    max_matches: int = 50,
) -> Dict[str, Any]:
    """Search for files by name or text content within the sandbox."""
    if not query or not query.strip():
        raise FileToolError("Search query cannot be empty.")

    query_lower = query.lower().strip()
    try:
        resolved_dir = sandbox.validate_path(directory)
    except SecurityError as e:
        raise FileToolError(f"Permission denied: {e}") from e

    matches: List[Dict[str, Any]] = []
    truncated = False

    for root_str, dirs, files in os.walk(resolved_dir):
        # Exclude hidden or git directories from walking
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for fname in files:
            file_path = Path(root_str) / fname
            try:
                sandbox.validate_path(file_path)
            except SecurityError:
                continue

            # 1. Match by filename
            matched = False
            match_type = ""
            if query_lower in fname.lower():
                matched = True
                match_type = "filename"

            # 2. Match by file content (for text files under 2 MB)
            if not matched:
                try:
                    if file_path.stat().st_size <= 2 * 1024 * 1024:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            if query_lower in content.lower():
                                matched = True
                                match_type = "content"
                except Exception:
                    pass

            if matched:
                matches.append({
                    "name": fname,
                    "path": str(file_path),
                    "match_type": match_type,
                    "size_bytes": file_path.stat().st_size,
                })

            if len(matches) >= max_matches:
                truncated = True
                break
        if truncated:
            break

    return {
        "directory": str(resolved_dir),
        "query": query,
        "count": len(matches),
        "truncated": truncated,
        "matches": matches,
    }


def file_info(
    sandbox: PathSandbox,
    path: str,
) -> Dict[str, Any]:
    """Get metadata for a path within the sandbox."""
    try:
        resolved = sandbox.validate_path(path)
    except SecurityError as e:
        raise FileToolError(f"Permission denied: {e}") from e

    exists = resolved.exists()
    info: Dict[str, Any] = {
        "path": str(resolved),
        "exists": exists,
        "is_file": resolved.is_file() if exists else False,
        "is_dir": resolved.is_dir() if exists else False,
    }
    if exists:
        st = resolved.stat()
        info["size_bytes"] = st.st_size
        info["modified_at"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
    return info
