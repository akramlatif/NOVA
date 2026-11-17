# ==============================================================================
# NOVA — LLM Provider Abstraction (Phase 2, Task: provider replaceability)
# ------------------------------------------------------------------------------
# Purpose:
#   Defines the ONE interface NOVA's engine talks to. Ollama is the first
#   implementation; future providers (cloud APIs, llama.cpp, LM Studio) plug
#   in here without touching the engine or anything above it.
#
# Design rule (master instructions): the AI provider must remain replaceable.
# The engine never imports Ollama directly — it imports THIS file only.
# ==============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Sequence


# --------------------------------------------------------------------------- errors
class LLMError(Exception):
    """Base class for all LLM-layer failures. Never leak raw provider errors upward."""


class LLMConnectionError(LLMError):
    """Provider unreachable (service down, wrong host, refused)."""


class LLMTimeoutError(LLMError):
    """Provider accepted the request but exceeded the configured timeout."""


class LLMModelNotAvailableError(LLMError):
    """Requested model is not installed / not loadable in the provider."""


class LLMResponseFormatError(LLMError):
    """Provider responded, but the content could not be parsed into the
    expected format (e.g. invalid JSON when structured output was requested)."""


# --------------------------------------------------------------------------- message types
@dataclass(frozen=True)
class ChatMessage:
    """A single message in a conversation. Immutable by design."""
    role: str                      # "system" | "user" | "assistant"
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"Invalid chat role: {self.role!r}")
        if not self.content:
            raise ValueError("Message content must not be empty")


# --------------------------------------------------------------------------- config
@dataclass(frozen=True)
class ProviderConfig:
    """Connection settings for a provider instance."""
    model_name: str
    host: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 120.0          # HDD + CPU inference is slow — generous default
    stream: bool = True                     # stream so the user sees tokens as they arrive


# --------------------------------------------------------------------------- the contract
class LLMProvider(ABC):
    """Abstract base every NOVA LLM provider must implement.

    Implementations must:
      * raise the typed errors above (never bare Exception),
      * accept Sequence[ChatMessage] as full context (caller owns history),
      * return plain text for generate(), validated structures come later.
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def is_available(self) -> bool:
        """True if the provider service responds and the configured model exists."""
        ...

    @abstractmethod
    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Send full context, return the complete response text.
        Raises LLMConnectionError / LLMTimeoutError / LLMModelNotAvailableError."""
        ...

    @abstractmethod
    def generate_stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        """Same as generate() but yields text chunks as they arrive.
        Providers without streaming may yield a single chunk — but must
        still raise the same typed errors."""
        ...

    def describe(self) -> str:
        """Human-readable provider description for logs/UI."""
        return f"{type(self).__name__}(model={self.config.model_name}, host={self.config.host})"
