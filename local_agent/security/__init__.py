"""Security and sandboxing engine for NOVA.

Provides strict filesystem boundaries, command execution allowlists,
and tamper-evident audit logging.
"""

from local_agent.security.paths import (
    PathSandbox,
    SecurityError,
    PathTraversalError,
    AccessDeniedError,
)
from local_agent.security.terminal import (
    TerminalAllowlist,
    BlockedCommandError,
)
from local_agent.security.audit import (
    SecurityAuditLogger,
    AuditRecord,
)

__all__ = [
    "PathSandbox",
    "SecurityError",
    "PathTraversalError",
    "AccessDeniedError",
    "TerminalAllowlist",
    "BlockedCommandError",
    "SecurityAuditLogger",
    "AuditRecord",
]
