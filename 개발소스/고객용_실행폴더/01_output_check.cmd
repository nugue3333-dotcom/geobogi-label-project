@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_label_job.ps1" -Mode DryRun
endlocal
