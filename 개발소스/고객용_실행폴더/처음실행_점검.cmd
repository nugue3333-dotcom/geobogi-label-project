@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "QUIET_ARG="
if /I "%~1"=="-Quiet" set "QUIET_ARG=1"
if /I "%~1"=="Quiet" set "QUIET_ARG=1"

echo 채움랩 라벨 출력 패키지 처음 실행 점검
echo.
echo [1/5] 채움랩 기본 글꼴을 설치합니다.
set "PS_CMD=powershell.exe"
where pwsh.exe >nul 2>nul && set "PS_CMD=pwsh.exe"
"%PS_CMD%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_chaeumlab_font.ps1" -Quiet
if errorlevel 1 goto FAILED

echo.
echo [2/5] 고객 PC 실행 전 점검을 실행합니다.
call "%~dp000_고객PC_실행전점검.cmd" -Quiet
if errorlevel 1 goto FAILED

echo.
echo [3/5] .gblabel 저장파일 연결과 아이콘을 등록합니다.
call "%~dp0register_label_filetype.cmd" -Quiet
if errorlevel 1 goto FAILED

echo.
echo [4/5] 프린터 전송 없이 출력 파일 생성 테스트를 실행합니다.
call "%~dp001_output_check.cmd" -Quiet
if errorlevel 1 goto FAILED

echo.
echo [5/5] 현재 설정과 고객 데이터를 백업합니다.
call "%~dp0고객데이터_백업.cmd" -Quiet
if errorlevel 1 goto FAILED

echo.
echo 처음 실행 점검이 완료되었습니다.
echo 다음 단계: 시작하기.cmd settings 로 프린터 설정을 확인한 뒤 라벨출력관리.exe에서 1장 테스트 출력하세요.
if not defined QUIET_ARG pause
endlocal & exit /b 0

:FAILED
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo 처음 실행 점검에 실패했습니다.
echo 위 오류 메시지와 out\customer_preflight_report.txt 파일을 확인하세요.
if not defined QUIET_ARG pause
endlocal & exit /b %EXIT_CODE%
