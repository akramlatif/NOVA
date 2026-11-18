"""NOVA Persistent Memory System — Phase 7.

Provides SQLite-backed short-term, long-term, and task memory management
with secret privacy protection, duplicate detection, and prompt context enrichment.
"""

from local_agent.memory.schema import (
    MemoryCategory,
    MemoryEntry,
    UserPreference,
)
from local_agent.memory.privacy import (
    PrivacyScrubber,
    PrivacyViolationError,
)
from local_agent.memory.store import MemoryStore
from local_agent.memory.manager import MemoryManager

__all__ = [
    "MemoryCategory",
    "MemoryEntry",
    "UserPreference",
    "PrivacyScrubber",
    "PrivacyViolationError",
    "MemoryStore",
    "MemoryManager",
]
