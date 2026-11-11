"""Controles de acceso de la demo local y guardia de administración."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from .config import settings

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
LOCAL_AUTHORITY = re.compile(r"(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?", re.IGNORECASE)
FORWARD_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded",
                   "x-real-ip", "cf-connecting-ip", "true-client-ip")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        return False
    return not any(h in request.headers for h in FORWARD_HEADERS)


def solo_admin(request: Request) -> None:
    """Dependencia de FastAPI para rutas de administración."""
    if (settings.admin_remoto and not settings.demo_local) or is_local(request):
        return
    raise HTTPException(403, "Esta acción solo se puede hacer desde el ordenador de la demo")


def _origin(url: str) -> tuple[str, str | None, int] | None:
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
                or parsed.path or parsed.query or parsed.fragment):
            return None
        return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None


def validar_demo_local(request: Request) -> None:
    """Protege el estado antes de leer cuerpos o suscribir un cliente a SSE."""
    hosts = request.headers.getlist("host")
    if len(hosts) != 1 or not LOCAL_AUTHORITY.fullmatch(hosts[0]):
        raise HTTPException(400, "Usa la dirección local de Centinela")
    expected_origin = _origin(f"{request.scope['scheme']}://{hosts[0]}")
    if expected_origin is None:
        raise HTTPException(400, "Usa la dirección local de Centinela")

    path = request.scope["path"].rstrip("/")
    if path == "/api/health" and request.method in {"GET", "HEAD"}:
        return
    if not (path.startswith("/api/") or path in {"/share-target", "/openapi.json"}):
        return

    solo_admin(request)
    site = request.headers.get("sec-fetch-site")
    if site not in {None, "same-origin", "none"}:
        raise HTTPException(403, "La solicitud debe venir de esta demo")
    if request.method not in SAFE_METHODS:
        origins = request.headers.getlist("origin")
        if origins and (len(origins) != 1 or _origin(origins[0]) != expected_origin):
            raise HTTPException(403, "El origen de la solicitud no es el de esta demo")
