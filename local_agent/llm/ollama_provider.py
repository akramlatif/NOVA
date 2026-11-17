# ==============================================================================
# NOVA — Ollama Provider (Phase 2, Task 1)
# ------------------------------------------------------------------------------
# Implements LLMProvider against the local Ollama HTTP API (default
# http://127.0.0.1:11434). Fully local: no cloud calls, no telemetry.
#
# Endpoints used:
#   GET  /api/tags            -> list installed models (availability check)
#   POST /api/chat            -> conversation with message history
#        (stream:true | false) -> streaming token chunks or full response
#
# All provider-specific details (HTTP, JSON keys, streaming protocol) live
# HERE and nowhere else — that is what keeps the provider replaceable.
# ==============================================================================

from __future__ import annotations

import json
from typing import Iterator, List, Sequence

import httpx

from .provider import (
    ChatMessage,
    LLMConnectionError,
    LLMModelNotAvailableError,
    LLMProvider,
    LLMResponseFormatError,
    LLMTimeoutError,
    ProviderConfig,
)


class OllamaProvider(LLMProvider):
    """Talks to a local Ollama service. Raises typed errors only."""

    # Short timeout for the cheap health/availability calls (service down = fast fail)
    HEALTH_TIMEOUT_SECONDS: float = 5.0

    # ------------------------------------------------------------------ helpers
    def _messages_payload(self, messages: Sequence[ChatMessage]) -> List[dict]:
        """Convert ChatMessage objects to Ollama's expected JSON shape."""
        if not messages:
            raise ValueError("messages must not be empty")
        return [{"role": m.role, "content": m.content} for m in messages]

    def _connect_error(self, exc: Exception) -> LLMConnectionError:
        return LLMConnectionError(
            f"Ollama unreachable at {self.config.host}. "
            f"Start it (Start Menu -> Ollama, or 'ollama serve') and retry. "
            f"Detail: {exc}"
        )

    # ------------------------------------------------------------------ availability
    def is_available(self) -> bool:
        """True iff the service responds AND the configured model is installed."""
        try:
            resp = httpx.get(
                f"{self.config.host}/api/tags",
                timeout=self.HEALTH_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.HTTPError):
            return False

        try:
            installed = {m["name"] for m in resp.json().get("models", [])}
        except (json.JSONDecodeError, KeyError, TypeError):
            return False

        # Ollama may report "llama3.2:3b" exactly, or "llama3.2" (latest tag)
        # normalization — match either the exact name or the base name.
        model = self.config.model_name
        base = model.split(":")[0]
        return model in installed or any(n.split(":")[0] == base for n in installed)

    # ------------------------------------------------------------------ generation
    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Non-streaming generation. Raises typed LLM errors."""
        payload = {
            "model": self.config.model_name,
            "messages": self._messages_payload(messages),
            "stream": False,
        }
        try:
            resp = httpx.post(
                f"{self.config.host}/api/chat",
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except httpx.ConnectTimeout as e:
            raise LLMTimeoutError(
                f"Ollama exceeded {self.config.timeout_seconds}s. "
                f"On HDD/CPU first loads are slow — retry or increase timeout. Detail: {e}"
            ) from e
        except (httpx.ConnectError, httpx.HTTPError) as e:
            raise self._connect_error(e) from e

        # Ollama signals a missing model with HTTP 404
        if resp.status_code == 404:
            raise LLMModelNotAvailableError(
                f"Model '{self.config.model_name}' is not installed. "
                f"Run: ollama pull {self.config.model_name}"
            )
        if resp.status_code >= 400:
            raise LLMConnectionError(
                f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        try:
            body = resp.json()
            content = body["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise KeyError("empty content")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LLMResponseFormatError(
                f"Unexpected Ollama response shape: {e}. Raw: {resp.text[:200]}"
            ) from e
        return content

    # ------------------------------------------------------------------ streaming
    def generate_stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        """Streaming generation — yields text chunks as they arrive.

        Ollama's stream protocol: newline-delimited JSON objects, each with a
        'message' -> 'content' chunk, and done=true on the final object.
        """
        payload = {
            "model": self.config.model_name,
            "messages": self._messages_payload(messages),
            "stream": True,
        }
        try:
            with httpx.stream(
                "POST",
                f"{self.config.host}/api/chat",
                json=payload,
                timeout=self.config.timeout_seconds,
            ) as resp:
                if resp.status_code == 404:
                    raise LLMModelNotAvailableError(
                        f"Model '{self.config.model_name}' is not installed. "
                        f"Run: ollama pull {self.config.model_name}"
                    )
                if resp.status_code >= 400:
                    raise LLMConnectionError(
                        f"Ollama stream failed with HTTP {resp.status_code}."
                    )

                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        piece = chunk.get("message", {}).get("content", "")
                    except json.JSONDecodeError as e:
                        raise LLMResponseFormatError(
                            f"Bad chunk from Ollama stream: {e}. Line: {line[:120]}"
                        ) from e
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        return
        except httpx.ConnectTimeout as e:
            raise LLMTimeoutError(
                f"Ollama stream exceeded {self.config.timeout_seconds}s. Detail: {e}"
            ) from e
        except (httpx.ConnectError, httpx.HTTPError) as e:
            raise self._connect_error(e) from e
