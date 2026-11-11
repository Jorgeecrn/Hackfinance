@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" iniciar_demo.py %*
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    python iniciar_demo.py %*
  ) else (
    py -3 iniciar_demo.py %*
  )
)
set RESULTADO=%ERRORLEVEL%
if not "%RESULTADO%"=="0" pause
exit /b %RESULTADO%
