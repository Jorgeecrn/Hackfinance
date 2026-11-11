"""Agente investigador con Claude (tool use + salida estructurada).

Flujo:
 1. Recibe el mensaje (texto o captura), el contexto (remitente, contactos) y el
    resultado del prefiltro de reglas, que ya incluye las comprobaciones deterministas.
 2. Claude decide si necesita investigar más (herramientas) y emite un veredicto JSON.
 3. Cada llamada a herramienta se emite como «paso» para mostrar el progreso en la app.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import anthropic

from . import budget, tools
from .config import settings
from .rules import RuleResult

log = logging.getLogger("centinela.agent")

SYSTEM_PROMPT = """Eres Centinela, un asistente que protege a personas mayores frente a estafas que llegan por SMS, WhatsApp o correo, en España.

Tu trabajo: decidir si un mensaje es una estafa y explicarlo con palabras muy sencillas, como lo haría un nieto paciente. Escribe en español de España, tuteando con cariño y respeto, frases cortas y sin tecnicismos (no digas «phishing», «dominio», «TLD» ni «IBAN»: di «web falsa», «la dirección de la web», «número de cuenta»).

Cómo trabajar:
- Recibirás el mensaje, quién lo envía y un informe preliminar de un motor de reglas con comprobaciones ya hechas. Úsalo como pista, no como verdad: tú decides.
- Si en el mensaje (o en la captura de pantalla) hay enlaces, teléfonos o números de cuenta que el informe NO ha comprobado, compruébalos con las herramientas antes de decidir. No inventes datos que no hayas comprobado.
- Si alguien dice ser un familiar, usa buscar_contacto para ver si el número es el de siempre.
- Evita falsas alarmas: un SMS real con un código de verificación que dice «no lo compartas», un aviso informativo sin enlaces ni peticiones, o un familiar guardado en contactos pidiendo algo normal NO son estafas. Las falsas alarmas hacen que la gente deje de confiar en la app.

Niveles:
- "rojo": estafa casi segura (pide dinero, claves o datos con engaño, web que imita a una entidad, falso familiar...). puntuacion 70-100.
- "amarillo": señales sospechosas pero no concluyentes; conviene comprobar antes de actuar. puntuacion 35-69.
- "verde": no hay señales relevantes de estafa. puntuacion 0-34.

