# NOVA — Technical Architecture (v1.0.0)

*Authoritative architectural specification for NOVA v1.0.*

---

## 1. Architectural Principles

NOVA is built under six foundational engineering principles:

1. **Local-First Privacy**: Model inference, memories, credentials, and task history reside exclusively on the user's local disk. No telemetry, third-party analytics, or cloud relays.
2. **Strict Separation of Concerns**: Modular decoupled layers. Subsystems interact exclusively via explicit schemas, registry interfaces, and dependency injection.
3. **Defense-in-Depth Sandboxing**: Tool execution is bounded by default. Destructive operations require human confirmation; commands and binaries run under strict allowlists; file operations are confined by path sandboxes.
4. **8 GB RAM Constraint Optimization**: Lightweight Python core (~42 MB RSS), zero heavy daemons, ephemeral browser pooling, and memory-mapped SQLite storage.
5. **Human-in-the-Loop Supervision**: Automated tasks pause in `waiting_for_approval` state for sensitive actions (file deletions, system reboots, external network posts).
6. **Graceful Degradation & Resilience**: Offline-first design. Database rollbacks prevent task corruption, and background operations provide timeout fail-safes.

---

## 2. System Architecture Diagram

```text
                  ┌────────────────────────────────────────────────────────┐
                  │                    USER INTERACTION                     │
                  │        Voice (SAPI5)  •  Desktop UI  •  Remote Phone   │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │            FastAPI LOCAL BACKEND (8000)       │
                      │  • REST Endpoints    • WebSocket Broadcasts   │
                      │  • Device Pairing    • Sliding-Rate Limiter   │
                      │  • HMAC-SHA256 Auth  • Security Audit Logger  │
                      └───────────────────────┬───────────────────────┘
                                              │
       ┌──────────────────────────────────────┼──────────────────────────────────────┐
       │                                      │                                      │
┌──────▼─────────────────────┐  ┌─────────────▼──────────────┐  ┌────────────────────▼───────┐
│        AI BRAIN            │  │      TASK PLANNER          │  │     PERSISTENT MEMORY      │
│ • Ollama (llama3.2:3b)     │  │ • Natural Language → Steps │  │ • SQLite (Zero-daemon)     │
│ • NovaEngine (Validation)  │  │ • DAG Dependency Planner   │  │ • Short-Term Active Task   │
│ • JSON Schema Strictness   │  │ • Confirmation Enforcement │  │ • Long-Term Prefs & Facts  │
│ • Prompt Injection Defense │  │ • Human Approval Gates     │  │ • Privacy Credential Scrub │
└──────────────┬─────────────┘  └─────────────┬──────────────┘  └────────────────────┬───────┘
               │                              │                                      │
               └──────────────────────┬───────┴──────────────────────────────────────┘
                                      │
                       ┌──────────────▼──────────────┐
                       │      AGENT ORCHESTRATOR     │
                       │ • Tool Registry             │
                       │ • Execution State Machine   │
                       │ • Task Cancellation Ledger  │
                       │ • Audit Trail Generator     │
                       └──────────────┬──────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┬──────────────────────────────┐
       │                              │                              │                              │
┌──────▼───────────────┐  ┌───────────▼────────────┐  ┌─────────────▼────────────┐  ┌───────────────▼──────────────┐
│   BROWSER AGENT      │  │    DESKTOP AGENT       │  │    FILE & SYSTEM AGENT   │  │       VOICE ASSISTANT        │
│ • Playwright Engine  │  │ • PyAutoGUI Controller │  │ • PathSandbox Confinement│  │ • SAPI5 Local TTS Synthesis  │
│ • Download Manager   │  │ • AppManager Allowlist │  │ • Multi-Doc Parser       │  │ • Local Speech Recognizer    │
│ • Ephemeral Profile  │  │ • ScreenObserver       │  │ • Download Organizer     │  │ • Wake-word Consent Gate     │
│ • SHA-256 Validator  │  │ • Visual Feedback      │  │ • Controlled Terminal    │  │ • Audio Device Controller    │
└──────────────────────┘  └────────────────────────┘  └──────────────────────────┘  └──────────────────────────────┘
```

---

## 3. Subsystem Breakdown

### 3.1 AI Brain & Inference Engine (`local_agent/engine/`, `local_agent/llm/`)
- **Ollama Provider**: Manages local HTTP communication with `http://127.0.0.1:11434`. Defaults to `llama3.2:3b` at 4-bit quantization (Q4_K_M).
- **NovaEngine**: Synthesizes system instructions, active workspace context, and persistent memories into structured requests. Validates responses through Pydantic schemas (`NovaResponse`).
- **Prompt Injection Guard**: Strips executable tool plans from conversational outputs and forces confirmation on sensitive payloads.

