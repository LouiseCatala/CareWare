@echo off
setlocal
cd /d "%~dp0"
where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo Windows PowerShell was not found. CareWare setup needs Windows PowerShell 5.1.
    pause
    exit /b 1
)
start "CareWare Setup" powershell.exe -NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0SETUP.ps1"
exit /b 0
