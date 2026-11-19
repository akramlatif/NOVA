# NOVA — Configuration Guide (v1.0.0)

NOVA uses configuration files, sensible environment defaults, and code registries to manage settings.

---

## 1. Environment Variables

Create a `.env` file in the project root to override defaults:

```ini
# --- Core Environment ---
NOVA_ENV=production
NOVA_DEBUG=false
NOVA_DATA_DIR=data
NOVA_LOG_LEVEL=INFO

# --- Backend & Server ---
NOVA_SERVER_HOST=127.0.0.1
NOVA_SERVER_PORT=8000
NOVA_JWT_SECRET=generate_a_random_32_byte_hex_secret_here
NOVA_JWT_TTL_SECONDS=3600
NOVA_RATE_LIMIT_REQUESTS=60
NOVA_RATE_LIMIT_WINDOW_SECONDS=60

# --- LLM Engine (Ollama) ---
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL_NAME=llama3.2:3b
OLLAMA_REQUEST_TIMEOUT=60.0
OLLAMA_TEMPERATURE=0.2

# --- Security Sandboxing ---
NOVA_ALLOWED_ROOTS=.,Downloads,data
NOVA_MAX_OUTPUT_BYTES=51200
NOVA_MAX_DOWNLOAD_BYTES=52428800

# --- Voice Settings ---
NOVA_TTS_RATE=175
NOVA_TTS_VOLUME=1.0
NOVA_VOICE_MUTED=false
NOVA_WAKEWORD_ENABLED=false
```

---

## 2. Application Allowlist (`local_agent/desktop/apps.py`)

NOVA maintains an approved registry of desktop applications that it is authorized to launch.

Default approved applications:
- **`notepad`**: Windows built-in text editor (`notepad.exe`)
- **`calculator`**: Windows Calculator (`calc.exe`)
- **`explorer`**: Windows File Explorer (`explorer.exe`)
- **`terminal`**: Windows Terminal (`wt.exe` — requires explicit user approval)
- **`cmd`**: Command Prompt (`cmd.exe` — requires explicit user approval)
- **`vscode`**: Visual Studio Code (`Code.exe`)
- **`chrome`**: Google Chrome (`chrome.exe`)

To add an application to the allowlist in your own scripts:
```python
from local_agent.desktop.apps import AppManager, AppSpec

manager = AppManager()
manager.register_app("blender", AppSpec(
    name="Blender 3D",
    exe_path=r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    description="3D modeling software",
    requires_approval=False,
))
```

---

## 3. Terminal Command Allowlist (`local_agent/security/terminal.py`)

To prevent arbitrary code execution, only allowlisted CLI binaries may be invoked:
- Approved: `dir`, `echo`, `type`, `git`, `python`, `py`, `pytest`, `where`, `whoami`, `hostname`, `ver`
- Prohibited patterns: `format`, `del /s`, `rmdir /s`, `reg`, `powershell -enc`, `Invoke-Expression`, `shutdown`, `net user`, `diskpart`

---

## 4. Path Sandboxing (`local_agent/security/paths.py`)

All file read/write operations must be contained within `allowed_roots`:
- Attempting to access paths outside these roots (e.g. `C:\Windows\System32`) raises `SecurityError`.
- Directory traversal sequences (`..\..`) are resolved and rejected automatically.
