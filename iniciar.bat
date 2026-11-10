@echo off
rem Banco Demo (con Centinela) - doble clic para arrancar la demo en Windows.
rem La primera vez prepara todo (tarda un par de minutos); despues arranca en segundos.
chcp 65001 >nul
cd /d "%~dp0"
set PORT=8000
set URL=http://localhost:%PORT%/

echo Banco Demo (con Centinela)
echo.

rem Ya esta encendido? Entonces solo abrimos el navegador.
curl -s -o nul http://localhost:%PORT%/api/health && (
  echo Centinela ya esta en marcha. Abriendo el navegador...
  start "" "%URL%"
  exit /b 0
)

rem Python 3.11 o superior (prueba "py" y luego "python")
set PY=
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set PY=py -3
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set PY=python
if not defined PY (
  echo Necesitas Python 3.11 o superior.
  echo Descargalo de https://www.python.org/downloads/ y, al instalarlo, marca "Add Python to PATH".
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)

rem Primera vez: entorno virtual y dependencias
if not exist ".venv\Scripts\uvicorn.exe" (
  echo Preparando Centinela por primera vez ^(solo ocurre una vez^)...
  %PY% -m venv .venv || (echo Error creando el entorno. & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
  ".venv\Scripts\pip.exe" install -q -r requirements.txt || (echo Error instalando dependencias. & pause & exit /b 1)
)
if not exist ".env" copy ".env.example" ".env" >nul

rem Abrimos el navegador en cuanto el servidor responda
start "" /b powershell -NoProfile -Command "for($i=0;$i -lt 30;$i++){try{Invoke-WebRequest -UseBasicParsing http://localhost:%PORT%/api/health | Out-Null; Start-Process '%URL%'; break}catch{Start-Sleep 1}}"

echo Banco Demo esta en marcha en %URL%
echo Deja esta ventana abierta mientras la uses. Para apagarla: cierra la ventana o pulsa Ctrl + C.
echo.
cd backend
"..\.venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port %PORT%
pause
