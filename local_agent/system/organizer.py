"""Intelligent Download Organizer for NOVA — Phase 6.

Organizes disorganized folders (like Downloads) by:
- File type (Documents, Spreadsheets, Images, Archives, Code, Media)
- Date (YYYY/MM)
- Project / Subject tags
- User-defined categorization rules

Supports dry-run preview before execution, duplicate protection, and logging.
"""

from __future__ import annotations

import datetime
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from local_agent.security.paths import PathSandbox
from local_agent.system.files import FileManager, FileOperationError

logger = logging.getLogger(__name__)


@dataclass
class OrganizationMove:
    """Represents a planned file move."""
    source_path: str
    filename: str
    target_category: str
    destination_path: str


@dataclass
class OrganizationPlan:
    """Full preview of an organization operation."""
    source_directory: str
    strategy: str
    moves: List[OrganizationMove] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        return {
            "source_directory": self.source_directory,
            "strategy": self.strategy,
            "total_files_to_move": len(self.moves),
            "skipped_count": len(self.skipped),
            "categories": sorted(list({m.target_category for m in self.moves})),
        }


class DownloadOrganizer:
    """Organizes files into structured categories within the sandbox."""

    TYPE_CATEGORIES = {
        "Documents": {".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".epub"},
        "Spreadsheets": {".xlsx", ".xls", ".csv", ".tsv", ".ods"},
        "Presentations": {".pptx", ".ppt", ".key", ".odp"},
        "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"},
        "Archives": {".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz"},
        "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".ps1"},
        "Audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
        "Video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    }

    def __init__(self, sandbox: PathSandbox, file_manager: Optional[FileManager] = None) -> None:
        self.sandbox = sandbox
        self.file_manager = file_manager or FileManager(sandbox)

    def _resolve(self, path: Union[str, Path]) -> Path:
        return self.sandbox.validate_path(path, allow_write=True)

    def plan_organization(
        self,
        directory: Union[str, Path],
        strategy: str = "type",
        custom_rules: Optional[Dict[str, Sequence[str]]] = None,
        date_format: str = "%Y-%m",
    ) -> OrganizationPlan:
        """Create a plan preview without moving any files.

        Strategies:
            - 'type': By extension categories (Documents, Spreadsheets, Images, etc.)
            - 'date': By modification date folder (e.g. '2026-11')
            - 'project': By project keyword matching
            - 'custom': Using user-supplied dict of category_name -> list of keywords or extensions
        """
        source_dir = self._resolve(directory)
        if not source_dir.is_dir():
            raise FileOperationError(f"Directory not found: {source_dir}")

        plan = OrganizationPlan(source_directory=str(source_dir), strategy=strategy)

        # Look only at top-level files in the directory to avoid recursive mess
        for item in source_dir.iterdir():
            if not item.is_file():
                continue

            try:
                self.sandbox.validate_path(item)
            except Exception:
                plan.skipped.append({"file": item.name, "reason": "Access denied / protected"})
                continue

            category = self._determine_category(
                item=item,
                strategy=strategy,
                custom_rules=custom_rules,
                date_format=date_format,
            )

            if not category:
                plan.skipped.append({"file": item.name, "reason": "No matching category"})
                continue

            dest_dir = source_dir / category
            dest_file = dest_dir / item.name

            plan.moves.append(
                OrganizationMove(
                    source_path=str(item),
                    filename=item.name,
                    target_category=category,
                    destination_path=str(dest_file),
                )
            )

        return plan

    def _determine_category(
        self,
        item: Path,
        strategy: str,
        custom_rules: Optional[Dict[str, Sequence[str]]] = None,
        date_format: str = "%Y-%m",
    ) -> Optional[str]:
        ext = item.suffix.lower()
        name_lower = item.name.lower()

        # 1. Custom rules have highest priority
        if custom_rules:
            for cat_name, patterns in custom_rules.items():
                for p in patterns:
                    p_lower = p.lower()
                    if p_lower.startswith(".") and ext == p_lower:
                        return cat_name
                    elif p_lower in name_lower:
                        return cat_name

        # 2. Strategy: type
        if strategy == "type":
            for cat_name, exts in self.TYPE_CATEGORIES.items():
                if ext in exts:
                    return cat_name
            return "Other"

        # 3. Strategy: date
        elif strategy == "date":
            mtime = item.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(mtime)
            return dt.strftime(date_format)

        # 4. Strategy: project / subject
        elif strategy in ("project", "subject"):
            # Check for common delimiters like ProjectX_file.ext or Subject-Notes.pdf
            prefix = name_lower.split("_")[0].split("-")[0]
            if len(prefix) >= 3 and prefix.isalnum():
                return prefix.capitalize()
            return "General"

        return "Unsorted"

    def execute_plan(
        self,
        plan: OrganizationPlan,
    ) -> Dict[str, Any]:
        """Execute the planned moves safely with duplicate collision handling."""
        moved_count = 0
        errors = []

        for move in plan.moves:
            src = Path(move.source_path)
            dst = Path(move.destination_path)

            if not src.exists():
                errors.append(f"Source file {src.name} no longer exists.")
                continue

            try:
                # Ensure category directory exists
                dst.parent.mkdir(parents=True, exist_ok=True)

                # Avoid overwriting existing files: resolve unique name if colliding
                final_dst = dst
                if final_dst.exists() and final_dst != src:
                    stem = final_dst.stem
                    suffix = final_dst.suffix
                    counter = 1
                    while final_dst.exists():
                        final_dst = final_dst.parent / f"{stem} ({counter}){suffix}"
                        counter += 1

                shutil.move(src, final_dst)
                moved_count += 1
            except Exception as e:
                errors.append(f"Failed to move {src.name}: {e}")

        return {
            "action": "execute_organization",
            "strategy": plan.strategy,
            "moved_count": moved_count,
            "errors": errors,
            "success": len(errors) == 0,
        }
