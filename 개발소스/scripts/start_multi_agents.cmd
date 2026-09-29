@echo off
setlocal
chcp 65001 >nul
if "%SystemRoot%"=="" set "SystemRoot=C:\Windows"
if "%WINDIR%"=="" set "WINDIR=%SystemRoot%"
if "%SystemDrive%"=="" set "SystemDrive=C:"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_multi_agents.ps1" %*
exit /b %ERRORLEVEL%
