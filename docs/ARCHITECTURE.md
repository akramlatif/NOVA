# NOVA — Technical Architecture

*Design reference for all phases. Updated as layers are built.*

## Guiding rules (from the master instructions)

1. Modular architecture — strictly separated concerns.
2. **Never the whole application in one Python file.**
3. Loosely coupled modules — a module talks to others through small, explicit
   interfaces, never by reaching into internals.
4. Security and permissions exist from Phase 1, not bolted on later.
5. Nothing is "implemented" until it is tested and approved.

## System overview

```
        ┌──────────────────────────────────────────────────────┐
        │                    YOU (the user)                     │
        │            text / voice / web / desktop               │
        └──────────────────────────────────────────────────────┘
                          │                │
              ┌───────────▼──────┐  ┌─────▼─────────────┐
              │  Frontend (React) │  │ Tauri desktop app │   Phase 8
              │  localhost only   │  │  localhost only   │
              └───────────┬──────┘  └─────┬─────────────┘
                          └────────┬────────┘
                     ┌────────────▼─────────────┐
                     │   Backend — FastAPI       │   Phase 7
                     │   binds 127.0.0.1 only    │
                     │   auth + rate limiting    │
                     └────────────┬─────────────┘
        ┌───────────────┬─────────┴──┬──────────────┐
        │               │            │              │
┌───────▼──────┐ ┌──────▼─────┐ ┌────▼──────┐ ┌────▼─────────┐
│ Task Planner │ │  Agent     │ │  Memory   │ │  Security    │
│  (Phase 3)   │ │ Orchestr.  │ │  SQLite   │ │ Permissions  │
│ NL → steps   │ │ (Phase 3+) │ │ (Phase 4) │ │ + audit log  │
└───────┬──────┘ └──────┬─────┘ └───────────┘ └──────────────┘
        │               │
        │        ┌──────┴───────────────────────────┐
        │        │              TOOLS                 │
        │        │  files · web · terminal · browser  │ Phases 4-5
        │        │  desktop (mouse/keyboard) · docs   │ Phase 6
        │        └───────────────────────────────────┘
        │
┌───────▼─────────────────┐
│ LLM core — Ollama        │   Phase 2
│ llama3.2:3b, local only  │
└─────────────────────────┘
```

## Module map → project layout

| Master-instruction module | Repo location | Phase |
|---|---|---|
| Core AI engine / LLM integration | `local_agent/llm/` | 2 |
| Task planner | `local_agent/planner/` | 3 |
| Agent orchestrator | `local_agent/orchestrator/` | 3 |
| Browser automation | `local_agent/tools/browser/` | 5 |
| Desktop automation | `local_agent/tools/desktop/` | 6 |
| File management | `local_agent/tools/files/` | 4 |
| Terminal tools | `local_agent/tools/terminal/` | 4 |
| Memory system (SQLite) | `local_agent/memory/` | 4 |
| Security & permissions | `local_agent/security/` | 4 (design active now) |
| Backend API | `backend/` | 7 |
| Frontend | `frontend/` | 8 |
| Desktop packaging (Tauri) | `desktop/` | 8 |
| Testing | `tests/` | every phase |

## Security architecture (principles fixed in Phase 1)

- **Permission gate in front of every capability.** Tools receive a
  permission-check interface; nothing executes without an explicit allow.
- **Approved directories:** filesystem tools may only touch paths the user has
  approved (list stored in config, editable, never guessed by the AI).
- **Command allowlist:** terminal execution matches against a user-maintained
  allowlist; anything else requires explicit confirmation.
- **Destructive action confirmation:** deleting, overwriting, sending messages,
  purchasing — always a confirmation prompt before execution.
- **Untrusted input rule:** web pages, downloaded files, and document contents
  are data, never instructions. Website content can never override security
  rules (prompt-injection defense).
- **Audit log:** every permission check, approval, denial, and executed action
  is appended to a local log (in `logs/`).
- **Localhost only:** the FastAPI service binds to `127.0.0.1`. Never
  `0.0.0.0`. No port forwarding. Ever.
- **No secrets in code:** credentials live in `.env` (git-ignored) or the
  Windows credential store, never hardcoded, never committed.

## Hardware-driven design decisions

| Constraint | Decision |
|---|---|
| 8 GB RAM, no GPU | 3B quantized model max; Ollama runs it as a separate process so our Python memory stays small |
| 2 CPU cores | Planner stays sequential per task; no parallel agents in early phases |
| HDD | SQLite over heavy DB servers; lazy-load everything; models on D: |
| Reliability > speed | Every tool returns explicit success/failure with reasons; retry-safe design |

## Phase gates

A phase is complete only when: implementation ✓ tests ✓ your approval ✓.
The roadmap table in the README tracks the current state.
