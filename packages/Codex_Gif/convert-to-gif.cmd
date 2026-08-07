@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-video-to-gif.ps1" %*
exit /b %ERRORLEVEL%
