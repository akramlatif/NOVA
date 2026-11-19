# NOVA — Installation & Setup Guide (v1.0.0)

This guide walks you through setting up and running **NOVA** on a Windows 11 machine (optimized for dual-core Intel/AMD CPUs, 8 GB RAM, and local mechanical HDD or SSD).

---

## 1. System Requirements

### Minimum Requirements:
- **Operating System**: Windows 11 (or Windows 10 64-bit Build 19044+)
- **Processor**: Dual-Core x64 CPU (e.g., Intel Core i5-5200U @ 2.20 GHz or AMD equivalent)
- **RAM**: 8.0 GB RAM
- **Disk Space**: 10 GB free storage (includes Ollama 3B model weights ~2.4 GB)
- **Display**: 1280 x 720 minimum resolution

### Recommended Requirements:
- **Processor**: Quad-Core x64 CPU or higher
- **RAM**: 16.0 GB RAM
- **Storage**: Solid State Drive (SSD) for sub-second cold starts

---

## 2. Software Prerequisites

Ensure the following tools are installed on your machine:
1. **Python 3.10+ (tested through Python 3.14)**:
   - Download from [python.org](https://www.python.org/downloads/)
   - *Important*: Check "Add Python to PATH" during installation.
2. **Node.js 18+ & npm**:
   - Download from [nodejs.org](https://nodejs.org/) (LTS recommended)
3. **Ollama (Local LLM Server)**:
   - Download from [ollama.com](https://ollama.com/download/windows)
4. **Rust & Cargo (Optional — only required if compiling standalone Tauri `.msi` installers)**:
   - Download from [rustup.rs](https://rustup.rs/)

---

## 3. Step-by-Step Installation

### Step 1: Clone the Repository
```powershell
git clone https://github.com/akramlatif/NOVA.git
cd NOVA
```

### Step 2: Configure Python Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install core dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browser binaries for web automation
playwright install chromium
```

### Step 3: Pull the Local Ollama Model
```powershell
# Run the automated Ollama setup script
powershell -ExecutionPolicy Bypass -File .\scripts\setup_ollama.ps1

# Or manually start Ollama and pull the recommended 3B model:
ollama pull llama3.2:3b
```

### Step 4: Build Frontend Assets
```powershell
cd frontend
npm install
npm run build
cd ..
```

---

## 4. Launching NOVA

NOVA can be launched in multiple modes depending on your workflow:

### Mode A: Complete Desktop Application (FastAPI + React Desktop)
Double-click `scripts\NOVA_Desktop.bat` or run:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_desktop.ps1
```
This script:
1. Validates Python environment and dependencies.
2. Starts the local FastAPI backend on `http://127.0.0.1:8000`.
3. Launches the React desktop dashboard in an isolated application window.

### Mode B: Standalone Backend Server (For Web Dashboard & Remote Access)
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open your browser and navigate to `http://localhost:8000` to access the interactive web dashboard and API docs (`/docs`).

### Mode C: Voice Assistant Mode
In the desktop dashboard, click the microphone button or call the voice flow programmatically:
```powershell
.\.venv\Scripts\python.exe -c "from local_agent.voice.controller import VoiceController; v = VoiceController(); v.speak_text('NOVA is online.')"
```

---

## 5. Verifying the Installation

To verify that all subsystems are functioning correctly, run the full test suite:
```powershell
.\.venv\Scripts\pytest -q
```
Expected output:
```text
237 passed in ~4 minutes (100% pass rate)
```
