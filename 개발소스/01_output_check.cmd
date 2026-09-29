@echo off
chcp 65001 >nul
setlocal
set "QUIET_ARG="
if /I "%~1"=="-Quiet" set "QUIET_ARG=-Quiet"
if /I "%~1"=="Quiet" set "QUIET_ARG=-Quiet"
call "%~dp0run_label_job.cmd" DryRun %QUIET_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
