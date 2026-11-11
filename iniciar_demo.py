"""Arranca la demo local usando el entorno Python ya preparado."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from http.client import HTTPConnection, HTTPException
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def is_demo(port: int) -> bool:
    connection = HTTPConnection(HOST, port, timeout=0.5)
    try:
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        if response.status != 200:
            return False
        data = json.loads(response.read(4096))
        return (
            isinstance(data, dict)
            and data.get("servicio") == "centinela"
            and data.get("perfil") == "demo-local"
            and all(data.get(key) is False for key in ("ia", "voz", "telegram", "consultas_online"))
        )
    except (OSError, HTTPException, ValueError):
        return False
    finally:
        connection.close()


def main() -> int:
    if sys.version_info < (3, 11):
        print("Centinela necesita Python 3.11 o superior.")
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto", type=int, default=os.getenv("PORT", "8000"))
    parser.add_argument("--sin-navegador", action="store_true")
    args = parser.parse_args()
    port = args.puerto
    if not 1 <= port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535")
    url = f"http://{HOST}:{port}/"

    if is_demo(port):
        print(f"Centinela en modo demo local: {url}", flush=True)
        if not args.sin_navegador:
            webbrowser.open(url)
        return 0

    try:
        occupied = socket.create_connection((HOST, port), timeout=0.5)
    except OSError:
        pass
    else:
        occupied.close()
        print(f"El puerto {port} está ocupado por un proceso ajeno a la demo local. Usa otro puerto.")
        return 1

    missing = [name for name in ("uvicorn", "fastapi", "dotenv", "anthropic", "python_multipart")
               if importlib.util.find_spec(name) is None]
    if missing:
        print("Faltan dependencias en el entorno actual: " + ", ".join(missing))
        print("Prepara el entorno con requirements.txt antes de arrancar la demo.")
        return 1

    env = {**os.environ, "CENTINELA_DEMO_LOCAL": "1", "FORCE_OFFLINE": "1",
           "ONLINE_CHECKS": "0", "ADMIN_REMOTO": "0"}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(port),
         "--no-proxy-headers"],
        cwd=ROOT / "backend",
        env=env,
    )
    try:
        for _ in range(60):
            if server.poll() is not None:
                return server.returncode or 1
            if is_demo(port):
                print(f"Centinela en modo demo local: {url}", flush=True)
                if not args.sin_navegador:
                    webbrowser.open(url)
                return server.wait()
            time.sleep(0.25)
        print("Centinela no confirmó el perfil local durante el arranque.")
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
