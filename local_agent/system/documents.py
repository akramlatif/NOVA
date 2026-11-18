"""Document Processing Engine for NOVA — Phase 6.

Extracts text, metadata, tables, and structures from common file formats:
TXT, Markdown (MD), CSV, PDF (pypdf), Word (DOCX), and Excel (XLSX).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from local_agent.security.paths import PathSandbox

logger = logging.getLogger(__name__)


class DocumentError(Exception):
    """Raised when parsing or reading a document fails."""


class DocumentProcessor:
    """Extracts content and structure from documents inside the sandbox."""

    def __init__(self, sandbox: PathSandbox) -> None:
        self.sandbox = sandbox

    def _resolve(self, path: Union[str, Path]) -> Path:
        return self.sandbox.validate_path(path, allow_write=False)

    def read_document(
        self,
        file_path: Union[str, Path],
        max_chars: int = 10000,
        max_rows: int = 50,
    ) -> Dict[str, Any]:
        """Universal document reader routing by extension."""
        target = self._resolve(file_path)
        if not target.exists() or not target.is_file():
            raise DocumentError(f"Document not found: {target}")

        ext = target.suffix.lower()
        if ext in (".txt", ".log", ".json", ".yaml", ".yml"):
            return self.read_text(target, max_chars)
        elif ext in (".md", ".markdown"):
            return self.read_markdown(target, max_chars)
        elif ext == ".csv":
            return self.read_csv(target, max_rows)
        elif ext == ".pdf":
            return self.read_pdf(target, max_chars)
        elif ext in (".docx", ".doc"):
            return self.read_docx(target, max_chars)
        elif ext in (".xlsx", ".xlsm"):
            return self.read_xlsx(target, max_rows)
        else:
            raise DocumentError(f"Unsupported document format: {ext}")

    # ------------------------------------------------------------------ TXT
    def read_text(self, path: Path, max_chars: int = 10000) -> Dict[str, Any]:
        """Read standard plaintext file."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars + 1)
            truncated = len(content) > max_chars
            text = content[:max_chars]
            return {
                "format": "txt",
                "filename": path.name,
                "text": text,
                "char_count": len(text),
                "truncated": truncated,
            }
        except Exception as e:
            raise DocumentError(f"Failed to read text file {path.name}: {e}") from e

    # ------------------------------------------------------------------ Markdown
    def read_markdown(self, path: Path, max_chars: int = 10000) -> Dict[str, Any]:
        """Read markdown and parse section headings."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars + 1)
            truncated = len(content) > max_chars
            text = content[:max_chars]

            headings = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    headings.append(stripped)

            return {
                "format": "markdown",
                "filename": path.name,
                "text": text,
                "headings": headings[:20],
                "char_count": len(text),
                "truncated": truncated,
            }
        except Exception as e:
            raise DocumentError(f"Failed to read markdown file {path.name}: {e}") from e

    # ------------------------------------------------------------------ CSV
    def read_csv(self, path: Path, max_rows: int = 50) -> Dict[str, Any]:
        """Parse CSV rows and headers."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                rows = []
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    rows.append(row)

            return {
                "format": "csv",
                "filename": path.name,
                "headers": headers,
                "rows_sample": rows,
                "row_count_returned": len(rows),
            }
        except Exception as e:
            raise DocumentError(f"Failed to parse CSV {path.name}: {e}") from e

    # ------------------------------------------------------------------ PDF
    def read_pdf(self, path: Path, max_chars: int = 10000) -> Dict[str, Any]:
        """Extract text and metadata from PDF using pypdf."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            total_pages = len(reader.pages)
            extracted_text = []
            char_count = 0

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                extracted_text.append(f"--- Page {page_num + 1} ---\n{text}")
                char_count += len(text)
                if char_count >= max_chars:
                    break

            full_text = "\n\n".join(extracted_text)
            truncated = char_count >= max_chars

            return {
                "format": "pdf",
                "filename": path.name,
                "total_pages": total_pages,
                "text": full_text[:max_chars],
                "char_count": min(char_count, max_chars),
                "truncated": truncated,
            }
        except Exception as e:
            raise DocumentError(f"Failed to parse PDF {path.name}: {e}") from e

    # ------------------------------------------------------------------ DOCX
    def read_docx(self, path: Path, max_chars: int = 10000) -> Dict[str, Any]:
        """Extract text and tables from Word DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(str(path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            
            # Extract basic table contents
            tables_data = []
            for table in doc.tables[:3]:  # sample up to 3 tables
                t_rows = []
                for row in table.rows[:10]:
                    t_rows.append([cell.text.strip() for cell in row.cells])
                if t_rows:
                    tables_data.append(t_rows)

            full_text = "\n\n".join(paragraphs)
            truncated = len(full_text) > max_chars

            return {
                "format": "docx",
                "filename": path.name,
                "paragraph_count": len(paragraphs),
                "tables_count": len(doc.tables),
                "text": full_text[:max_chars],
                "char_count": len(full_text[:max_chars]),
                "tables_sample": tables_data,
                "truncated": truncated,
            }
        except Exception as e:
            raise DocumentError(f"Failed to read DOCX {path.name}: {e}") from e

    # ------------------------------------------------------------------ XLSX
    def read_xlsx(self, path: Path, max_rows: int = 50) -> Dict[str, Any]:
        """Inspect sheet names and read table cells from Excel XLSX using openpyxl."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            active_sheet = wb.active or wb[sheet_names[0]]

            rows_sample = []
            for i, row in enumerate(active_sheet.iter_rows(values_only=True)):
                if i >= max_rows:
                    break
                rows_sample.append([str(c) if c is not None else "" for c in row])

            wb.close()
            return {
                "format": "xlsx",
                "filename": path.name,
                "sheet_names": sheet_names,
                "active_sheet": active_sheet.title,
                "rows_sample": rows_sample,
                "row_count_returned": len(rows_sample),
            }
        except Exception as e:
            raise DocumentError(f"Failed to read Excel workbook {path.name}: {e}") from e
