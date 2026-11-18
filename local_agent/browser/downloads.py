"""Download Manager for NOVA's Browser Automation Agent.

Handles safe file naming, duplicate detection, content verification,
file type allowlisting, and prevents directory traversal attacks.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


class DownloadError(Exception):
    """Raised when a download operation fails or violates safety rules."""


class DownloadManager:
    """Manages file downloads into an isolated, sandboxed directory."""

    # Default permitted file extensions for research & documents
    DEFAULT_ALLOWED_EXTENSIONS = (
        ".pdf",
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".zip",
        ".docx",
        ".xlsx",
        ".pptx",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    )

    # Strictly forbidden executable or script extensions
    BLOCKED_EXTENSIONS = (
        ".exe",
        ".msi",
        ".bat",
        ".cmd",
        ".ps1",
        ".vbs",
        ".js",
        ".scr",
        ".dll",
        ".com",
        ".pif",
    )

    def __init__(
        self,
        download_dir: Path | str,
        allowed_extensions: Sequence[str] = DEFAULT_ALLOWED_EXTENSIONS,
        max_file_size_bytes: int = 50 * 1024 * 1024,  # 50 MB safety ceiling
    ) -> None:
        self.download_dir = Path(download_dir).resolve()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_extensions = {ext.lower() for ext in allowed_extensions}
        self.max_file_size_bytes = max_file_size_bytes

    def sanitize_filename(self, filename: str) -> str:
        """Strip directory traversal elements and illegal filesystem characters."""
        if not filename or not filename.strip():
            return "downloaded_file"

        # Remove path separators
        clean = Path(filename).name.strip()
        # Remove dangerous or invalid Windows characters: <>:"/\|?*
        clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", clean)
        # Limit length to 200 chars
        if len(clean) > 200:
            stem = Path(clean).stem[:180]
            ext = Path(clean).suffix
            clean = f"{stem}{ext}"
        return clean or "downloaded_file"

    def validate_file_type(self, filename: str) -> str:
        """Verify the file extension against permitted and blocked lists."""
        ext = Path(filename).suffix.lower()
        if not ext:
            raise DownloadError(f"Download rejected: file {filename!r} has no extension.")
        if ext in self.BLOCKED_EXTENSIONS:
            raise DownloadError(
                f"Security violation: executable file download {filename!r} is strictly forbidden."
            )
        if ext not in self.allowed_extensions:
            raise DownloadError(
                f"File type {ext!r} is not in approved download extensions: {sorted(list(self.allowed_extensions))}"
            )
        return ext

    def resolve_unique_path(self, target_name: str) -> Path:
        """Resolve a non-colliding destination path by suffixing counter if exists."""
        clean_name = self.sanitize_filename(target_name)
        dest = self.download_dir / clean_name
        if not dest.exists():
            return dest

        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while True:
            candidate = self.download_dir / f"{stem} ({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def verify_download(self, file_path: Path) -> Dict[str, Any]:
        """Verify that a downloaded file exists, is non-empty, and calculate SHA-256."""
        if not file_path.exists():
            raise DownloadError(f"Download verification failed: file does not exist at {file_path}")
        if not file_path.is_file():
            raise DownloadError(f"Download target is not a regular file: {file_path}")

        size = file_path.stat().st_size
        if size == 0:
            raise DownloadError(f"Download verification failed: file is empty (0 bytes): {file_path}")
        if size > self.max_file_size_bytes:
            raise DownloadError(
                f"Download exceeded maximum permitted size ({size} > {self.max_file_size_bytes} bytes): {file_path}"
            )

        # Compute SHA-256 for integrity and duplicate tracking
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()

        return {
            "path": str(file_path),
            "filename": file_path.name,
            "size_bytes": size,
            "sha256": digest,
            "verified": True,
        }
