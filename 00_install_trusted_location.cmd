@echo off
setlocal
set "TARGET=%~dp0"

for %%V in (12.0 14.0 15.0 16.0) do (
  reg add "HKCU\Software\Microsoft\Office\%%V\Excel\Security\Trusted Locations\Location99" /v Path /t REG_SZ /d "%TARGET%" /f >nul
  reg add "HKCU\Software\Microsoft\Office\%%V\Excel\Security\Trusted Locations\Location99" /v AllowSubfolders /t REG_DWORD /d 1 /f >nul
  reg add "HKCU\Software\Microsoft\Office\%%V\Excel\Security\Trusted Locations\Location99" /v Description /t REG_SZ /d "Geobok Dream Label Folder" /f >nul
)

echo Excel trusted location registered:
echo %TARGET%
echo.
echo Close Excel completely, then reopen labels.xlsm.
pause
