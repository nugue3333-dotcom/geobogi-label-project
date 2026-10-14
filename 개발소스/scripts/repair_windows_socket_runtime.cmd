@echo off
setlocal EnableExtensions

net session >nul 2>&1
if errorlevel 1 (
  echo [ADMIN REQUIRED] Run this file as administrator.
  exit /b 1
)

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "OUT=%ROOT%\out"
if not exist "%OUT%" mkdir "%OUT%"
set "REPORT=%OUT%\network_socket_runtime_repair.cmd.log"

echo [%DATE% %TIME%] Start no-reboot Windows socket and crypto repair > "%REPORT%"
echo [1/5] System file check and repair >> "%REPORT%"
sfc.exe /scannow >> "%REPORT%" 2>&1
echo SFC_EXIT=%ERRORLEVEL% >> "%REPORT%"

echo [2/5] Component store repair >> "%REPORT%"
dism.exe /Online /Cleanup-Image /RestoreHealth >> "%REPORT%" 2>&1
echo DISM_EXIT=%ERRORLEVEL% >> "%REPORT%"

echo [3/5] Refresh cryptographic and proxy services >> "%REPORT%"
net stop CryptSvc /y >> "%REPORT%" 2>&1
net start CryptSvc >> "%REPORT%" 2>&1
net stop WinHttpAutoProxySvc /y >> "%REPORT%" 2>&1
net start WinHttpAutoProxySvc >> "%REPORT%" 2>&1
ipconfig.exe /flushdns >> "%REPORT%" 2>&1

echo [4/5] Reinitialize Ethernet adapter without Windows restart >> "%REPORT%"
netsh.exe interface set interface name="Ethernet" admin=disabled >> "%REPORT%" 2>&1
timeout /t 2 /nobreak >> "%REPORT%" 2>&1
netsh.exe interface set interface name="Ethernet" admin=enabled >> "%REPORT%" 2>&1

echo [5/5] DNS smoke test >> "%REPORT%"
nslookup.exe pypi.org >> "%REPORT%" 2>&1
echo [%DATE% %TIME%] Repair command completed >> "%REPORT%"
type "%REPORT%"
endlocal
