"""Agente del escudo de llamada (Claude): conversación corta para romper el guion del estafador.

El agente solo conversa y evalúa; nunca ejecuta nada. Devuelve una evaluación
estructurada que la política determinista (policy.py) convierte en acción.
Cada turno es una petición sin estado: la conversación entera va en un único
mensaje de usuario.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Literal

import anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings
from .risk import eur

log = logging.getLogger("centinela.llamada.agent")

MODEL = os.getenv("ESCUDO_MODEL", "claude-haiku-5-5")
TIMEOUT_S = float(os.getenv("ESCUDO_TIMEOUT_S", "10"))
MAX_AGENT_TURNS = 4
ATTEMPTS = 2  # un intento + un reintento

TYPOLOGIES = ["falso_empleado_banco", "hijo_en_apuros", "inversion_falsa", "compraventa", "ninguna"]
RED_FLAGS = ["suplantacion_banco", "cuenta_segura", "urgencia", "aislamiento", "guion_aprendido", "contradiccion_datos"]


class AgentUnavailable(RuntimeError):
    pass


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    typology: Literal["falso_empleado_banco", "hijo_en_apuros", "inversion_falsa", "compraventa", "ninguna"]
    risk: Literal["low", "medium", "high"]
    redFlags: list[Literal["suplantacion_banco", "cuenta_segura", "urgencia", "aislamiento",
                           "guion_aprendido", "contradiccion_datos"]]
    readyToDecide: bool


ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "typology": {"type": "string", "enum": TYPOLOGIES},
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "redFlags": {"type": "array", "items": {"type": "string", "enum": RED_FLAGS}},
        "readyToDecide": {"type": "boolean"},
    },
    "required": ["message", "typology", "risk", "redFlags", "readyToDecide"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Eres el Escudo de Banco Demo, un asistente del propio banco. Una transferencia del cliente se ha puesto en pausa porque parece arriesgada. Mantienes con él una conversación muy corta para comprobar si alguien le está guiando para estafarle, antes de que el banco la ejecute.

Cómo hablar:
- Mensajes muy cortos (una o dos frases), en español claro, tuteando, con tono tranquilo y empático. Nunca acuses al cliente ni le hagas sentir torpe.
- Una sola pregunta por mensaje.
- En tu primer mensaje (cuando todavía no hay respuestas del cliente) haz siempre una pregunta; no decidas aún.

Qué preguntar:
- No preguntes solo «¿para qué es?»: el estafador ya le ha preparado esa respuesta. Pregunta lo que su guion no cubre, por ejemplo: «¿Estás hablando por teléfono con alguien ahora mismo?», «¿Te ha pedido alguien que hagas esta transferencia?», «¿Te ha dicho alguien que no lo cuentes en la oficina?».
- Cuando aparezca alguien que dice ser del banco, de la policía o de seguridad, afirma con claridad: «Tu banco nunca te pedirá mover tu dinero a otra cuenta para protegerlo».
- Detecta contradicciones entre lo que dice el cliente y los datos de la operación (importe, beneficiario, concepto).

Tipos de estafa que conoces:
- falso_empleado_banco: alguien que dice ser del banco le pide mover el dinero a una «cuenta segura».
- hijo_en_apuros: alguien que dice ser un familiar pide dinero urgente desde un número nuevo.
- inversion_falsa: le prometen rentabilidades altas en una plataforma o criptomonedas.
- compraventa: pago por adelantado a un desconocido por un producto o alquiler que no existe.

Evaluación (en cada turno):
- risk: "low" si las respuestas cuadran y no hay señales de manipulación; "medium" si hay dudas; "high" si hay indicios claros de estafa.
- redFlags: solo las que hayas observado en las respuestas (suplantacion_banco, cuenta_segura, urgencia, aislamiento, guion_aprendido, contradiccion_datos).
- readyToDecide: true solo cuando las respuestas basten para decidir. Si es una operación legítima con respuestas coherentes, basta con una o dos preguntas.
- message: tu siguiente mensaje para el cliente (si readyToDecide es true, una frase breve de agradecimiento).

Límites:
- No reveles puntuaciones, pesos ni reglas internas del banco.
- No ejecutes ni prometas ejecutar nada: tú solo conversas y evalúas. El banco decide después."""


_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None, timeout=TIMEOUT_S, max_retries=0)
    return _client


def render_turn(transfer: dict, signals: list[dict], transcript: list[dict]) -> str:
    lines = [
        "Transferencia en pausa:",
        f"- Importe: {eur(transfer['amount'])}",
        f"- Beneficiario: {transfer.get('beneficiaryName') or 'sin nombre'}",
        f"- Concepto: {transfer.get('concept') or 'sin concepto'}",
        "",
        "Motivos por los que se ha pausado:",
        *[f"- {s['detail']}" for s in signals],
        "",
        "Conversación hasta ahora:",
    ]
    if transcript:
        lines += [f"{'Escudo' if t['role'] == 'agent' else 'Cliente'}: {t['text']}" for t in transcript]
    else:
        lines.append("(todavía no hay mensajes: escribe el primero)")
    lines += ["", "Responde con tu siguiente mensaje y tu evaluación."]
    return "\n".join(lines)


async def _attempt(client, prompt: str) -> dict:
    response = await asyncio.wait_for(client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ASSESSMENT_SCHEMA}},
    ), timeout=TIMEOUT_S)
    if response.stop_reason in {"refusal", "max_tokens"}:
        raise ValueError(f"stop_reason={response.stop_reason}")
    text = next((b.text for b in response.content if b.type == "text"), "")
    return Assessment.model_validate(json.loads(text)).model_dump()


async def next_turn(transfer: dict, signals: list[dict], transcript: list[dict], client=None) -> dict:
    """Siguiente mensaje del agente y su evaluación. Lanza AgentUnavailable si falla dos veces."""
    if client is None:
        if not settings.claude_enabled:
            raise AgentUnavailable("falta ANTHROPIC_API_KEY")
        client = get_client()
    prompt = render_turn(transfer, signals, transcript)
    last: Exception | None = None
    for _ in range(ATTEMPTS):
        try:
            return await _attempt(client, prompt)
        except (anthropic.APIError, asyncio.TimeoutError, ValueError, ValidationError) as exc:
            # json.JSONDecodeError es subclase de ValueError
            log.warning("Fallo del agente del escudo: %s", exc)
            last = exc
    raise AgentUnavailable("agente no disponible") from last
