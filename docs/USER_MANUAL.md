# NOVA — User Manual (v1.0.0)

Welcome to **NOVA** — your personal, privacy-first local AI assistant for Windows 11.

---

## 1. Getting Started

When you launch NOVA, you are presented with the modern desktop interface:
- **Sidebar**: Access Conversations, Task Monitor, Memory Management, Voice Controls, Remote Devices, and Settings.
- **Chat Window**: Enter natural language requests, review execution plans, and view rich markdown responses.
- **Agent Status Indicator**: Displays live CPU and RAM consumption in the top-right header.
- **Voice Bar**: Start/stop voice listening, toggle mute, and view audio activity.

---

## 2. Real-World Task Examples

### A. Web Research & File Downloads
> *"Go to the arXiv website, find recent papers on localized LLM inference, and download the top PDF."*
- NOVA starts Chromium in an isolated sandbox, searches the website, selects the matching publication, and downloads the PDF directly to your sandboxed `Downloads` folder.
- All files are verified with SHA-256 and checked against malicious extensions.

### B. Organizing Your Downloads Folder
> *"Find all PDF files in my Downloads folder and organize them by subject."*
- NOVA inspects the folder, parses metadata and keywords, creates subject folders (e.g., `Research`, `Finance`, `Personal`), and moves matching files safely.

### C. Developer & Desktop Automation
> *"Open VS Code, create a Python project called 'weather_cli', and run the tests."*
- NOVA launches approved applications (e.g. VS Code, Notepad, Calculator), creates project files within your sandboxed directory, and runs test commands via the controlled terminal allowlist.

### D. System Telemetry & Health Checks
> *"How much free RAM and disk space do I have right now?"*
- NOVA queries Windows performance counters and replies with human-readable statistics (e.g., *4.2 GB free of 8.0 GB RAM, 182.4 GB free on C:*).

### E. Remote Tasks from Mobile Phone
> *"From your phone: 'Download this invoice to my laptop.' "*
- Open NOVA's mobile-friendly web dashboard on your phone.
- Enter the 6-character pairing code shown on your laptop.
- Send the instruction: your paired laptop receives the instruction, performs the task, and sends back real-time status updates.

---

## 3. Voice Controls

- **Push-to-Talk**: Click the **Microphone** icon in the bottom bar to begin speaking. Click again to stop.
- **Mute**: Click the **Speaker/Mute** button to silence speech synthesis while retaining visual responses.
- **Consent-Gated Wake Word**: Wake-word detection is disabled by default. You can enable it in **Settings > Voice Settings** with explicit microphone access consent.

---

## 4. Safety & Approval Controls

NOVA is designed to keep you in control:
1. **Approval Dialogs**: Destructive actions (deleting files, overwriting important documents, executing unfamiliar scripts) will automatically trigger a yellow **Approval Required** dialog.
2. **Emergency Stop**: 
   - Click the red **Cancel Task** button in the Task Monitor.
   - Or press the global keyboard shortcut: `Ctrl + Alt + S`.
   - Or quickly fling the mouse cursor to the top-left corner of the primary monitor (`(0, 0)` corner fail-safe).

---

## 5. Memory Management

Access the **Memory** tab from the sidebar:
- **Inspect**: Review all stored facts, user preferences, and project context.
- **Delete**: Remove any specific memory entry or clear all memories with a single click.
- **Privacy Scrubber**: Automatically prevents passwords, API tokens, and SSH keys from being retained in long-term storage.
- **Private Mode**: Toggle **Disable Memory** in Settings to prevent NOVA from reading or recording memories during sensitive sessions.
