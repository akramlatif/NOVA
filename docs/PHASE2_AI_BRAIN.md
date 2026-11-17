# NOVA — Phase 2 Documentation: The Local AI Brain

## What was built

```
local_agent/
├── __init__.py               # public surface — import NOVA from here
├── config.py                 # .env-driven settings (model name NOT hardcoded)
├── schemas.py                # Pydantic NovaResponse + safety invariants
├── llm/
│   ├── provider.py           # LLMProvider ABC + typed errors + ChatMessage
│   └── ollama_provider.py    # the local implementation (HTTP via httpx)
├── engine/
│   ├── system_prompt.py      # NOVA's identity & rules (full + compact)
│   └── nova_engine.py        # the brain: chat(), chat_stream(), parser, fallback
└── conversation/
    └── store.py              # SQLite history with context limits
```

## Module responsibilities (loose coupling)

| Module | Knows about | Deliberately knows nothing about |
|---|---|---|
| `llm/provider.py` | message types, errors | Ollama, HTTP, engine, storage |
| `llm/ollama_provider.py` | HTTP, Ollama's API shape | engine logic, schemas, SQLite |
| `conversation/store.py` | SQLite, context limits | LLMs, prompts, intents |
| `schemas.py` | validation rules | where data came from |
| `engine/nova_engine.py` | orchestrates ALL above | never imports httpx directly |

**Replaceability proof:** `NovaEngine.__init__` takes any `LLMProvider`.
Adding a cloud provider later = one new file implementing 3 methods. The
engine, store, and schemas never change.

## The structured response contract

`NovaResponse` (Pydantic, `extra="forbid"`) — exactly the seven master fields:

| Field | Type | Meaning |
|---|---|---|
| `response_type` | enum | conversation / question_answer / action_request / clarification_needed |
| `user_message` | str | the user's original message |
| `detected_intent` | enum | chat / question / action / ambiguous / unknown |
| `requested_action` | str \| null | plain-language action description |
| `required_tools` | list[str] | e.g. `["files", "browser"]` |
| `execution_plan` | list[str] | ordered steps — DATA, never executed by this layer |
| `requires_confirmation` | bool | true for sensitive actions (enforced in code) |

### Safety invariants (in code, not just the prompt)

1. **Sensitive actions force `requires_confirmation=true`** — keyword scan over
   action + plan. A model that says `false` for "delete my files" gets
   overridden.
2. **Conversation-type responses can never carry plans or tools** — normalized
   away.
3. **Unparseable model output falls back to a non-executable response** —
   NOVA asks for clarification rather than guessing.
4. **Nothing in this phase executes anything.** The pipeline returns validated
   data only.

## Context management

- History kept in `data/conversations.db` (SQLite, zero services).
- Two limits: **20 messages** (turns) and **16,000 characters**. When both
   can't be honored, oldest messages drop first — recent context matters most
   for a 3B model on 8 GB RAM.
- `reset_conversation()` clears messages, keeps the id. `delete_conversation()`
  removes everything.

## Configuration (no hardcoded model)

`.env` (copy from `.env.example`):
```
NOVA_LLM_MODEL=llama3.2:3b
NOVA_OLLAMA_HOST=http://127.0.0.1:11434
```
Loaded by `local_agent.config.load_config()`. Changing model = edit `.env`.

## Error taxonomy (all typed, no bare exceptions)

| Error | Meaning | Typical fix |
|---|---|---|
| `LLMConnectionError` | service unreachable | start Ollama |
| `LLMTimeoutError` | exceeded timeout (HDD loads are slow) | retry / raise `NOVA_LLM_TIMEOUT_SECONDS` |
| `LLMModelNotAvailableError` | model not pulled | `ollama pull llama3.2:3b` |
| `LLMResponseFormatError` | provider returned garbage shape | bug report — shouldn't happen |

## Testing

Two tiers, by design:

1. **`pytest`** (no Ollama needed): provider tested via `httpx.MockTransport`,
   engine via a `FakeProvider`. Covers all six master scenarios + safety
   invariants. Runs anywhere, including CI.
2. **`python scripts\verify_ai_brain.py`** (your machine, real Ollama):
   availability, structured conversation, context retention, ambiguity
   handling against the actual local model.

## Phase 2 usage example

```python
from local_agent import NovaEngine, load_config  # load_config via local_agent.config

from local_agent.config import load_config
cfg = load_config()
engine = NovaEngine(config=cfg.llm, data_dir=cfg.data_dir, compact_prompt=True)
conv = engine.store.new_conversation()
response = engine.chat(conv, "What's on my agenda?")
print(response.response_type, response.execution_plan)
```
