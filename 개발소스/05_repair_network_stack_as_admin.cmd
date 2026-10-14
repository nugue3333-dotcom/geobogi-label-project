@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ADMIN REQUIRED]
  echo Right-click this file and choose "Run as administrator".
  echo.
  echo File:
  echo %~f0
  echo.
  pause
  exit /b 1
)

echo.
echo Starting Windows Winsock/IP/DNS repair.
echo Public DNS will be set to 1.1.1.1 and 8.8.8.8 on Ethernet.
echo Restart Windows after this command completes.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\repair_windows_network_stack.ps1" -Apply -SetPublicDns
set EXIT_CODE=%ERRORLEVEL%
echo.
if not "%EXIT_CODE%"=="0" (
  echo Repair command failed. Check the error above.
  pause
  exit /b %EXIT_CODE%
)
echo Repair command completed. Restart Windows, then retry Codex CLI.
pause
