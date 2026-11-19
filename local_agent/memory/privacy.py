"""Privacy and Secret Sanitization for NOVA Memory — Phase 7.

Ensures sensitive authentication tokens, API keys, and passwords
are never stored as persistent memories.
"""

from __future__ import annotations

import re
from typing import Tuple


class PrivacyViolationError(Exception):
    """Raised when an attempt is made to store sensitive secrets in memory."""


class PrivacyScrubber:
    """Detects and scrubs secrets from memory candidates."""

    SENSITIVE_PATTERNS = [
        # API Keys & Tokens
        (r"(?i)\b(?:api[_-]?key|apikey|token|secret)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?", "API/Secret Key"),
        (r"\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}\b", "GitHub Token"),
        (r"\bsk-[a-zA-Z0-9_\-]{20,}\b", "OpenAI/LLM Key"),
        (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key ID"),
        # Passwords
        (r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?", "Password"),
        # Private Keys
        (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Key"),
        # Credit Card Numbers
        (r"\b(?:\d{4}[ -]?){3}\d{4}\b", "Payment Card"),
    ]

    @classmethod
    def check_for_secrets(cls, text: str) -> Tuple[bool, str]:
        """Check if text contains credentials or API keys.

        Returns:
            Tuple of (contains_secret: bool, secret_type: str)
        """
        for pattern, secret_type in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                return True, secret_type
        return False, ""

    @classmethod
    def validate_memory_content(cls, key: str, content: str) -> None:
        """Validate that a memory does not contain sensitive secrets."""
        has_secret_key, secret_type_k = cls.check_for_secrets(key)
        if has_secret_key:
            raise PrivacyViolationError(
                f"Memory key rejected: detected {secret_type_k}. Secrets must never be stored in persistent memory."
            )

        has_secret_val, secret_type_v = cls.check_for_secrets(content)
        if has_secret_val:
            raise PrivacyViolationError(
                f"Memory content rejected: detected {secret_type_v}. Passwords and API tokens cannot be memorized."
            )

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Replace detected secrets with [REDACTED_SECRET]."""
        sanitized = text
        for pattern, _ in cls.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, "[REDACTED_SECRET]", sanitized)
        return sanitized
