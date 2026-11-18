"""Secure File Operations Manager for NOVA — Phase 6.

Enforces PathSandbox boundary constraints on all filesystem interactions.
Supports search, folder creation, reading, writing, copying, moving,
renaming, duplicate detection, and confirmed deletion.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from local_agent.security.paths import PathSandbox, PathTraversalError, AccessDeniedError

logger = logging.getLogger(__name__)


class FileOperationError(Exception):
    """Raised when a filesystem operation fails."""


class FileManager:
    """Provides secure, sandboxed filesystem operations."""

    def __init__(self, sandbox: PathSandbox) -> None:
        self.sandbox = sandbox

    def _resolve(self, path: Union[str, Path], allow_write: bool = False) -> Path:
        """Resolve and validate path against sandbox rules."""
        return self.sandbox.validate_path(path, allow_write=allow_write)

    # ------------------------------------------------------------------ Search
    def search_files(
        self,
        query: str,
        directory: Optional[Union[str, Path]] = None,
        recursive: bool = True,
        extensions: Optional[Sequence[str]] = None,
        max_results: int = 100,
        min_size_bytes: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search files by pattern, extension, or size inside sandboxed directory."""
        base_dir = self._resolve(directory or self.sandbox.allowed_roots[0])
        if not base_dir.is_dir():
            raise FileOperationError(f"Search target is not a directory: {base_dir}")

        ext_filter = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions} if extensions else None
        results: List[Dict[str, Any]] = []

        iterator = base_dir.rglob("*") if recursive else base_dir.glob("*")
        for item in iterator:
            if len(results) >= max_results:
                break
            try:
                if not item.is_file():
                    continue

                # Filter by extension if specified
                if ext_filter and item.suffix.lower() not in ext_filter:
                    continue

                # Filter by query pattern (glob match on filename or substring)
                name = item.name
                if query and query != "*" and not (
                    fnmatch.fnmatch(name.lower(), f"*{query.lower()}*") or
                    fnmatch.fnmatch(name.lower(), query.lower())
                ):
                    continue

                # Sandbox check
                self.sandbox.validate_path(item)
                stat = item.stat()

                # Filter by size
                if min_size_bytes is not None and stat.st_size < min_size_bytes:
                    continue
                if max_size_bytes is not None and stat.st_size > max_size_bytes:
                    continue

                results.append({
                    "name": name,
                    "path": str(item),
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                    "extension": item.suffix.lower(),
                })
            except (AccessDeniedError, PathTraversalError, PermissionError, OSError):
                continue

        return results

    # ------------------------------------------------------------------ Folder creation
    def create_folder(self, folder_path: Union[str, Path]) -> Dict[str, Any]:
        """Create a directory securely inside the sandbox."""
        target = self._resolve(folder_path, allow_write=True)
        if target.exists() and not target.is_dir():
            raise FileOperationError(f"A non-directory file already exists at {target}")
        
        target.mkdir(parents=True, exist_ok=True)
        return {
            "action": "create_folder",
            "path": str(target),
            "created": True,
        }

    # ------------------------------------------------------------------ File Reading
    def read_file(
        self,
        file_path: Union[str, Path],
        max_bytes: int = 100 * 1024,
    ) -> Dict[str, Any]:
        """Read a file's content up to max_bytes."""
        target = self._resolve(file_path, allow_write=False)
        if not target.exists():
            raise FileOperationError(f"File does not exist: {target}")
        if not target.is_file():
            raise FileOperationError(f"Path is not a regular file: {target}")

        stat = target.stat()
        truncated = stat.st_size > max_bytes

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
        except OSError as e:
            raise FileOperationError(f"Failed to read file {target}: {e}") from e

        return {
            "path": str(target),
            "filename": target.name,
            "size_bytes": stat.st_size,
            "content": content,
            "truncated": truncated,
        }

    # ------------------------------------------------------------------ File Writing
    def write_file(
        self,
        file_path: Union[str, Path],
        content: str,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Create or overwrite a file securely."""
        target = self._resolve(file_path, allow_write=True)
        if target.exists() and not overwrite:
            raise FileOperationError(
                f"File {target.name} already exists. Set overwrite=True with approval to replace."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            raise FileOperationError(f"Failed to write file {target}: {e}") from e

        return {
            "action": "write_file",
            "path": str(target),
            "bytes_written": len(content.encode("utf-8")),
            "success": True,
        }

    # ------------------------------------------------------------------ Copying & Moving
    def copy_file(
        self,
        source_path: Union[str, Path],
        destination_path: Union[str, Path],
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Copy a file to a new location inside the sandbox."""
        src = self._resolve(source_path, allow_write=False)
        dst = self._resolve(destination_path, allow_write=True)

        if not src.exists() or not src.is_file():
            raise FileOperationError(f"Source file does not exist: {src}")

        if dst.is_dir():
            dst = dst / src.name

        if dst.exists() and not overwrite:
            raise FileOperationError(f"Destination {dst.name} already exists. Overwrite not permitted.")

        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            raise FileOperationError(f"Copy failed from {src} to {dst}: {e}") from e

        return {
            "action": "copy_file",
            "source": str(src),
            "destination": str(dst),
            "size_bytes": dst.stat().st_size,
            "success": True,
        }

    def move_file(
        self,
        source_path: Union[str, Path],
        destination_path: Union[str, Path],
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Move a file to a new location inside the sandbox."""
        src = self._resolve(source_path, allow_write=True)
        dst = self._resolve(destination_path, allow_write=True)

        if not src.exists() or not src.is_file():
            raise FileOperationError(f"Source file does not exist: {src}")

        if dst.is_dir():
            dst = dst / src.name

        if dst.exists() and not overwrite:
            raise FileOperationError(f"Destination {dst.name} already exists. Overwrite not permitted.")

        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(src, dst)
        except OSError as e:
            raise FileOperationError(f"Move failed from {src} to {dst}: {e}") from e

        return {
            "action": "move_file",
            "source": str(src),
            "destination": str(dst),
            "success": True,
        }

    def rename_file(
        self,
        file_path: Union[str, Path],
        new_name: str,
    ) -> Dict[str, Any]:
        """Rename a file in-place."""
        src = self._resolve(file_path, allow_write=True)
        if not src.exists():
            raise FileOperationError(f"File to rename does not exist: {src}")

        # Sanitize new_name: remove directory separators
        clean_name = Path(new_name).name.strip()
        if not clean_name:
            raise FileOperationError("New file name cannot be empty.")

        dst = src.parent / clean_name
        self.sandbox.validate_path(dst, allow_write=True)

        if dst.exists() and dst != src:
            raise FileOperationError(f"A file named {clean_name!r} already exists in this folder.")

        try:
            src.rename(dst)
        except OSError as e:
            raise FileOperationError(f"Rename failed: {e}") from e

        return {
            "action": "rename_file",
            "old_name": src.name,
            "new_name": clean_name,
            "path": str(dst),
            "success": True,
        }

    # ------------------------------------------------------------------ Duplicate Detection
    def find_duplicates(
        self,
        directory: Optional[Union[str, Path]] = None,
        recursive: bool = True,
    ) -> List[Dict[str, Any]]:
        """Identify duplicate files using a two-pass algorithm: size grouping then SHA-256."""
        base_dir = self._resolve(directory or self.sandbox.allowed_roots[0])
        if not base_dir.is_dir():
            raise FileOperationError(f"Target is not a directory: {base_dir}")

        size_map: Dict[int, List[Path]] = defaultdict(list)
        iterator = base_dir.rglob("*") if recursive else base_dir.glob("*")

        # Pass 1: Quick grouping by exact byte size (zero disk read)
        for item in iterator:
            try:
                if item.is_file():
                    self.sandbox.validate_path(item)
                    size = item.stat().st_size
                    if size > 0:  # Skip zero-byte files
                        size_map[size].append(item)
            except Exception:
                continue

        duplicates: List[Dict[str, Any]] = []

        # Pass 2: Hash only groups containing 2 or more files
        for size, candidates in size_map.items():
            if len(candidates) < 2:
                continue

            hash_map: Dict[str, List[str]] = defaultdict(list)
            for path in candidates:
                try:
                    hasher = hashlib.sha256()
                    with open(path, "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            hasher.update(chunk)
                    digest = hasher.hexdigest()
                    hash_map[digest].append(str(path))
                except Exception:
                    continue

            for digest, paths in hash_map.items():
                if len(paths) > 1:
                    duplicates.append({
                        "size_bytes": size,
                        "sha256": digest,
                        "count": len(paths),
                        "files": paths,
                    })

        return duplicates

    # ------------------------------------------------------------------ Safe Deletion
    def delete_file(
        self,
        file_path: Union[str, Path],
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Safely delete a file with mandatory explicit confirmation."""
        target = self._resolve(file_path, allow_write=True)
        if not target.exists():
            raise FileOperationError(f"File to delete does not exist: {target}")

        if not confirmed:
            raise FileOperationError(
                f"Permanent deletion of {target.name!r} requires explicit user confirmation (confirmed=True)."
            )

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        except OSError as e:
            raise FileOperationError(f"Deletion failed: {e}") from e

        return {
            "action": "delete_file",
            "path": str(target),
            "deleted": True,
        }
