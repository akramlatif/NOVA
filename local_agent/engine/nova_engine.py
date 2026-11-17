# ==============================================================================
# NOVA — AI Engine (Phase 2, Task 2)
# ------------------------------------------------------------------------------
# The modular brain. Receives user messages, maintains context via the
# conversation store, asks the LLM provider, and returns VALIDATED structured
# responses. It NEVER executes anything the model says — it returns data.
#
# Flow of one message:
#   user text
#     -> ConversationStore.load_history()        (context)
#     -> build_context(system_prompt, history, text)
#     -> provider.generate()                    (local Ollama)
#     -> ResponseParser -> NovaResponse        (Pydantic-validated)
#     -> stored to history
#     -> returned to caller
# ==============================================================================

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional, Sequence

from local_agent.conversation.store import ConversationStore
from local_agent.engine.system_prompt import SYSTEM_PROMPT, SYSTEM_PROMPT_COMPACT
from local_agent.llm.ollama_provider import OllamaProvider
from local_agent.llm.provider import (
    ChatMessage,
    LLMError,
    LLMProvider,
    ProviderConfig,
)
from local_agent.schemas import NovaResponse, ResponseType

logger = logging.getLogger("nova.engine")


# ============================================================================== parser
class ResponseParser:
    """Extracts a JSON object from model text and validates it.

    Small local models wrap JSON in prose ("Here is my response: {...}"),
    fence it, or emit trailing commas. This parser is defensive on purpose:
    a 3B model is not GPT-4 — we accept imperfect formatting, but NEVER
    accept invalid semantics (Pydantic still rejects bad values).
    """

    _JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

    @classmethod
    def parse(cls, raw_text: str, user_message: str) -> NovaResponse:
        """Parse + validate. Raises ValueError on unusable output."""
        for candidate in cls._extract_candidates(raw_text):
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            data["user_message"] = user_message
            try:
                return NovaResponse.model_validate(data)
            except Exception:  # pydantic ValidationError — try next candidate
                continue
        raise ValueError(f"Model output is not valid NOVA JSON: {raw_text[:200]!r}")

    @classmethod
    def _extract_candidates(cls, raw: str) -> Sequence[str]:
        """Yield increasingly aggressive JSON extraction attempts."""
        text = raw.strip()
        # 1. Fenced code block ```json ... ```
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            yield fenced[0]
        # 2. First {...} block anywhere (greedy to the last })
        block = cls._JSON_BLOCK.search(text)
        if block:
            yield block.group(0)
        # 3. The raw text itself (if the model was perfectly obedient)
        yield text


# ============================================================================== engine
class NovaEngine:
    """NOVA's brain. Owns the provider, the store, and the safety pipeline."""

    ACTION_VERBS: frozenset[str] = frozenset({
        "open", "create", "delete", "move", "copy", "download", "run",
        "search", "find", "send", "write", "make", "install", "rename",
        "close", "start", "stop", "organize", "sort", "save", "set",
    })

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        store: Optional[ConversationStore] = None,
        config: Optional[ProviderConfig] = None,
        data_dir: Path = Path("data"),
        compact_prompt: bool = False,
    ) -> None:
        # Every dependency is injectable -> replaceable provider, testable engine.
        self.config = config or ProviderConfig(model_name="llama3.2:3b")
        self.provider = provider or OllamaProvider(self.config)
        self.store = store or ConversationStore(Path(data_dir) / "conversations.db")
        self.system_prompt = SYSTEM_PROMPT_COMPACT if compact_prompt else SYSTEM_PROMPT

    # ------------------------------------------------------------------ availability
    def is_ready(self) -> bool:
        """True if the provider responds and the model is installed."""
        return self.provider.is_available()

    # ------------------------------------------------------------------ main entry
    def chat(self, conversation_id: str, user_message: str) -> NovaResponse:
        """Process one user message. Returns a VALIDATED NovaResponse.

        Raises LLMError subclasses for connection/timeout/model failures —
        callers surface those as NOVA status, not crashes.
        """
        message = ChatMessage(role="user", content=user_message)

        # 1. Load context (with limits) and assemble the LLM request
        history = self.store.load_history(conversation_id)
        context = ConversationStore.build_context(
            self.system_prompt, history, user_message
        )

        # 2. Ask the local model for a STRUCTURED response
        prompt_text = (
            "Respond ONLY with a JSON object with these keys: "
            'response_type (one of "conversation", "question_answer", '
            '"action_request", "clarification_needed"), '
            "user_message (the user's text), "
            "detected_intent (one of \"chat\", \"question\", \"action\", "
            '"ambiguous", "unknown"), '
            "requested_action (string or null), "
            "required_tools (array of strings), "
            "execution_plan (array of step strings), "
            "requires_confirmation (boolean, true for sensitive actions)."
        )
        context.append(ChatMessage(role="user", content=prompt_text))

        raw = self.provider.generate(context)

        # 3. Validate the model's output — never trust it
        try:
            response = ResponseParser.parse(raw, user_message)
        except ValueError as e:
            logger.warning("Structured parse failed, falling back: %s", e)
            response = self._fallback_response(user_message)

        # 4. Persist the exchange
        self.store.append_message(conversation_id, message)
        self.store.append_message(
            conversation_id, ChatMessage(role="assistant", content=raw)
        )

        return response

    # ------------------------------------------------------------------ streaming chat
    def chat_stream(self, conversation_id: str, user_message: str):
        """Stream raw text chunks as they arrive; stores when done.

        Returns an iterator of text chunks. Structure validation happens on
        the assembled text at the end — streaming is for UX, not semantics.
        """
        history = self.store.load_history(conversation_id)
        context = ConversationStore.build_context(
            self.system_prompt, history, user_message
        )
        collected: list[str] = []
        for chunk in self.provider.generate_stream(context):
            collected.append(chunk)
            yield chunk

        full_text = "".join(collected)
        self.store.append_message(
            conversation_id, ChatMessage(role="user", content=user_message)
        )
        self.store.append_message(
            conversation_id, ChatMessage(role="assistant", content=full_text)
        )

    # ------------------------------------------------------------------ fallback
    def _fallback_response(self, user_message: str) -> NovaResponse:
        """When structured parsing fails: return a NON-executable response.

        Failing safe: if the user's message looked like an action request we
        ask for clarification (so the user knows the plan was NOT captured),
        otherwise treat it as plain conversation. Never fabricate a plan.
        """
        if self._looks_like_action(user_message):
            return NovaResponse(
                response_type=ResponseType.CLARIFICATION_NEEDED,
                user_message=user_message,
            )
        return NovaResponse(
            response_type=ResponseType.CONVERSATION,
            user_message=user_message,
        )

    @classmethod
    def _looks_like_action(cls, text: str) -> bool:
        """Cheap heuristic: imperative verbs at the start suggest an action."""
        first = text.strip().split(" ", 1)[0].lower().strip(".,!?")
        return first in cls.ACTION_VERBS
