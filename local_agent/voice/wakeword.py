"""Wake-Word Detection & Privacy Gate for NOVA — Phase 8.

Treats wake-word activation as an optional feature. Never records continuously
without explicit, documented user consent.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class WakeWordConsentError(Exception):
    """Raised when continuous listening is attempted without explicit user consent."""


class WakeWordDetector:
    """Detects trigger words and guards user audio privacy."""

    DEFAULT_WAKE_WORDS = ["hey nova", "nova", "ok nova", "hello nova"]

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        enabled: bool = False,
        has_user_consent: bool = False,
    ) -> None:
        self.wake_words = [w.lower().strip() for w in (wake_words or self.DEFAULT_WAKE_WORDS)]
        self.enabled = enabled
        self.has_user_consent = has_user_consent

    def enable_with_consent(self, consent: bool = True) -> None:
        """Explicitly enable wake-word detection with confirmed user consent."""
        if not consent:
            raise WakeWordConsentError("Cannot enable wake-word detection without explicit user consent.")
        self.has_user_consent = True
        self.enabled = True
        logger.info("Wake-word detection enabled with explicit user consent: %s", self.wake_words)

    def disable(self) -> None:
        """Disable wake-word listening."""
        self.enabled = False
        logger.info("Wake-word detection disabled.")

    def check_audio_consent(self) -> None:
        """Validate privacy invariants before any continuous background audio capture."""
        if self.enabled and not self.has_user_consent:
            raise WakeWordConsentError(
                "Privacy violation: Continuous background listening is forbidden without explicit user consent."
            )

    def is_wake_word(self, transcript: str) -> bool:
        """Check if transcript triggers the wake word."""
        if not self.enabled:
            return False

        clean = transcript.lower().strip()
        for word in self.wake_words:
            # Match exact word or start of sentence
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, clean):
                return True
        return False

    def extract_command(self, transcript: str) -> str:
        """Strip the wake word from the prompt to isolate the intent."""
        clean = transcript.strip()
        lower = clean.lower()
        for word in self.wake_words:
            if lower.startswith(word):
                command = clean[len(word):].lstrip(" ,.:;!?")
                return command or clean
        return clean
