@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "QUIET_ARG="
if /I "%~1"=="-Quiet" set "QUIET_ARG=1"
if /I "%~1"=="Quiet" set "QUIET_ARG=1"

set "DESIGNER_EXE=%~dp0라벨디자이너.exe"
set "ICON_SOURCE=%~dp0assets\brand\chaeumlab_label_file_icon_white.ico"
set "LOCAL_APP_DATA=%LOCALAPPDATA%"
if not defined LOCAL_APP_DATA for /f "tokens=3,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v "Local AppData" 2^>nul') do set "LOCAL_APP_DATA=%%B"
if not defined LOCAL_APP_DATA set "LOCAL_APP_DATA=%USERPROFILE%\AppData\Local"
set "ICON_DIR=%LOCAL_APP_DATA%\ChaeumLAB\icons"
set "ICON_PATH="
set "LEGACY_PROG_ID=Geobogi"
set "LEGACY_PROG_ID=%LEGACY_PROG_ID%Dream.LabelFile"

if not exist "%DESIGNER_EXE%" (
  echo 라벨디자이너.exe 파일을 찾을 수 없습니다.
  if not defined QUIET_ARG pause
  exit /b 1
)

if exist "%ICON_SOURCE%" (
  set "ICON_HASH="
  for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%ICON_SOURCE%" SHA256 2^>nul') do if not defined ICON_HASH set "ICON_HASH=%%H"
  set "ICON_HASH=!ICON_HASH: =!"
  set "ICON_HASH=!ICON_HASH:~0,12!"
  if not defined ICON_HASH set "ICON_HASH=fallback"
  set "ICON_PATH=!ICON_DIR!\chaeumlab_label_file_!ICON_HASH!.ico"
  if not exist "%ICON_DIR%" mkdir "%ICON_DIR%" >nul 2>&1
  copy /y "%ICON_SOURCE%" "!ICON_PATH!" >nul
)

if not exist "%ICON_PATH%" (
  set "ICON_PATH=%DESIGNER_EXE%"
)

reg delete "HKCU\Software\Classes\%LEGACY_PROG_ID%" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gblabel\OpenWithProgids" /v "%LEGACY_PROG_ID%" /f >nul 2>&1

reg add "HKCU\Software\Classes\.gblabel" /ve /t REG_SZ /d "ChaeumLAB.LabelFile" /f >nul
if errorlevel 1 goto FAILED

reg add "HKCU\Software\Classes\ChaeumLAB.LabelFile" /ve /t REG_SZ /d "채움랩 라벨 파일" /f >nul
if errorlevel 1 goto FAILED

reg add "HKCU\Software\Classes\ChaeumLAB.LabelFile\DefaultIcon" /ve /t REG_SZ /d "\"%ICON_PATH%\",0" /f >nul
if errorlevel 1 goto FAILED

reg add "HKCU\Software\Classes\ChaeumLAB.LabelFile\shell\open\command" /ve /t REG_SZ /d "\"%DESIGNER_EXE%\" \"%%1\"" /f >nul
if errorlevel 1 goto FAILED

reg add "HKCU\Software\Classes\ChaeumLAB.LabelFile\shell\print\command" /ve /t REG_SZ /d "\"%DESIGNER_EXE%\" --print \"%%1\"" /f >nul
if errorlevel 1 goto FAILED

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gblabel\OpenWithProgids" /v "ChaeumLAB.LabelFile" /t REG_NONE /d "" /f >nul
if errorlevel 1 goto FAILED

set "SYSTEM_ROOT=%SystemRoot%"
if not defined SYSTEM_ROOT set "SYSTEM_ROOT=%WINDIR%"
if not defined SYSTEM_ROOT set "SYSTEM_ROOT=C:\Windows"
if exist "%SYSTEM_ROOT%\System32\ie4uinit.exe" "%SYSTEM_ROOT%\System32\ie4uinit.exe" -show >nul 2>&1

echo .gblabel 저장파일 연결을 등록했습니다.
echo 파일 아이콘: "%ICON_PATH%"
if not defined QUIET_ARG pause
endlocal & exit /b 0

:FAILED
set "EXIT_CODE=%ERRORLEVEL%"
echo .gblabel 저장파일 연결 등록에 실패했습니다.
if not defined QUIET_ARG pause
endlocal & exit /b %EXIT_CODE%
