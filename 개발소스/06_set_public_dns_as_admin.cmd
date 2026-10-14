@echo off
setlocal

net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ADMIN REQUIRED]
  echo Right-click this file and choose "Run as administrator".
  echo.
  echo File:
  echo %~f0
  echo.
  pause
  exit /b 1
)

echo.
echo Setting DNS for interface index 12 to Cloudflare and Google DNS.
echo This does not require a Windows restart.
echo.
netsh interface ipv4 set dnsservers name=12 static 1.1.1.1 primary validate=no
if errorlevel 1 goto failed
netsh interface ipv4 add dnsservers name=12 8.8.8.8 index=2 validate=no
if errorlevel 1 goto failed
ipconfig /flushdns

echo.
echo Current DNS configuration:
netsh interface ipv4 show dnsservers name=12
echo.
echo DNS smoke test:
nslookup chatgpt.com
nslookup stitch.googleapis.com
echo.
echo Done. Retry Codex CLI after this window shows successful DNS answers.
pause
exit /b 0

:failed
echo.
echo DNS update failed. Check the error above.
pause
exit /b 1
