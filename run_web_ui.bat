@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -ExecutionPolicy Bypass -File "%~dp0run_web_ui.ps1"
