"""NOVA File & System Management Agent — Phase 6.

Provides secure filesystem operations, document processing (PDF, DOCX, XLSX,
CSV, TXT, MD), intelligent download organization, system monitoring via psutil,
and controlled terminal command execution.
"""

from local_agent.system.files import FileManager, FileOperationError
from local_agent.system.documents import DocumentProcessor, DocumentError
from local_agent.system.organizer import DownloadOrganizer, OrganizationPlan
from local_agent.system.monitor import SystemMonitor
from local_agent.system.terminal import ControlledTerminal, TerminalExecutionError

__all__ = [
    "FileManager",
    "FileOperationError",
    "DocumentProcessor",
    "DocumentError",
    "DownloadOrganizer",
    "OrganizationPlan",
    "SystemMonitor",
    "ControlledTerminal",
    "TerminalExecutionError",
]
