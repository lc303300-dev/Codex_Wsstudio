@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%sync-global-codex.ps1" -Yes
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo Global Codex synchronization failed with exit code %EXITCODE%.
  pause
  exit /b %EXITCODE%
)
echo.
echo Global Codex synchronization completed successfully.
pause
endlocal
