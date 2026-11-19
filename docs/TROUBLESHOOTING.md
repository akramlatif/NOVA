# NOVA — Troubleshooting & Diagnostic Guide (v1.0.0)

This guide provides solutions for common issues encountered during setup and operation.

---

## 1. Quick Diagnostics

Run the automated environment and diagnostic check:
```powershell
.\.venv\Scripts\python.exe scripts\verify_environment.py
```
This tests:
- Python version and installed packages
- Ollama availability and loaded model
- Playwright Chromium installation
- SAPI5 audio synthesizer and microphone input
- SQLite memory database integrity

---

## 2. Common Issues & Solutions

### A. Ollama Connection Error (`Cannot connect to 127.0.0.1:11434`)
- **Cause**: Ollama is not running as a local service.
- **Solution**:
  1. Open a terminal and run `ollama serve`.
  2. In another window, check if the model is installed:
     ```powershell
     ollama list
     ```
  3. If `llama3.2:3b` is missing, run:
     ```powershell
     ollama pull llama3.2:3b
     ```

### B. Port 8000 Already in Use
- **Cause**: Another instance of FastAPI or an external service is occupying port 8000.
- **Solution**:
  1. Identify the process holding port 8000:
     ```powershell
     Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
     ```
  2. Terminate the conflicting process or change the port in `backend/main.py` / `scripts/run_desktop.ps1`:
     ```powershell
     .\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8080
     ```

### C. Playwright Chromium Fails to Launch
- **Cause**: Missing browser binaries or slow HDD cold start.
- **Solution**:
  1. Reinstall the Playwright binaries:
     ```powershell
     .\.venv\Scripts\playwright.exe install chromium
     ```
  2. Note that on dual-core mechanical HDDs, initial browser startup may take ~5 seconds. Subsequent page interactions are cached and fast.

### D. Microphone Input Not Recognized (Voice Assistant)
- **Cause**: Windows microphone permissions disabled or invalid default input device.
- **Solution**:
  1. Go to **Windows Settings > Privacy & security > Microphone** and ensure "Let desktop apps access your microphone" is set to **On**.
  2. Verify your default recording device in Windows Sound Settings.
  3. Run the voice diagnostic:
     ```powershell
     .\.venv\Scripts\python.exe -c "from local_agent.voice.controller import VoiceController; c = VoiceController(); print(c.get_status())"
     ```

### E. Device Pairing Code Fails or Expires
- **Cause**: Pairing codes have a strict 5-minute time-to-live (TTL) for security.
- **Solution**:
  1. On your Windows desktop app, click **New Pairing Code**.
  2. Immediately enter the fresh 6-character code (e.g., `NOVA-1234`) on your mobile browser.
  3. Ensure both devices are on the same local network or reachable via your local subnet.

### F. Permission Denied on File Operations
- **Cause**: NOVA's `PathSandbox` strictly confines file creation to approved directories.
- **Solution**:
  - Keep project files inside your workspace root or the user's `Downloads` folder.
  - Operations attempting to write to `C:\Windows\` or system partitions are blocked by design.

---

## 3. Logs & Audit Records

- **Runtime Logs**: `logs/nova.log`
- **Security Audit Trail**: `logs/audit.jsonl`
- **Task History Ledger**: `data/memory.db` (SQLite)
