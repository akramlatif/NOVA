# NOVA — Personal AI Computer Assistant

NOVA is a **local-first** personal AI assistant for Windows 11 that understands
natural-language instructions and performs real-world tasks on your own computer
and through a web interface — with explicit permissions and security from day one.

> **Status: Phase 11 — Security, Testing and Optimization.**
> NOVA is built phase by phase. Nothing is marked done until it is tested and approved.

## What NOVA is being built to do (eventually)

Understand natural-language instructions · plan multi-step tasks · open and
navigate websites · search online · download and organize files · control
approved Windows applications · use mouse/keyboard when needed · read and
create documents · run approved terminal commands · remember preferences ·
communicate through text and voice · operate through desktop and web interfaces.

**One capability at a time.** Nothing ships until the previous layer is built,
tested, and approved.

## Hardware target & design consequences

| Item | Value | Consequence for design |
|---|---|---|
| CPU | Intel Core i5-5200U (2 cores / 4 threads) | Small models; reliability over speed |
| RAM | 8 GB | 3B-parameter quantized models maximum |
| Storage | HDD, project on D: | Models and data live on `D:\NOVA`; first loads are slow |
| GPU | Not assumed | CPU-only quantized inference (Ollama) |
| OS | Windows 11 | Desktop automation will use Windows APIs |

## Technology stack (planned)

| Layer | Technology | Status |
|---|---|---|
| AI runtime | Ollama | Phase 1–2 |
| Core language | Python 3.10+ | Phase 1 |
| Backend | FastAPI | Phase 9 |
| Frontend | React | Phase 10 |
| Desktop shell | Tauri | Phase 10 |
| Database | SQLite | Phase 2 (conversations), Phase 7 (memory) |

## Project structure

```
D:\NOVA\
├── backend\        # FastAPI service                    (Phase 7)
├── frontend\       # React web UI                      (Phase 8)
├── desktop\        # Tauri desktop shell                (Phase 8)
├── local_agent\    # NOVA's brain: LLM, planner, tools  (Phases 2-6)
├── docs\           # Setup and architecture guides
├── scripts\        # Developer helper scripts
├── tests\          # Pytest test suite
├── models\         # Ollama model storage   (contents git-ignored)
├── data\           # SQLite DBs, user data  (contents git-ignored)
└── logs\           # Runtime + audit logs   (contents git-ignored)
```

## Quick start (Windows 11)

Full guide with every command explained: **[docs/ENVIRONMENT_SETUP.md](docs/ENVIRONMENT_SETUP.md)**

```powershell
cd D:\
git clone https://github.com/akramlatif/NOVA.git
cd NOVA
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest                                   # run the test suite
python scripts\verify_environment.py    # inspect your machine
python scripts\verify_ai_brain.py       # Phase 2: live AI brain check (needs Ollama)
```

## The local AI brain (Phase 2)

```python
from local_agent import NovaEngine
from local_agent.config import load_config

cfg = load_config()
engine = NovaEngine(config=cfg.llm, data_dir=cfg.data_dir, compact_prompt=True)
conv = engine.store.new_conversation()
response = engine.chat(conv, "What's on my agenda?")
# response: NovaResponse (Pydantic-validated, 7 fields, safety-checked)
```

Details: **[docs/PHASE2_AI_BRAIN.md](docs/PHASE2_AI_BRAIN.md)**

## Security principles (active from Phase 1)

- Explicit permissions for every capability — nothing runs "by default."
- Filesystem access restricted to approved directories only.
- Command allowlists; confirmation required before destructive actions.
- Website content and downloaded files are always treated as untrusted.
- Website content can never override system security rules.
- The control service binds to localhost only — never exposed to the internet.
- Every security-relevant action goes to an audit log.
- No API keys or passwords are ever hardcoded or committed.
- **Model output is data, never instructions** — the AI brain cannot execute anything.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Environment setup, project foundation, verification tooling | **Approved** ✅ |
| 2 | Ollama LLM core, local conversation loop, structured responses | **Approved** ✅ |
| 3 | Task planner, tool registry, and execution orchestrator | **Approved** ✅ |
| 4 | Browser automation agent, safe download manager, web interaction | **Approved** ✅ |
| 5 | Desktop automation (mouse/keyboard, window control, approved apps) | **Approved** ✅ |
| 6 | File and system management agent, document support, system monitor | **Approved** ✅ |
| 7 | Persistent memory system (SQLite, short/long-term, privacy scrubber) | **Approved** ✅ |
| 8 | Voice assistant (SAPI5 TTS, speech recognition, wake-word consent gate) | **Approved** ✅ |
| 9 | Windows desktop application & local backend (React, Tauri, FastAPI) | **Approved** ✅ |
| 10 | Web dashboard and secure remote access (WebSockets, Device Pairing) | **Approved** ✅ |
| 11 | Security assessment, threat modeling, and performance benchmarks | **Approved** ✅ |
| 12 | Final integration, end-to-end scenarios, release v1.0.0 packaging | **Implemented & Tested** 🟢 |

## Documentation Suite (v1.0.0)

- **[Architecture & Subsystem Breakdown](docs/ARCHITECTURE.md)**
- **[Installation & Setup Guide](docs/INSTALLATION.md)**
- **[User Manual & Workflow Guide](docs/USER_MANUAL.md)**
- **[API Reference (REST & WebSockets)](docs/API_DOCUMENTATION.md)**
- **[Security Policy & STRIDE Assessment](docs/SECURITY.md)**
- **[Hardware Benchmarking & Optimization](docs/PERFORMANCE_BENCHMARK.md)**
- **[Configuration & Environment Guide](docs/CONFIGURATION.md)**
- **[Troubleshooting & Diagnostics](docs/TROUBLESHOOTING.md)**
- **[Backup & Recovery Procedures](docs/BACKUP_AND_RECOVERY.md)**
- **[v1.0.0 Release Notes](docs/RELEASE_NOTES_v1.0.0.md)**

## License

Private, personal project of @akramlatif. All rights reserved.
