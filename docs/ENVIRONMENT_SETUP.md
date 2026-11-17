# NOVA — Environment Setup Guide (Phase 1)

*Every command explained. Run them one at a time and check the output before moving on.*

This guide targets **Windows 11**, project root **`D:\NOVA`**, and the
constraints: i5-5200U · 8 GB RAM · HDD · no GPU assumed.

---

## 0. Why each tool is needed

| Tool | What NOVA uses it for |
|---|---|
| Python 3.10+ | Core language — the agent, planner, and tools are Python |
| pip | Installs the small dependency set (kept minimal on purpose) |
| Git | Version control — checkpoint after every phase |
| Ollama | Runs the local AI model as its own process (keeps RAM cost out of our code) |
| Node.js / npm | Needed only in Phase 7–8 (React frontend, Tauri desktop) — not required today |

---

## 1. Inspect before installing anything

Open **PowerShell** (Start → type "powershell"). Run:

```powershell
python --version
```
*Shows the Python version. NOVA needs 3.10 or newer (3.11 ideal). If this
errors, Python isn't installed or isn't on PATH.*

```powershell
pip --version
```
*Confirms pip exists and shows which Python it belongs to — make sure it says
Python 3.10+, not an old 2.x or 3.8.*

```powershell
git --version
```
*NOVA needs git ≥ 2.30 for normal clone/push behavior.*

```powershell
node --version ; npm --version
```
*Optional today — a failure here is fine until Phase 7.*

```powershell
ollama --version
```
*If this errors, Ollama isn't installed — that's expected; we handle it in step 3.*

**Automated version of all the above** (also checks RAM, D: free space, and
Windows version):

```powershell
python scripts\verify_environment.py
```
*This is the official Phase 1 inspection script. Run it before AND after setup.
Exit code 0 = all good; 1 = fix the [FAIL] lines first.*

---

## 2. Project folder, clone, virtual environment

```powershell
mkdir D:\NOVA
```
*Creates the project folder. No-op if it already exists.*

```powershell
cd D:\NOVA
git clone https://github.com/akramlatif/NOVA.git .
```
*Clones the repo INTO the current folder (that's what the trailing dot means).
If it complains the directory isn't empty, you may already have files there —
run `git pull` instead, or clone elsewhere and copy.*

```powershell
python -m venv .venv
```
*Creates an isolated Python environment in `D:\NOVA\.venv`. Why: NOVA's
dependencies then never clash with other Python projects on your machine, and
"reinstalling" is always safe because it's contained.*

```powershell
.\.venv\Scripts\Activate.ps1
```
*Activates the venv for this terminal — your prompt changes to `(.venv) ...`.
Everything installed now goes into `.venv`, not the system. If PowerShell
blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
once, which allows local scripts but still blocks unsigned downloads.*

```powershell
python -m pip install --upgrade pip
```
*Upgrades pip inside the venv so installs behave predictably.*

```powershell
pip install -r requirements.txt
```
*Installs NOVA's Phase 1 dependencies: `python-dotenv`, `httpx`, `pytest`.
Deliberately tiny (~2 MB total) — no ML frameworks, because model inference
is Ollama's job, not ours.*

---

## 3. Ollama — install, configure storage on D:, verify

**Run the helper script** (it checks everything first and refuses unsafe installs):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama.ps1
```

What it does, in order:
1. **Skips install if Ollama exists** (rule: never reinstall unnecessarily).
2. Otherwise installs via winget.
3. Sets `OLLAMA_MODELS=D:\NOVA\models` so **model weights land on D:, not C:** —
   this matters on your machine: the C: drive is usually the fuller, faster SSD
   but you asked for models on D:; more importantly the env-var must be set
   BEFORE downloading any model, or weights pile up in
   `C:\Users\<you>\AppData\Local\Ollama` where they're hard to move later.
4. Starts the service if needed and pings `http://127.0.0.1:11434` until it
   responds.
5. **Checks RAM and D: free space before recommending any model** — and exits
   with a clear error if either is insufficient. Per the master rule: *never
   download a large model without checking storage and RAM first.*

### Model recommendation (for 8 GB RAM, no GPU)

| Model | Size | Verdict |
|---|---|---|
| `llama3.2:3b` | ~2.0 GB | **Recommended.** Fast enough on 2 cores, leaves Windows breathing room |
| `qwen2.5:3b` | ~1.9 GB | Strong alternative — better structured output |
| `llama3.1:8b` | ~4.7 GB | **Too heavy** — with Windows 11 (~3 GB) you'd hit the pagefile on an HDD |

**Do not download anything yet.** The model pull (`ollama pull llama3.2:3b`)
belongs to **Phase 2**, after this phase is approved — that keeps Phase 1
verifiable without waiting on a 2 GB download.

---

## 4. Verify everything

```powershell
pytest
```
*Runs NOVA's test suite. Phase 1 ships tests for the environment-inspection
logic so the suite is meaningful from day one.*

```powershell
python scripts\verify_environment.py
```
*Final inspection — every check should print [OK].*

### Expected end state

- ✅ Python 3.10+ inside `.venv`, pip upgraded, deps installed
- ✅ Repo cloned, `main` + phase branches present
- ✅ Ollama installed, `OLLAMA_MODELS` → `D:\NOVA\models`, service responding
- ✅ `pytest` green
- ✅ `verify_environment.py` exit code 0

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry |
| Clone into non-empty dir error | You have files in `D:\NOVA` — `git pull`, or clean the folder first |
| Ollama not responding | Start the Ollama app from Start Menu once, re-run the setup script |
| Python 3.8/3.9 detected | Install 3.11 from python.org, tick "Add to PATH", reopen PowerShell |
| pip too old / weird install errors | `python -m pip install --upgrade pip` inside the venv |
