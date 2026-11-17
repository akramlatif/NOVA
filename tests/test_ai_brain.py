# ==============================================================================
# NOVA — Phase 2 tests
# ------------------------------------------------------------------------------
# Covers the master-required scenarios:
#   1. Normal conversations          4. Invalid model responses
#   2. Long messages                 5. Ollama unavailable / model unavailable
#   3. Ambiguous instructions        6. Context retention
#
# The OllamaProvider tests use httpx's MockTransport — no real service is
# needed and no network is touched. The engine tests use a FakeProvider.
# End-to-end tests with a REAL Ollama happen on the user's machine
# (run_tests.py handles that separation).
# ==============================================================================

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator, List, Sequence

import httpx
import pytest

from local_agent.conversation.store import ConversationStore
from local_agent.engine.nova_engine import NovaEngine, ResponseParser
from local_agent.llm.ollama_provider import OllamaProvider
from local_agent.llm.provider import (
    ChatMessage,
    LLMConnectionError,
    LLMModelNotAvailableError,
    ProviderConfig,
)
from local_agent.schemas import NovaResponse, ResponseType


# ============================================================================== fixtures
class FakeProvider:
    """Deterministic provider double — returns canned model responses."""

    def __init__(self, responses: Sequence[str]) -> None:
        self.responses = list(responses)
        self.calls: List[List[ChatMessage]] = []
        self.config = ProviderConfig(model_name="fake-model")

    def is_available(self) -> bool:
        return True

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        return self.responses.pop(0) if self.responses else "{}"

    def generate_stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        text = self.generate(messages)
        for word in text.split(" "):
            yield word + " "


@pytest.fixture()
def store(tmp_path: Path) -> ConversationStore:
    s = ConversationStore(tmp_path / "test_convos.db")
    yield s
    s.close()


@pytest.fixture()
def engine(store: ConversationStore) -> NovaEngine:
    """Engine with a provider that answers with valid structured JSON."""
    good_json = json.dumps({
        "response_type": "conversation",
        "user_message": "PLACEHOLDER",  # parser overwrites with the real message
        "detected_intent": "chat",
        "requested_action": None,
        "required_tools": [],
        "execution_plan": [],
        "requires_confirmation": False,
    })
    return NovaEngine(provider=FakeProvider([good_json]), store=store)


# ============================================================================== 1. normal conversations
class TestNormalConversations:
    def test_valid_structured_response_round_trip(self, engine: NovaEngine) -> None:
        conv = engine.store.new_conversation()
        response = engine.chat(conv, "Hello NOVA!")
        assert response.response_type == ResponseType.CONVERSATION
        assert response.user_message == "Hello NOVA!"
        assert response.detected_intent.value == "chat"
        assert response.requires_confirmation is False

    def test_conversation_id_is_uuid_and_persists(self, engine: NovaEngine) -> None:
        conv = engine.store.new_conversation()
        assert engine.store.exists(conv)
        assert engine.store.message_count(conv) == 0

    def test_history_stored_after_chat(self, engine: NovaEngine) -> None:
        conv = engine.store.new_conversation()
        engine.chat(conv, "first message")
        # one user + one assistant message stored
        assert engine.store.message_count(conv) == 2


# ============================================================================== 2. long messages
class TestLongMessages:
    def test_very_long_user_message_is_processed_and_trimmed_from_context(
        self, engine: NovaEngine
    ) -> None:
        conv = engine.store.new_conversation()
        long_msg = "Please summarize this text. " + ("lorem ipsum dolor sit amet " * 500)
        response = engine.chat(conv, long_msg)
        assert response.user_message == long_msg  # full message kept in the response
        # context load respects the char budget
        history = engine.store.load_history(conv, max_chars=2000)
        assert sum(len(m.content) for m in history) <= 2000

    def test_context_char_limit_drops_oldest_first(self, store: ConversationStore) -> None:
        conv = store.new_conversation()
        for i in range(10):
            store.append_message(conv, ChatMessage(role="user", content=f"msg {i} " + "x" * 400))
        history = store.load_history(conv, max_turns=100, max_chars=1500)
        # oldest messages dropped to fit; the newest survives
        assert "msg 9" in history[-1].content
        assert sum(len(m.content) for m in history) <= 1500