### 3.2 Task Planner & Agent Orchestrator (`local_agent/tasks/`)
- **TaskPlanner**: Deconstructs user intent into a multi-step directed acyclic graph (`TaskPlan`).
- **AgentOrchestrator**: Executes steps sequentially, captures runtime tool results, handles failures, and respects user cancellations.
- **ToolRegistry**: Manages tool registration across 5 domains (`web`, `desktop`, `filesystem`, `system`, `voice`), tagging each tool with a `PermissionLevel` (`SAFE`, `NORMAL`, `SENSITIVE`).

### 3.3 Browser Automation Agent (`local_agent/browser/`)
- **BrowserController**: Drives Chromium via Playwright in headless mode. Supports page navigation, screenshot capture, DOM inspection, and text extraction.
- **DownloadManager**: Enforces an allowed extension allowlist (`.pdf`, `.csv`, `.docx`, etc.), prevents directory traversal, and computes SHA-256 digests.

### 3.4 Windows Desktop Automation Agent (`local_agent/desktop/`)
- **AppManager**: Maintains an explicit allowlist of authorized desktop applications (`notepad`, `calculator`, `explorer`, `terminal`, `vscode`, `chrome`).
- **DesktopController**: Automates mouse navigation, keyboard input, and hotkeys via PyAutoGUI.
- **ScreenObserver**: Captures regional and full-screen screenshots for visual verification.
- **DesktopSecurity**: Enforces fail-safe boundaries, pauses for user approval, and handles emergency stop (`Ctrl+Alt+S` / mouse corner fling).

### 3.5 File & System Management Agent (`local_agent/system/`)
- **PathSandbox**: Enforces boundary containment inside approved project roots and downloads directories. Prevents path traversal (`../../`).
- **FileManager**: Implements CRUD, copying, moving, renaming, and SHA-256 duplicate detection.
- **DocumentProcessor**: Extracts and parses `.txt`, `.pdf`, `.docx`, `.xlsx`, `.csv`, and `.md`.
- **DownloadOrganizer**: Sorts files into classified folders by file type, project, date, or subject keyword rules.
- **SystemMonitor**: Collects live CPU, RAM, disk, and process telemetry using `psutil`.
- **ControlledTerminal**: Executes CLI commands with an allowlist (`dir`, `echo`, `git status`, `python --version`, etc.) with `shell=False`.

### 3.6 Persistent Memory System (`local_agent/memory/`)
- **MemoryStore**: SQLite database with WAL journaling and zero background daemons. Tables: `users`, `conversations`, `messages`, `preferences`, `memories`, `tasks`, `task_steps`.
- **MemoryManager**: Manages short-term conversation context, long-term facts/preferences, and past task lessons.
- **PrivacyScrubber**: Scans text for high-entropy secrets, passwords, RSA private keys, and LLM project tokens (`sk-proj-...`), redacting them before storage.

### 3.7 Voice Assistant (`local_agent/voice/`)
- **TextToSpeechEngine**: Zero-latency local synthesis using Windows SAPI5 (`pyttsx3`). Supports custom rates, volume, voice selection, and audio file export.
- **SpeechRecognizer**: Speech-to-text integration with energy-threshold microphone calibration.
- **VoiceController**: Coordinates recording, mute toggling, listening state, and UI visual indicators.
- **WakeWordDetector**: Explicit consent-gated wake-word detection preventing unauthorized background recording.

### 3.8 Backend & Web Remote Access (`backend/`)
- **FastAPI Core**: Local REST and WebSocket server running on `http://127.0.0.1:8000`.
- **TokenManager**: Issues short-lived PBKDF2-HMAC-SHA256 tokens with 1-hour expiration.
- **DeviceManager**: Manages mutual cryptographic device pairing (6-character code with 5-minute TTL) allowing authorized web browsers or mobile devices to dispatch tasks.
- **AuditLogger**: Append-only security audit log tracking all auth attempts, task dispatches, and sensitive executions.

---

## 4. Resource Allocation & Hardware Footprint

Designed specifically for an 8.0 GB RAM / Dual-Core Windows 11 machine:

| Component | RAM Working Set (RSS) | CPU Consumption (Idle) | Storage Footprint |
|---|---|---|---|
| **NOVA Core (Python + FastAPI)** | ~41.95 MB | < 0.2% | ~35 MB (excl venv) |
| **Ollama LLM (llama3.2:3b Q4)** | ~2,400 MB | 0% (evaluates on-demand) | ~2.4 GB |
| **Desktop Webview / React UI** | ~65 MB | < 0.5% | ~8 MB (compiled dist) |
| **Playwright Chromium (On-Demand)** | ~150 MB (when active) | 0% (closed when idle) | ~180 MB |
| **Windows 11 OS Baseline** | ~3,800 MB | ~2 - 5% | - |
| **Total Peak Working Set** | **~6.46 GB** | **Headroom > 1.5 GB** | **Total Disk ~5.5 GB** |
