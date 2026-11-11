"""Tope de gasto diario de las APIs de pago (Claude y ElevenLabs).

Idea tomada del control de costes de hackaton-finance-antifraude (ai/budget.py), simplificada para la demo:

- Antes de cada llamada se comprueba que queda margen. Si no queda, la llamada NO se hace: el análisis sigue
  con el motor de reglas, la voz con la del navegador y el Escudo de llamada pasa el caso al analista (falla de
  forma segura, como ya hacía si faltaba la clave).
- Claude: límite de llamadas al día y de tokens al día. Los tokens de cada llamada se reservan por el peor caso
  (``max_tokens``) antes de llamar y se ajustan con el ``usage`` real al terminar.
- ElevenLabs: límite de caracteres de voz al día y de notas de voz transcritas al día.
- El contador se guarda en un JSON fuera del repositorio (``~/.centinela/gasto.json`` o ``CENTINELA_GASTO_FILE``)
  y se reinicia cada día. Nunca guarda textos ni claves: solo números.

Es un freno local. El tope real de facturación se pone en la consola de Anthropic y en la de ElevenLabs.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date
from pathlib import Path

from .config import settings

GASTO_FILE = Path(os.getenv("CENTINELA_GASTO_FILE") or (Path.home() / ".centinela" / "gasto.json"))
_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    """Se ha alcanzado el tope diario: la llamada de pago no se hace."""


def _empty() -> dict:
    return {"dia": date.today().isoformat(), "claude_llamadas": 0, "claude_tokens": 0,
            "voz_caracteres": 0, "transcripciones": 0}


def _load() -> dict:
    try:
        data = json.loads(GASTO_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty()
    if not isinstance(data, dict) or data.get("dia") != date.today().isoformat():
        return _empty()
    base = _empty()
    base.update({k: int(v) for k, v in data.items() if k in base and k != "dia" and isinstance(v, (int, float))})
    return base


def _save(data: dict) -> None:
    try:
        GASTO_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = GASTO_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(GASTO_FILE)
    except OSError:
        pass  # si no se puede escribir, el contador sigue en memoria de esta llamada; no rompemos la demo


def limits() -> dict:
    return {
        "claude_llamadas": settings.ia_max_llamadas_dia,
        "claude_tokens": settings.ia_max_tokens_dia,
        "voz_caracteres": settings.voz_max_caracteres_dia,
        "transcripciones": settings.voz_max_transcripciones_dia,
    }


def status() -> dict:
    """Uso de hoy frente a los topes (sin textos ni claves)."""
    with _lock:
        used = _load()
    lim = limits()
    return {"dia": used["dia"], "uso": {k: used[k] for k in lim}, "topes": lim}


def reserve_claude(max_tokens: int) -> int:
    """Apunta una llamada a Claude por el peor caso. Devuelve los tokens reservados."""
    with _lock:
        data = _load()
        if data["claude_llamadas"] + 1 > settings.ia_max_llamadas_dia:
            raise BudgetExceeded("Se ha alcanzado el tope diario de llamadas a la IA")
        if data["claude_tokens"] + max_tokens > settings.ia_max_tokens_dia:
            raise BudgetExceeded("Se ha alcanzado el tope diario de uso de la IA")
        data["claude_llamadas"] += 1
        data["claude_tokens"] += max_tokens
        _save(data)
    return max_tokens


def settle_claude(reserved: int, usage) -> None:
    """Sustituye la reserva por el uso real. Sin ``usage`` (error a mitad) se queda la reserva: peor caso."""
    if usage is None:
        return
    real = 0
    for name in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = getattr(usage, name, None)
        if isinstance(value, int):
            real += value
    if real <= 0:
        return
    with _lock:
        data = _load()
        data["claude_tokens"] = max(0, data["claude_tokens"] - reserved + real)
        _save(data)


def reserve_voice(chars: int) -> None:
    with _lock:
        data = _load()
        if data["voz_caracteres"] + chars > settings.voz_max_caracteres_dia:
            raise BudgetExceeded("Se ha alcanzado el tope diario de voz")
        data["voz_caracteres"] += chars
        _save(data)


def reserve_transcription() -> None:
    with _lock:
        data = _load()
        if data["transcripciones"] + 1 > settings.voz_max_transcripciones_dia:
            raise BudgetExceeded("Se ha alcanzado el tope diario de notas de voz")
        data["transcripciones"] += 1
        _save(data)
