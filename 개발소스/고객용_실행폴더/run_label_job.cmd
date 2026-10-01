@echo off
chcp 65001 >nul
setlocal
set "MODE=%~1"
if "%MODE%"=="" (
  echo Missing mode.
  exit /b 1
)
set "QUIET_ARG="
if /I "%~2"=="-Quiet" set "QUIET_ARG=-Quiet"
if /I "%~2"=="Quiet" set "QUIET_ARG=-Quiet"

if exist "%~dp0라벨작업실행기.exe" goto RUN_WITH_LABEL_JOB_RUNNER

set "PS_CMD="
where pwsh.exe >nul 2>nul
if not errorlevel 1 set "PS_CMD=pwsh.exe"

if not defined PS_CMD (
  if defined SystemRoot set "PS_CMD=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
)

if not defined PS_CMD set "PS_CMD=powershell.exe"

"%PS_CMD%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_label_job.ps1" -Mode "%MODE%" %QUIET_ARG%
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo PowerShell failed. Error code: %EXIT_CODE%
  echo Check that this folder is in a writable location and PowerShell can run.
  if not defined QUIET_ARG pause
)

endlocal & exit /b %EXIT_CODE%

:RUN_WITH_LABEL_JOB_RUNNER
"%~dp0라벨작업실행기.exe" "%MODE%" %QUIET_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" (
  endlocal & exit /b 0
)
echo.
echo Label job runner failed. Error code: %EXIT_CODE%
echo Check last_run.log or run 00_고객PC_실행전점검.cmd.
if not defined QUIET_ARG pause
endlocal & exit /b %EXIT_CODE%
