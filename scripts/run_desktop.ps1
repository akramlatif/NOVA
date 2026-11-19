# ==============================================================================
# NOVA — Desktop Application Launcher (Windows 11)
# ------------------------------------------------------------------------------
# Starts the localhost-only FastAPI backend service and opens the NOVA desktop UI.
# ==============================================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   NOVA — Personal AI Computer Assistant Launcher         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Virtual Environment
$PythonVenv = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonVenv)) {
    Write-Host "[ERROR] Virtual environment not found at $PythonVenv" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv; pip install -r requirements.txt"
    exit 1
}

# 2. Check if Backend is already responding
$BackendUrl = "http://127.0.0.1:8000/api/health"
$BackendRunning = $false
try {
    $res = Invoke-RestMethod -Uri $BackendUrl -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($res.status -eq "ok") {
        $BackendRunning = $true
        Write-Host "[OK] NOVA Backend is already running on port 8000" -ForegroundColor Green
    }
} catch {
    $BackendRunning = $false
}

# 3. Start Backend if not running
if (-not $BackendRunning) {
    Write-Host "[*] Starting NOVA FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
    $BackendProcess = Start-Process -FilePath $PythonVenv `
        -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $ProjectRoot `
        -PassThru -WindowStyle Hidden

    Start-Sleep -Seconds 3
    Write-Host "[OK] Backend server started (PID: $($BackendProcess.Id))" -ForegroundColor Green
}

# 4. Launch Desktop Webview / App
$AppUrl = "http://127.0.0.1:8000/"
Write-Host "[*] Launching NOVA Desktop Application window ($AppUrl)..." -ForegroundColor Cyan

# Check if Tauri release binary exists
$TauriExe = Join-Path $ProjectRoot "desktop\src-tauri\target\release\nova-desktop.exe"
if (Test-Path $TauriExe) {
    Write-Host "[OK] Starting Tauri native desktop binary..." -ForegroundColor Green
    Start-Process -FilePath $TauriExe
} else {
    # Launch via Windows Edge App Mode (Chromium/WebView2 native window with no browser address bar)
    $EdgePaths = @(
        "$env:ProgramFiles (x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    $EdgeExe = $EdgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($EdgeExe) {
        Write-Host "[OK] Opening native desktop app frame via Microsoft Edge WebView..." -ForegroundColor Green
        Start-Process -FilePath $EdgeExe -ArgumentList "--app=$AppUrl", "--window-size=1280,840"
    } else {
        Start-Process $AppUrl
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   NOVA is now running! Enjoy your local AI assistant.    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
