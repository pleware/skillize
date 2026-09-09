@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0skillize.ps1" %*
exit /b %ERRORLEVEL%
