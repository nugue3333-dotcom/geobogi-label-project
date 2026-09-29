@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "QUIET_ARG="
if /I "%~1"=="-Quiet" set "QUIET_ARG=1"
if /I "%~1"=="Quiet" set "QUIET_ARG=1"
if not exist "고객환경점검.exe" (
  echo 고객환경점검.exe 파일이 없습니다.
  if not defined QUIET_ARG pause
  exit /b 1
)
"%~dp0고객환경점검.exe" --base-dir "%CD%"
set CHECK_EXIT=%ERRORLEVEL%
echo.
if "%CHECK_EXIT%"=="0" (
  echo Preflight check completed. Confirm printer settings before real printing.
) else (
  echo Preflight check failed. Review the messages above and run again.
)
if not defined QUIET_ARG pause
exit /b %CHECK_EXIT%
