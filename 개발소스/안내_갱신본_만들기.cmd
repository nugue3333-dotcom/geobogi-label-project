@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo 사용법: 안내_갱신본_만들기.cmd "새 출력 폴더" [--apply]
  echo 기본 실행은 파일을 쓰지 않는 dry-run입니다.
  exit /b 2
)
if not exist ".venv\Scripts\python.exe" (
  echo 개발용 Python 환경 .venv\Scripts\python.exe가 필요합니다.
  exit /b 1
)
set "MODE_ARG=--dry-run"
if /I "%~2"=="--apply" set "MODE_ARG=--apply"
if not "%~2"=="" if /I not "%~2"=="--apply" if /I not "%~2"=="--dry-run" (
  echo 두 번째 인수는 --apply 또는 --dry-run만 사용할 수 있습니다.
  exit /b 2
)
if not "%~3"=="" (
  echo 인수는 출력 폴더와 실행 모드만 지정하세요.
  exit /b 2
)
".venv\Scripts\python.exe" -m barcode_label_automation.customer_guide_package --customer-dir ".\고객용_실행폴더" --guides-dir "." --output-dir "%~1" %MODE_ARG%
exit /b %ERRORLEVEL%
