@echo off
title NOVA Personal AI Assistant
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_desktop.ps1"
pause
