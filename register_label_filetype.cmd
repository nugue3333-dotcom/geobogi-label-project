@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "QUIET_ARG="
if /I "%~1"=="-Quiet" set "QUIET_ARG=1"
if /I "%~1"=="Quiet" set "QUIET_ARG=1"
if /I "%~3"=="-Quiet" set "QUIET_ARG=1"
set "DESIGNER_EXE=%~dp0라벨디자이너.exe"

if not exist "%DESIGNER_EXE%" (
  echo 라벨디자이너.exe 파일을 찾을 수 없습니다.
  if not defined QUIET_ARG pause
  exit /b 1
)

if /I "%~1"=="rollback" goto RESTORE
"%DESIGNER_EXE%" --register-file-associations
if errorlevel 1 goto FAILED
echo .cllabel / .clproject 및 기존 .gblabel / .gbproject 파일 연결 후보를 등록했습니다.
echo 기존 사용자 기본 앱 선택은 유지됩니다.
echo 변경 전 연결값은 채움랩 사용자 데이터의 file-association 폴더에 보관됩니다.
goto DONE

:RESTORE
if "%~2"=="" (
  echo 사용법: register_label_filetype.cmd rollback "복원기록.json" -Quiet
  if not defined QUIET_ARG pause
  exit /b 1
)
"%DESIGNER_EXE%" --restore-file-associations "%~2"
if errorlevel 1 goto FAILED
echo 채움랩이 변경한 파일 연결값을 복원했습니다.
goto DONE

:FAILED
set "EXIT_CODE=%ERRORLEVEL%"
echo 파일 연결 등록 또는 복원에 실패했습니다. 실행 경로와 연결 복원 기록을 확인하세요.
if not defined QUIET_ARG pause
endlocal & exit /b %EXIT_CODE%

:DONE
if not defined QUIET_ARG pause
endlocal & exit /b 0
