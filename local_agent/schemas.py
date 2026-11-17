# ==============================================================================
# NOVA — Structured Response Schemas (Phase 2, Task 5)
# ------------------------------------------------------------------------------
# The validated contract between the AI layer and everything above it.
# Model output is NEVER trusted: it must parse into NovaResponse or the
# engine falls back to safe conversational mode.
#
# Safety invariants enforced HERE (in code, not just the prompt):
#   * requires_confirmation is FORCED true for sensitive actions — even if
#     the model claims otherwise.
#   * execution_plan steps are data, never instructions. Nothing in this
#     file executes anything.
# ==============================================================================

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- enums
class ResponseType(str, Enum):
    """What kind of reply NOVA produced."""
    CONVERSATION = "conversation"          # small talk, general chat
    QUESTION_ANSWER = "question_answer"    # direct informational answer
    ACTION_REQUEST = "action_request"      # user wants something DONE
    CLARIFICATION_NEEDED = "clarification_needed"  # model needs more info


class Intent(str, Enum):
    """High-level intent categories. 'unknown' is a valid, honest answer."""
    CHAT = "chat"
    QUESTION = "question"
    ACTION = "action"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


# Actions that ALWAYS require explicit user confirmation, regardless of what
# the model says. This list mirrors the system prompt's sensitive actions.
SENSITIVE_ACTION_KEYWORDS: frozenset[str] = frozenset({
    "delete", "remove", "overwrite", "format", "uninstall",
    "run", "execute", "command", "terminal", "cmd", "powershell",
    "send", "message", "email", "whatsapp", "telegram",
    "purchase", "payment", "buy", "pay", "checkout",
    "password", "credential", "login", "token", "secret",
    "settings", "config", "registry", "admin", "sudo",
    "install", "download", "upload",
})


class NovaResponse(BaseModel):
    """The ONLY structure NOVA's engine returns to callers.

    All seven master-specified fields, validated:
      response_type, user_message, detected_intent, requested_action,
      required_tools, execution_plan, requires_confirmation
    """
    model_config = {"extra": "forbid"}  # reject invented fields

    response_type: ResponseType
    user_message: str = Field(..., description="The user's original message")
    detected_intent: Intent = Intent.UNKNOWN
    requested_action: Optional[str] = Field(
        None, description="Plain-language description of the action, if any"
    )
    required_tools: List[str] = Field(
        default_factory=list,
        description="Tool categories the plan needs, e.g. ['files', 'browser']",
    )
    execution_plan: List[str] = Field(
        default_factory=list,
        description="Ordered steps as DATA — executed only after user approval",
    )
    requires_confirmation: bool = False

    # ------------------------------------------------------------- validators
    @field_validator("user_message")
    @classmethod
    def _message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_message must not be empty")
        return v.strip()

    @field_validator("execution_plan")
    @classmethod
    def _plan_steps_not_empty(cls, v: List[str]) -> List[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        return cleaned

    def model_post_init(self, __context) -> None:
        """Enforce safety invariants AFTER the model's raw values are loaded."""
        # Force confirmation for sensitive actions — the model cannot opt out.
        if self._mentions_sensitive_action():
            self.requires_confirmation = True

        # An action request without a plan is not executable — but it is still
        # a valid response (the model may need to clarify first). We only
        # normalize contradictory states:
        if self.response_type == ResponseType.CONVERSATION:
            # Conversation never requires confirmation or tools
            self.required_tools = []
            self.execution_plan = []
            self.requires_confirmation = False
        if self.response_type == ResponseType.CLARIFICATION_NEEDED:
            # Clarifications must not carry executable plans
            self.execution_plan = []

    def _mentions_sensitive_action(self) -> bool:
        """True if the action or plan text touches a sensitive keyword."""
        text = " ".join(
            [self.requested_action or ""] + self.execution_plan
        ).lower()
        return any(k in text for k in SENSITIVE_ACTION_KEYWORDS)


# --------------------------------------------------------------------------- fallback
class ConversationFallback(BaseModel):
    """Safe response when the model's structured output is unusable.

    If the model returns garbage, NOVA still answers — as plain conversation
    with NO action attached. Failing safe = no execution.
    """
    response_type: ResponseType = ResponseType.CONVERSATION
    user_message: str
    detected_intent: Intent = Intent.UNKNOWN
    requested_action: None = None
    required_tools: List[str] = []
    execution_plan: List[str] = []
    requires_confirmation: bool = False
