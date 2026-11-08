"""Estado de la demo persistido en un JSON (perfil, contactos, bandeja, alertas, banco).

En producción esto sería una base de datos; para el hackathon un JSON es suficiente,
fácil de inspeccionar y de reiniciar (`POST /api/demo/reset`).
"""
from __future__ import annotations

import copy
import json
import threading
import uuid
from datetime import datetime, timezone

from .config import DATA_DIR

STATE_FILE = DATA_DIR / "state.json"
_lock = threading.RLock()

SEED: dict = {
    "perfil": {
        "nombre": "Carmen",
        "proteccion_activa": True,
        "leer_en_voz_alta": True,
        "escudo_bancario": True,
        "tamano_letra": "grande",
        "voz_id": "",
        "familiar": {"nombre": "Lucía", "relacion": "hija", "telefono": "+34600111222"},
    },
    "contactos": [
        {"nombre": "Lucía", "relacion": "hija", "telefono": "+34600111222"},
        {"nombre": "Javier", "relacion": "hijo", "telefono": "+34600333444"},
        {"nombre": "Centro de salud", "relacion": "médico", "telefono": "+34915555555"},
    ],
    "mensajes": [],
    "alertas": [],
    "banco": {
        "entidad": "MyInvestor (simulado)",
        "titular": "Carmen López",
        "iban": "ES12 1544 0000 0000 0000 1234",
        "saldo": 12450.30,
        "beneficiarios_conocidos": [
            {"nombre": "Lucía López", "iban": "ES9121000418450200051332"},
            {"nombre": "Comunidad de vecinos", "iban": "ES7620770024003102575766"},
        ],
        "transferencias": [],
        "escudo": {"activo_hasta": None, "motivo": None, "alerta_id": None},
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def load() -> dict:
    with _lock:
        if not STATE_FILE.exists():
            save(copy.deepcopy(SEED))
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            save(copy.deepcopy(SEED))
            return copy.deepcopy(SEED)


def save(state: dict) -> None:
    with _lock:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STATE_FILE)


def reset() -> dict:
    with _lock:
        state = copy.deepcopy(SEED)
        save(state)
        return state


def update(fn):
    """Aplica `fn(state)` de forma atómica y guarda. Devuelve lo que devuelva fn."""
    with _lock:
        state = load()
        result = fn(state)
        save(state)
        return result
