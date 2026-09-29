@echo off
chcp 65001 >nul
setlocal
set "TARGET=%~dp0"

set "PS_CMD=powershell.exe"
where pwsh.exe >nul 2>nul && set "PS_CMD=pwsh.exe"
"%PS_CMD%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_chaeumlab_font.ps1" -Quiet
if errorlevel 1 (
  echo 채움랩 기본 글꼴 설치에 실패했습니다.
  exit /b 1
)

for %%V in (12.0 14.0 15.0 16.0) do (
  reg add "HKCU\Software\Microsoft\Office\%%V\Excel\Security\Trusted Locations\Location99" /v Path /t REG_SZ /d "%TARGET%" /f >nul
  reg add "HKCU\Software\Microsoft\Office\%%V\Excel\Security\Trusted Locations\Location99" /v AllowSubfolders /t REG_DWORD /d 1 /f >nul
  reg add "HKCU\Software\Microsoft\Office\%%V\Excel\Security\Trusted Locations\Location99" /v Description /t REG_SZ /d "채움랩 라벨 출력 폴더" /f >nul
)

echo Excel 신뢰할 수 있는 위치를 등록했습니다:
echo %TARGET%
echo 채움랩 기본 글꼴도 현재 사용자 계정에 설치했습니다.
echo.
echo Excel을 완전히 종료한 뒤 labels.xlsm을 다시 여세요.
pause
