"""Rutas de administración de la demo: solo desde el propio portátil.

Idea tomada de la seguridad de la API local de hackaton-finance-antifraude (ADR 0013), simplificada: los
lanzadores arrancan el servidor en 0.0.0.0 para que el móvil de la demo entre por la wifi, así que cualquiera
en esa red podría reiniciar la demo, simular mensajes o liberar transferencias retenidas. Con esta dependencia,
esas rutas solo responden a peticiones que llegan desde el propio ordenador (127.0.0.1 / ::1).

- La app del cliente (analizar, transferir, ajustes) sigue funcionando desde el móvil.
- Detrás de un túnel (cloudflared, ngrok) la petición llega desde 127.0.0.1 pero con cabeceras de reenvío:
  se trata como remota.
- ``ADMIN_REMOTO=1`` en el .env desactiva la protección (por ejemplo, si el panel del familiar se abre en
  otro móvil). No se recomienda en una red compartida.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from .config import settings

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
FORWARD_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip", "cf-connecting-ip", "true-client-ip")


def is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        return False
    return not any(h in request.headers for h in FORWARD_HEADERS)


def solo_admin(request: Request) -> None:
    """Dependencia de FastAPI: 403 si la petición no viene del propio portátil."""
    if settings.admin_remoto or is_local(request):
        return
    raise HTTPException(403, "Esta acción solo se puede hacer desde el ordenador de la demo")