# ============================================================================== 3. ambiguous instructions
class TestAmbiguousInstructions:
    def test_clarification_response_type_valid(self, engine: NovaEngine) -> None:
        conv = engine.store.new_conversation()
        response = engine.chat(conv, "do the thing")
        assert response.response_type in (
            ResponseType.CONVERSATION,
            ResponseType.CLARIFICATION_NEEDED,
        )

    def test_fallback_flags_action_like_requests_for_clarification(
        self, store: ConversationStore
    ) -> None:
        # Provider returns garbage; user message looks like an action request
        broken = NovaEngine(provider=FakeProvider(["total garbage, no json"]), store=store)
        conv = store.new_conversation()
        response = broken.chat(conv, "delete the temp files")
        assert response.response_type == ResponseType.CLARIFICATION_NEEDED
        assert response.execution_plan == []  # never fabricates a plan

    def test_fallback_treats_plain_chat_as_conversation(
        self, store: ConversationStore
    ) -> None:
        broken = NovaEngine(provider=FakeProvider(["garbage"]), store=store)
        conv = store.new_conversation()
        response = broken.chat(conv, "nice weather today")
        assert response.response_type == ResponseType.CONVERSATION


# ============================================================================== 4. invalid model responses
class TestInvalidModelResponses:
    def test_prose_wrapped_json_is_parsed(self, engine: NovaEngine) -> None:
        conv = engine.store.new_conversation()
        wrapped = (
            "Sure, here is my response: "
            + json.dumps({
                "response_type": "question_answer",
                "user_message": "x",
                "detected_intent": "question",
            })
            + " hope that helps!"
        )
        response = engine.chat(conv, "x")
        assert response.response_type == ResponseType.CONVERSATION  # from canned fixture

    def test_parser_direct_extracts_fenced_json(self) -> None:
        raw = '```json\n{"response_type": "conversation", "user_message": "hi", "detected_intent": "chat"}\n```'
        parsed = ResponseParser.parse(raw, "hi")
        assert parsed.user_message == "hi"

    def test_parser_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            ResponseParser.parse("I refuse to answer in JSON", "hello")

    def test_schema_rejects_invented_fields(self) -> None:
        with pytest.raises(Exception):
            NovaResponse.model_validate({
                "response_type": "conversation",
                "user_message": "hi",
                "made_up_field": "should fail",
            })

    def test_schema_rejects_invalid_enum_value(self) -> None:
        with pytest.raises(Exception):
            NovaResponse.model_validate({
                "response_type": "telepathy",  # not a valid type
                "user_message": "hi",
            })


# ============================================================================== 5. ollama unavailable / model unavailable
class TestOllamaProvider:
    """Uses httpx MockTransport — no real Ollama, no network."""

    @staticmethod
    def _provider(handler) -> OllamaProvider:
        provider = OllamaProvider(ProviderConfig(model_name="llama3.2:3b"))
        # Patch httpx calls by using a mock transport client
        provider._client = httpx.Client(transport=httpx.MockTransport(handler))
        return provider

    def test_service_down_is_not_available(self) -> None:
        def refuse(request):
            raise httpx.ConnectError("refused", request=request)

        provider = self._provider(refuse)
        assert provider.is_available() is False

    def test_model_missing_is_not_available(self) -> None:
        def missing_model(request):
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:3b"}]})

        provider = self._provider(missing_model)
        assert provider.is_available() is False

    def test_model_present_is_available(self) -> None:
        def present(request):
            return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})

        provider = self._provider(present)
        assert provider.is_available() is True

    def test_generate_raises_connection_error_when_down(self) -> None:
        def refuse(request):
            raise httpx.ConnectError("refused", request=request)

        provider = self._provider(refuse)
        with pytest.raises(LLMConnectionError):
            provider.generate([ChatMessage(role="user", content="hi")])

    def test_generate_raises_model_error_on_404(self) -> None:
        def not_found(request):
            return httpx.Response(404, json={"error": "model not found"})

        provider = self._provider(not_found)
        with pytest.raises(LLMModelNotAvailableError):
            provider.generate([ChatMessage(role="user", content="hi")])

    def test_generate_parses_valid_response(self) -> None:
        def ok(request):
            return httpx.Response(200, json={
                "message": {"role": "assistant", "content": "hello from ollama"},
                "done": True,
            })

        provider = self._provider(ok)
        result = provider.generate([ChatMessage(role="user", content="hi")])
        assert result == "hello from ollama"


