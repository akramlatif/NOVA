# ==============================================================================
# NOVA — Desktop Installer Builder (Tauri v2 + React)
# ------------------------------------------------------------------------------
# Builds the React frontend and packages the Windows installer using Tauri.
# ==============================================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   NOVA — Desktop Installer Builder                       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Build React Frontend
Write-Host "[1/3] Building React Frontend Assets with Vite..." -ForegroundColor Yellow
$FrontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $FrontendDir
& npm.cmd run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Frontend build succeeded (output in frontend/dist)." -ForegroundColor Green

# 2. Check Rust & Cargo Toolchain
Write-Host "[2/3] Checking Rust & Cargo for Tauri installer compilation..." -ForegroundColor Yellow
$CargoPath = Get-Command cargo -ErrorAction SilentlyContinue

if ($CargoPath) {
    Write-Host "[OK] Cargo found: $(& cargo --version)" -ForegroundColor Green
    Set-Location (Join-Path $ProjectRoot "desktop\src-tauri")

    Write-Host "[3/3] Compiling Tauri Windows installer (.msi / .exe)..." -ForegroundColor Yellow
    & cargo tauri build
    if ($LASTEXITCODE -eq 0) {
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host "   Installer built successfully! Check:                  " -ForegroundColor Green
        Write-Host "   desktop\src-tauri\target\release\bundle\msi\           " -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Tauri build exited with code $LASTEXITCODE" -ForegroundColor Yellow
    }
} else {
    Write-Host "[NOTICE] Rust & Cargo are not currently installed on this system." -ForegroundColor Yellow
    Write-Host "         The React desktop bundle is completely compiled and ready." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To compile the standalone .msi/.exe installer with Tauri:" -ForegroundColor White
    Write-Host "  1. Install Rust via https://rustup.rs" -ForegroundColor White
    Write-Host "  2. Run 'cargo install tauri-cli'" -ForegroundColor White
    Write-Host "  3. Re-run this script: .\scripts\build_installer.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Meanwhile, you can launch NOVA immediately using:" -ForegroundColor Green
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\run_desktop.ps1" -ForegroundColor Green
}
