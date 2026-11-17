# ==============================================================================
# NOVA — Ollama setup helper (Phase 1, Task 3)
# ------------------------------------------------------------------------------
# Purpose:
#   1. Installs Ollama via winget if it is not already present.
#   2. Sets OLLAMA_MODELS so model weights are stored on D:\NOVA\models
#      (per the rule: keep AI models on D:, not C:).
#   3. Verifies the Ollama service responds.
#   4. Recommends a model sized to detected RAM — and REFUSES to download
#      anything if storage or RAM headroom is insufficient.
#
# Usage (PowerShell, from D:\NOVA, as needed):
#   powershell -ExecutionPolicy Bypass -File scripts\setup_ollama.ps1
#
# Safety:
#   - Installs nothing if Ollama already exists (no unnecessary reinstalls).
#   - Downloads no model without a RAM/storage check (master rule).
# ==============================================================================

param(
    [switch]$SkipInstall,   # set to only configure/verify, never install
    [string]$ModelsDir = "$PSScriptRoot\..\models"
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------ config
$ModelsDir = (Resolve-Path -Path $ModelsDir -ErrorAction SilentlyContinue)
if (-not $ModelsDir) {
    $ModelsDir = [System.IO.Path]::GetFullPath("$PSScriptRoot\..\models")
}
$MinFreeDiskGB = 10
$MinRamGB = 6

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }

# ------------------------------------------------------------------ 1. install check
Write-Step "Step 1/4: Checking whether Ollama is already installed..."

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $ver = (ollama --version) 2>$null | Select-Object -First 1
    Write-Ok "Ollama already installed: $ver"
    Write-Warn "Skipping installation (rule: never reinstall existing software)."
}
elseif ($SkipInstall) {
    Write-Warn "Ollama not installed and -SkipInstall was set — stopping here."
    exit 1
}
else {
    Write-Step "Step 1/4: Installing Ollama with winget..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Fail "winget not available. Download Ollama from https://ollama.com/download/windows then re-run this script."
        exit 1
    }
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "winget install failed. Install manually from ollama.com and re-run."
        exit 1
    }
    # Refresh PATH so this session can see the new install
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Ok "Ollama installed."
}

# ------------------------------------------------------------------ 2. model storage on D:
Write-Step "Step 2/4: Configuring model storage on D: ..."

if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
    Write-Ok "Created $ModelsDir"
}

# Set for this session AND persist for the user account
$env:OLLAMA_MODELS = $ModelsDir
[System.Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $ModelsDir, "User")
Write-Ok "OLLAMA_MODELS = $ModelsDir (set for session and persisted for user)"
Write-Host "        NOTE: already-downloaded models on C: will not move automatically."
Write-Host "        If ollama list shows nothing after this, restart Ollama from the"

# ------------------------------------------------------------------ 3. service check
Write-Step "Step 3/4: Verifying the Ollama service responds..."

# Start the app/service if it is not running (first launch takes a moment on HDD)
$ollamaProc = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    Write-Host "  Ollama not running — starting it (first start on HDD can take ~30s)..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 8
}

$serviceOk = $false
foreach ($attempt in 1..5) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { $serviceOk = $true; break }
    } catch { Start-Sleep -Seconds 3 }
}
if ($serviceOk) {
    Write-Ok "Ollama service is responding at http://127.0.0.1:11434"
} else {
    Write-Fail "Ollama service not responding. Start the Ollama app from the Start Menu, then re-run this script."
    exit 1
}

# ------------------------------------------------------------------ 4. RAM/storage-gated model recommendation
Write-Step "Step 4/4: Checking RAM and storage before recommending a model..."

$os = Get-CimInstance Win32_OperatingSystem
$totalRamGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeRamGB  = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$modelsDrive = (Get-Item (Split-Path $ModelsDir -Parent)).PSDrive.Name
if (-not $modelsDrive) { $modelsDrive = (Get-Item $ModelsDir).PSDrive.Name }
$freeDiskGB = [math]::Round((Get-PSDrive $modelsDrive).Free / 1GB, 1)

Write-Host "        RAM:   ${freeRamGB} GB free of ${totalRamGB} GB"
Write-Host "        $($modelsDrive): free: ${freeDiskGB} GB (model storage drive)"

if ($totalRamGB -lt $MinRamGB) {
    Write-Fail "Only ${totalRamGB} GB total RAM — running a local model alongside Windows 11 is unsafe. Aborting; consider a cloud API instead."
    exit 1
}
if ($freeDiskGB -lt $MinFreeDiskGB) {
    Write-Fail "Only ${freeDiskGB} GB free on ${modelsDrive}: — not enough for models plus growth. Free space first."
    exit 1
}

Write-Ok "Sufficient RAM and disk. Recommended model: llama3.2:3b (~2 GB)"
Write-Host "        It fits safely in 8 GB RAM with Windows 11 running."
Write-Host ""
Write-Host "        When you are ready (Phase 2), download it with:"
Write-Host "            ollama pull llama3.2:3b"
Write-Host "        Expect roughly 5-15 minutes on an HDD connection — the download"
Write-Host "        is one-time; after that it loads from D:\NOVA\models."
exit 0
