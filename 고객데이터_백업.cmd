@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "QUIET_ARG="
if /I "%~1"=="-Quiet" set "QUIET_ARG=1"
if /I "%~1"=="Quiet" set "QUIET_ARG=1"

if not exist "%~dp0라벨작업실행기.exe" (
  echo 라벨작업실행기.exe 파일이 없습니다.
  if not defined QUIET_ARG pause
  exit /b 1
)

"%~dp0라벨작업실행기.exe" Backup -Quiet
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo 고객 데이터 백업에 실패했습니다. out 폴더와 오류 메시지를 확인하세요.
  if not defined QUIET_ARG pause
)
endlocal & exit /b %EXIT_CODE%