Campos de la respuesta:
- titulo: una frase corta y clara (p. ej. «Es un timo: alguien se hace pasar por tu hija»).
- tipo_estafa: nombre corto del tipo de estafa, o cadena vacía si es verde.
- explicacion: 2-3 frases explicando por qué, citando las pruebas concretas.
- pruebas: de 2 a 5 pruebas concretas y comprobadas, cada una en una frase sencilla.
- consejo: qué hacer ahora, en una o dos frases (p. ej. «No pagues nada. Llama a Lucía a su número de siempre»).
- mensaje_voz: texto para leer en voz alta, 2-4 frases naturales y tranquilas, sin direcciones web ni números largos.
"""

TOOLS = [
    {
        "name": "analizar_enlace",
        "description": "Investiga un enlace o dirección web: si imita a un banco, empresa u organismo oficial, si es un acortador, si la web es muy reciente, si otros usuarios la han reportado.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "El enlace tal y como aparece en el mensaje"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analizar_telefono",
        "description": "Investiga un número de teléfono: país, si es de tarificación especial, si está en los contactos de confianza del usuario y si otros usuarios lo han reportado.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"telefono": {"type": "string"}},
            "required": ["telefono"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analizar_iban",
        "description": "Investiga un número de cuenta bancaria (IBAN): si es válido, de qué país y de qué banco es, y si encaja con la entidad que dice ser el remitente.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "iban": {"type": "string"},
                "entidad_que_dice_ser": {"type": "string", "description": "Entidad que dice ser el remitente, o cadena vacía"},
            },
            "required": ["iban", "entidad_que_dice_ser"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_campanas",
        "description": "Compara un texto con campañas de estafa conocidas en España (falso hijo en apuros, paquete retenido, multa DGT, banco bloqueado, inversión milagro...).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string"}},
            "required": ["texto"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_contacto",
        "description": "Busca en los contactos de confianza del usuario por nombre, parentesco (hija, hijo, nieto...) o número.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"consulta": {"type": "string"}},
            "required": ["consulta"],
            "additionalProperties": False,
        },
    },
]

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "nivel": {"type": "string", "enum": ["verde", "amarillo", "rojo"]},
        "puntuacion": {"type": "integer"},
        "titulo": {"type": "string"},
        "tipo_estafa": {"type": "string"},
        "explicacion": {"type": "string"},
        "pruebas": {"type": "array", "items": {"type": "string"}},
        "consejo": {"type": "string"},
        "mensaje_voz": {"type": "string"},
    },
    "required": ["nivel", "puntuacion", "titulo", "tipo_estafa", "explicacion", "pruebas", "consejo", "mensaje_voz"],
    "additionalProperties": False,
}

TOOL_LABELS = {
    "analizar_enlace": "Comprobando el enlace",
    "analizar_telefono": "Comprobando el número de teléfono",
    "analizar_iban": "Comprobando el número de cuenta",
    "buscar_campanas": "Comparando con estafas conocidas",
    "buscar_contacto": "Buscando en tus contactos de confianza",
}


class AgentError(RuntimeError):
    pass


MAX_TOKENS = 8000
_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or None,
            timeout=settings.claude_timeout_s,
            max_retries=1,
        )
    return _client


def run_tool(name: str, args: dict, contacts: list[dict]) -> dict | list:
    if name == "analizar_enlace":
        return tools.analyze_url(args["url"])
    if name == "analizar_telefono":
        return tools.analyze_phone(args["telefono"], contacts)
    if name == "analizar_iban":
        return tools.analyze_iban(args["iban"], args.get("entidad_que_dice_ser") or None)
    if name == "buscar_campanas":
        return tools.search_campaigns(args["texto"], top_k=3)
    if name == "buscar_contacto":
        return tools.lookup_contact(args["consulta"], contacts)
    raise ValueError(f"Herramienta desconocida: {name}")


def _tool_summary(name: str, result) -> str:
    if isinstance(result, dict):
        if result.get("hallazgos"):
            return result["hallazgos"][0]
        if name == "buscar_contacto":
            found = result.get("encontrados") or []
            return f"Encontrado: {found[0]['nombre']} ({found[0]['telefono']})" if found else "No aparece en tus contactos"
    if isinstance(result, list):
        return f"Se parece a: {result[0]['nombre']}" if result else "No coincide con campañas conocidas"
    return "Hecho"


def _user_content(text: str, sender: str | None, channel: str, rules: RuleResult,
                  image: tuple[bytes, str] | None, contacts: list[dict], family: dict | None) -> list[dict]:
    import base64

    contact_lines = "\n".join(f"- {c['nombre']} ({c.get('relacion', '')}): {c['telefono']}" for c in contacts) or "(ninguno)"
    report = json.dumps(rules.to_dict(), ensure_ascii=False)
    fam = f"{family.get('nombre')} ({family.get('relacion')}), teléfono {family.get('telefono')}" if family else "no configurado"
    prompt = (
        f"Canal: {channel}\n"
        f"Remitente: {sender or 'desconocido'}\n"
        f"Familiar de confianza del usuario: {fam}\n"
        f"Contactos de confianza:\n{contact_lines}\n\n"
        f"Informe preliminar del motor de reglas (JSON):\n{report}\n\n"
    )
    if text:
        prompt += f"Mensaje recibido:\n<<<\n{text}\n>>>\n"
    if image:
        prompt += "El usuario ha compartido una captura de pantalla del mensaje (adjunta). Lee su contenido con atención; el informe preliminar no la ha analizado.\n"
    prompt += "\nInvestiga lo necesario y responde con el veredicto."

    content: list[dict] = []
    if image:
        data, mime = image
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": base64.standard_b64encode(data).decode()},
        })
    content.append({"type": "text", "text": prompt})
    return content


async def investigate(text: str, sender: str | None, channel: str, rules: RuleResult,
                      contacts: list[dict], family: dict | None,
                      image: tuple[bytes, str] | None = None) -> AsyncIterator[dict]:
    """Ejecuta el agente. Emite {"tipo": "paso", ...} y termina con {"tipo": "veredicto", ...}."""
    messages: list[dict] = [{"role": "user", "content": _user_content(text, sender, channel, rules, image, contacts, family)}]
    tool_calls: list[dict] = []

    for round_idx in range(settings.claude_max_tool_rounds + 1):
        last_round = round_idx == settings.claude_max_tool_rounds
        kwargs = {}
        if last_round:
            kwargs["tool_choice"] = {"type": "none"}
        try:
            reserved = budget.reserve_claude(MAX_TOKENS)
        except budget.BudgetExceeded as exc:
            raise AgentError(str(exc)) from exc
        try:
            response = await client().beta.messages.create(
                model=settings.claude_model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": settings.claude_effort, "format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **kwargs,
            )
        except anthropic.APIStatusError as exc:
            raise AgentError(f"Error de la API de Claude ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise AgentError("No se pudo conectar con Claude") from exc
        budget.settle_claude(reserved, getattr(response, "usage", None))

        if response.stop_reason == "refusal":
            raise AgentError("Claude no pudo analizar este mensaje")
        if response.stop_reason == "max_tokens":
            raise AgentError("Respuesta de Claude incompleta")

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": response.content})
            for tu in tool_uses:
                yield {"tipo": "paso", "texto": TOOL_LABELS.get(tu.name, tu.name) + "…", "herramienta": tu.name, "estado": "en_curso"}

            async def _exec(tu):
                try:
                    res = await asyncio.to_thread(run_tool, tu.name, dict(tu.input), contacts)
                    return tu, res, False
                except Exception as exc:  # la herramienta falla -> se lo decimos a Claude
                    return tu, {"error": str(exc)}, True

            results = await asyncio.gather(*[_exec(tu) for tu in tool_uses])
            tool_results = []
            for tu, res, is_err in results:
                summary = "No se pudo comprobar" if is_err else _tool_summary(tu.name, res)
                tool_calls.append({"herramienta": tu.name, "entrada": dict(tu.input), "resumen": summary})
                yield {"tipo": "paso", "texto": f"{TOOL_LABELS.get(tu.name, tu.name)}: {summary}", "herramienta": tu.name, "estado": "hecho"}
                block = {"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(res, ensure_ascii=False)}
                if is_err:
                    block["is_error"] = True
                tool_results.append(block)
            messages.append({"role": "user", "content": tool_results})
            continue

        text_out = next((b.text for b in response.content if b.type == "text"), "")
        try:
            verdict = json.loads(text_out)
        except json.JSONDecodeError as exc:
            raise AgentError("Claude devolvió un veredicto con formato no válido") from exc
        verdict["herramientas_usadas"] = tool_calls
        verdict["modelo"] = response.model
        yield {"tipo": "veredicto", "datos": verdict}
        return

    raise AgentError("El agente no terminó a tiempo")
