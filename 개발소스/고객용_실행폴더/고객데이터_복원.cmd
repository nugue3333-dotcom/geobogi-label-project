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

set "BACKUP_ZIP=%~1"
if /I "%BACKUP_ZIP%"=="-Quiet" set "BACKUP_ZIP="
if /I "%BACKUP_ZIP%"=="Quiet" set "BACKUP_ZIP="

if "%BACKUP_ZIP%"=="" (
  echo 복원할 백업 ZIP 파일 경로를 입력하세요.
  echo 예: out\chaeumlab_customer_backup_20260708_101500.zip
  set /p BACKUP_ZIP=백업 ZIP 경로: 
)

if "%BACKUP_ZIP%"=="" (
  echo 백업 ZIP 경로가 입력되지 않았습니다.
  if not defined QUIET_ARG pause
  exit /b 1
)

"%~dp0라벨작업실행기.exe" Restore --backup-zip "%BACKUP_ZIP%" -Quiet
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo 고객 데이터 복원에 실패했습니다. 백업 ZIP 경로와 오류 메시지를 확인하세요.
  if not defined QUIET_ARG pause
)
endlocal & exit /b %EXIT_CODE%
