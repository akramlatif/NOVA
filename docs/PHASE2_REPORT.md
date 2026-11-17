# NOVA — Phase 2 Report

*Format per master instructions §8.*

## 1. What was implemented

- **Ollama integration** — connection manager, model availability checker,
  typed error handling (connection / timeout / model-missing / format),
  streaming and non-streaming generation, injectable HTTP client.
- **AI engine** — receives messages, maintains context, distinguishes
  question vs action via `ResponseType`/`Intent` enums, returns Pydantic-
  validated structured output. Never executes model instructions.
- **System prompt** — full and compact variants: natural communicator, never
  claims execution, asks for clarification on ambiguity, flags sensitive
  actions, never bypasses permissions.
- **Conversation management** — SQLite store: UUID conversations, message
  history, turn + character context limits (oldest dropped first), reset and
  delete. Context survives process restarts.
- **Structured output** — `NovaResponse` with all seven master fields;
  `extra="forbid"` rejects invented fields; safety invariants force
  confirmation on sensitive actions even when the model lies.
- **Provider replaceability** — engine depends only on the abstract
  `LLMProvider`; Ollama is one implementation behind three methods.
- **Config** — model name/host/timeouts from `.env`; nothing hardcoded.

## 2. Files created / modified

| File | Purpose |
|---|---|
| `local_agent/__init__.py` (+ llm/engine/conversation inits) | public package surface |
| `local_agent/llm/provider.py` | abstract provider, typed errors, ChatMessage |
| `local_agent/llm/ollama_provider.py` | local Ollama implementation |
| `local_agent/engine/system_prompt.py` | NOVA identity + hard rules |
| `local_agent/engine/nova_engine.py` | the brain + parser + safe fallback |
| `local_agent/conversation/store.py` | SQLite history + context limits |
| `local_agent/schemas.py` | validated NovaResponse + invariants |
| `local_agent/config.py` | .env-driven configuration |
| `tests/test_ai_brain.py` | full Phase 2 suite |
| `conftest.py` | pytest import bootstrap |
| `scripts/verify_ai_brain.py` | live verification (real Ollama) |
| `docs/PHASE2_AI_BRAIN.md` | architecture + contract docs |
| `requirements.txt` | + pydantic |

## 3. Dependencies installed

Added: `pydantic==2.9.2` (~1 MB). Everything else was already in Phase 1
(httpx, python-dotenv, pytest). Still no ML frameworks — inference is
Ollama's job.

## 4. Tests performed (assistant side)

Unit suite covering all six master scenarios: normal conversation, long
messages (with context trimming), ambiguous instructions, invalid model
responses (prose-wrapped JSON, fenced JSON, garbage), Ollama unavailable
(connection refused → `is_available()` false), model unavailable (404 →
`LLMModelNotAvailableError`), and context retention (history sent with
follow-ups, persistence across store reloads, reset semantics, turn limits).
Plus dedicated safety-invariant tests.

## 5. Test results

**Unit suite: written and self-reviewed; not yet executed — pending your
`pytest` run.** Live behavior against real Ollama is pending
`scripts\verify_ai_brain.py`. Per master rule 14, Phase 2 is NOT declared
working until you paste green results.

## 6. Known issues

- Small local models are inconsistent at emitting clean JSON. The parser is
  deliberately tolerant (fenced/prose-wrapped extraction), and the fallback
  path is safe (clarification, never a fabricated plan). Expect occasional
  fallback responses with `llama3.2:3b`; Phase 3 will tighten the prompt.
- 3B models may misclassify borderline intents. `Intent.UNKNOWN` exists as
  an honest answer; the fallback keeps such cases non-executable.
- First token latency after model load can exceed 30s on the HDD; the 120s
  default timeout accounts for it, and `NOVA_LLM_TIMEOUT_SECONDS` tunes it.

## 7. Security considerations

- Model output is data, never instructions — no execution path exists in
  this phase.
- Sensitive-action keyword scan runs in `model_post_init`, so every
  validated `NovaResponse` is safety-checked even if the model omits it.
- System prompt is static trusted text; conversation history (user data)
  can never overwrite it.
- `.env` (never committed) holds configuration; no secrets in code.
- SQLite file lives under git-ignored `data/`.

## 8. Documentation

`docs/PHASE2_AI_BRAIN.md` (architecture, contract table, error taxonomy,
usage). README roadmap updated: Phase 1 → done pending local verification;
Phase 2 → in progress pending local verification.

## 9. Git checkpoint recommendation

After your local run is green:
```
git tag -a v0.2.0-phase2 -m "Phase 2: local AI brain (Ollama, engine, conversation, schemas)"
```

## 10. Readiness assessment for Phase 3 (Task Planner)

**Design-ready; blocked only on your verification results.** The planner
consumes exactly what this phase produces: `NovaResponse.execution_plan`,
`required_tools`, and `requires_confirmation` — a validated, typed contract.
Phase 3 will add the planner module that turns validated action requests
into checked, ordered, permission-gated steps. No rework expected in this
phase's modules.
