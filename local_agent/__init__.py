# NOVA local_agent — the AI brain package.
#
# Public surface (import from local_agent, not deep modules):
#   NovaEngine            - the brain (chat, chat_stream, is_ready)
#   LLMProvider          - abstract provider contract (for future providers)
#   OllamaProvider        - the local Ollama implementation
#   ProviderConfig       - connection settings
#   ChatMessage          - immutable message record
#   ConversationStore    - SQLite-backed history
#   NovaResponse & enums - validated structured output

from local_agent.conversation.store import ConversationStore
from local_agent.engine.nova_engine import NovaEngine
from local_agent.llm.ollama_provider import OllamaProvider
from local_agent.llm.provider import (
    ChatMessage,
    LLMConnectionError,
    LLMError,
    LLMModelNotAvailableError,
    LLMProvider,
    LLMResponseFormatError,
    LLMTimeoutError,
    ProviderConfig,
)
from local_agent.schemas import Intent, NovaResponse, ResponseType

__all__ = [
    "NovaEngine",
    "OllamaProvider",
    "LLMProvider",
    "ProviderConfig",
    "ChatMessage",
    "LLMError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMModelNotAvailableError",
    "LLMResponseFormatError",
    "ConversationStore",
    "NovaResponse",
    "ResponseType",
    "Intent",
]

__version__ = "0.2.0"
