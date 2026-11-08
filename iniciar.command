#!/bin/bash
# Centinela — doble clic para arrancar la demo en Mac.
# La primera vez prepara todo (tarda un par de minutos); después arranca en segundos.
cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8000}"
URL="http://localhost:$PORT/demo.html"

echo "🛡️  Centinela"
echo

# ¿Ya está encendido? Entonces solo abrimos el navegador.
if curl -s -o /dev/null "http://localhost:$PORT/api/health"; then
  echo "Centinela ya está en marcha. Abriendo el navegador…"
  open "$URL"
  exit 0
fi

# Python 3.11 o superior
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "❌ Necesitas Python 3.11 o superior."
  echo "   Descárgalo de https://www.python.org/downloads/ , instálalo y vuelve a abrir este archivo."
  open "https://www.python.org/downloads/"
  read -r -p "Pulsa Enter para cerrar…"
  exit 1
fi

# Primera vez: entorno virtual y dependencias
if [ ! -x .venv/bin/uvicorn ]; then
  echo "Preparando Centinela por primera vez (solo ocurre una vez)…"
  python3 -m venv .venv || { read -r -p "Error creando el entorno. Pulsa Enter para cerrar…"; exit 1; }
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt || { read -r -p "Error instalando dependencias. Pulsa Enter para cerrar…"; exit 1; }
fi
[ -f .env ] || cp .env.example .env

# Abrimos el navegador en cuanto el servidor responda
(
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "http://localhost:$PORT/api/health"; then open "$URL"; exit 0; fi
    sleep 1
  done
) &

echo "Centinela está en marcha en $URL"
echo "Deja esta ventana abierta mientras la uses. Para apagarla: cierra la ventana o pulsa Ctrl + C."
echo
cd backend && exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