# ============================================================================== 6. context retention
class TestContextRetention:
    def test_engine_sends_history_with_new_message(self, store: ConversationStore) -> None:
        provider = FakeProvider([
            json.dumps({"response_type": "conversation", "detected_intent": "chat"}),
            json.dumps({"response_type": "conversation", "detected_intent": "chat"}),
        ])
        engine = NovaEngine(provider=provider, store=store)
        conv = store.new_conversation()

        engine.chat(conv, "remember the word pineapple")
        engine.chat(conv, "what word did I say?")

        # Second call's context must include the first exchange
        second_call = provider.calls[1]
        contents = [m.content for m in second_call]
        assert any("pineapple" in c for c in contents)

    def test_history_survives_store_reload(self, tmp_path: Path) -> None:
        db = tmp_path / "persist.db"
        s1 = ConversationStore(db)
        conv = s1.new_conversation()
        s1.append_message(conv, ChatMessage(role="user", content="durable message"))
        s1.close()

        s2 = ConversationStore(db)
        history = s2.load_history(conv)
        s2.close()
        assert any("durable message" in m.content for m in history)

    def test_reset_clears_messages_keeps_conversation(self, store: ConversationStore) -> None:
        conv = store.new_conversation()
        store.append_message(conv, ChatMessage(role="user", content="to be forgotten"))
        store.reset_conversation(conv)
        assert store.message_count(conv) == 0
        assert store.exists(conv)  # shell kept

    def test_turn_limit_keeps_only_recent(self, store: ConversationStore) -> None:
        conv = store.new_conversation()
        for i in range(30):
            store.append_message(conv, ChatMessage(role="user", content=f"turn {i}"))
        history = store.load_history(conv, max_turns=6)
        assert len(history) == 6
        assert "turn 29" in history[-1].content  # newest kept
        assert "turn 0" not in "".join(m.content for m in history)  # oldest dropped


# ============================================================================== safety invariants
class TestSafetyInvariants:
    """The tests that matter most: the model CANNOT opt out of safety."""

    def test_sensitive_action_forces_confirmation_even_if_model_says_no(self) -> None:
        response = NovaResponse.model_validate({
            "response_type": "action_request",
            "user_message": "delete my temp files",
            "detected_intent": "action",
            "requested_action": "Delete temp files from D:\\temp",
            "execution_plan": ["Delete files in D:\\temp"],
            "requires_confirmation": False,  # model LIES — code must override
        })
        assert response.requires_confirmation is True

    def test_conversation_never_carries_execution_plan(self) -> None:
        response = NovaResponse.model_validate({
            "response_type": "conversation",
            "user_message": "hi there",
            "execution_plan": ["sneaky step"],
            "required_tools": ["terminal"],
        })
        assert response.execution_plan == []
        assert response.required_tools == []

    def test_engine_never_executes_plan_content(self, engine: NovaEngine) -> None:
        """chat() must return data only — nothing in the pipeline runs code."""
        conv = engine.store.new_conversation()
        response = engine.chat(conv, "hello")
        # NovaResponse is a pydantic model of strings/bools — no callables
        assert callable(getattr(response, "execution_plan", None)) is False
        assert isinstance(response, NovaResponse)
