@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if /I "%~1"=="help" goto HELP
if /I "%~1"=="first-run" goto FIRST_RUN
if /I "%~1"=="check" goto CHECK
if /I "%~1"=="output-check" goto OUTPUT_CHECK
if /I "%~1"=="print" goto PRINT
if /I "%~1"=="settings" goto SETTINGS
if /I "%~1"=="manager" goto MANAGER
if /I "%~1"=="designer" goto DESIGNER
if /I "%~1"=="backup" goto BACKUP
if /I "%~1"=="restore" goto RESTORE
if /I "%~1"=="version" goto VERSION
if /I "%~1"=="quick-manual" goto QUICK_MANUAL
if /I "%~1"=="manual" goto MANUAL
if /I "%~1"=="file-association" goto FILE_ASSOCIATION
if /I "%~1"=="folder" goto FOLDER
if /I "%~1"=="menu" goto MENU
if /I "%~1"=="quit" exit /b 0
if not "%~1"=="" goto UNKNOWN

goto MANAGER

:MENU
cls
echo 채움랩 라벨 출력 패키지 시작 메뉴
echo.
echo  1. 처음 실행 점검
echo  2. 실행 전 점검
echo  3. 프린터 설정
echo  4. 라벨 출력 관리
echo  5. 라벨 디자이너
echo  6. 출력 파일 생성 테스트
echo  7. 고객 데이터 백업
echo  8. 고객 데이터 복원
echo  9. 버전 정보 보기
echo  10. 빠른 사용안내 열기
echo  11. 상세 매뉴얼 열기
echo  12. 저장파일 연결 등록
echo  13. 현재 폴더 열기
echo  14. 종료
echo.
set /p MENU_CHOICE=번호를 선택하세요: 
if "%MENU_CHOICE%"=="1" goto FIRST_RUN
if "%MENU_CHOICE%"=="2" goto CHECK
if "%MENU_CHOICE%"=="3" goto SETTINGS
if "%MENU_CHOICE%"=="4" goto MANAGER
if "%MENU_CHOICE%"=="5" goto DESIGNER
if "%MENU_CHOICE%"=="6" goto OUTPUT_CHECK
if "%MENU_CHOICE%"=="7" goto BACKUP
if "%MENU_CHOICE%"=="8" goto RESTORE
if "%MENU_CHOICE%"=="9" goto VERSION
if "%MENU_CHOICE%"=="10" goto QUICK_MANUAL
if "%MENU_CHOICE%"=="11" goto MANUAL
if "%MENU_CHOICE%"=="12" goto FILE_ASSOCIATION
if "%MENU_CHOICE%"=="13" goto FOLDER
if "%MENU_CHOICE%"=="14" exit /b 0
echo.
echo 잘못된 번호입니다.
pause
goto MENU

:HELP
echo 채움랩 라벨 출력 패키지 시작 메뉴
echo.
echo 사용법:
echo   시작하기.cmd
echo   시작하기.cmd first-run
echo   시작하기.cmd check
echo   시작하기.cmd output-check
echo   시작하기.cmd settings
echo   시작하기.cmd manager
echo   시작하기.cmd designer
echo   시작하기.cmd backup
echo   시작하기.cmd restore
echo   시작하기.cmd version
echo   시작하기.cmd quick-manual
echo   시작하기.cmd manual
echo   시작하기.cmd file-association
echo   시작하기.cmd folder
echo   시작하기.cmd menu
exit /b 0

:FIRST_RUN
call "%~dp0처음실행_점검.cmd" -Quiet
goto AFTER_ACTION

:CHECK
call "%~dp000_고객PC_실행전점검.cmd" -Quiet
goto AFTER_ACTION

:OUTPUT_CHECK
call "%~dp001_output_check.cmd" -Quiet
goto AFTER_ACTION

:PRINT
call "%~dp002_print_labels.cmd" -Quiet
goto AFTER_ACTION

:SETTINGS
start "" "%~dp0프린터설정.exe"
exit /b 0

:MANAGER
start "" "%~dp0라벨출력관리.exe"
exit /b 0

:DESIGNER
start "" "%~dp0라벨디자이너.exe"
exit /b 0

:BACKUP
call "%~dp0고객데이터_백업.cmd"
goto AFTER_ACTION

:RESTORE
call "%~dp0고객데이터_복원.cmd"
goto AFTER_ACTION

:VERSION
if exist "%~dp0버전정보.txt" (
  type "%~dp0버전정보.txt"
  goto AFTER_ACTION
)
echo 버전정보.txt 파일을 찾을 수 없습니다.
exit /b 1

:QUICK_MANUAL
if exist "%~dp0사용안내.txt" (
  start "" "%~dp0사용안내.txt"
  exit /b 0
)
echo 사용안내.txt 파일을 찾을 수 없습니다.
exit /b 1

:MANUAL
if exist "%~dp0라벨출력패키지_고객용_매뉴얼.docx" (
  start "" "%~dp0라벨출력패키지_고객용_매뉴얼.docx"
  exit /b 0
)
if exist "%~dp0설치_및_사용_메뉴얼.txt" (
  start "" "%~dp0설치_및_사용_메뉴얼.txt"
  exit /b 0
)
echo 상세 매뉴얼 파일을 찾을 수 없습니다.
exit /b 1

:FILE_ASSOCIATION
call "%~dp0register_label_filetype.cmd" -Quiet
goto AFTER_ACTION

:FOLDER
start "" "%~dp0"
exit /b 0

:UNKNOWN
echo 알 수 없는 명령입니다: %~1
echo.
goto HELP

:AFTER_ACTION
set "ACTION_EXIT=%ERRORLEVEL%"
if not "%~1"=="" exit /b %ACTION_EXIT%
echo.
pause
goto MENU
