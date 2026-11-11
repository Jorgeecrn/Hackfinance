"""Orquestador del análisis: nota de voz -> texto, reglas, agente IA y acciones de protección."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import aclosing

import httpx

from . import bank, elevenlabs, state as st
from .agent import AgentError, investigate
from .config import settings
from .events import bus
from .rules import RuleResult, _actions, analyze_rules, explain_rules

log = logging.getLogger("centinela.analyzer")

AUDIO_TYPES = ("audio/",)
IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")
_in_progress: set[str] = set()  # Reclamaciones del bucle ASGI de la demo, un solo proceso.


NOTA_RED_DE_SEGURIDAD = ("La IA no ha visto riesgo, pero nuestras comprobaciones automáticas sí: "
                         "mejor comprobarlo antes de actuar.")


def _merge_with_rules(verdict: dict, rules: RuleResult, strong_evidence: bool) -> tuple[dict, str]:
    """Red de seguridad: la IA no puede dar por tranquilo (verde) un mensaje si
    - hay pruebas objetivas fuertes (web que imita a un banco, cuenta extranjera...), o
    - las reglas ya lo marcan en rojo (por ejemplo, el falso hijo que pide un Bizum urgente).
    En ese caso manda el veredicto de las reglas entero, para que el nivel, el texto y la voz digan lo mismo.
    Devuelve (veredicto, fuente)."""
    if verdict.get("nivel") == "verde" and (strong_evidence or rules.level == "rojo"):
        if rules.level != "verde":
            v = explain_rules(rules)
            v["pruebas"].append(NOTA_RED_DE_SEGURIDAD)
            return v, "reglas"
        verdict["nivel"] = "amarillo"
        verdict["puntuacion"] = max(int(verdict.get("puntuacion", 0)), 40)
        verdict.setdefault("pruebas", []).append(NOTA_RED_DE_SEGURIDAD)
    verdict["puntuacion"] = max(0, min(100, int(verdict.get("puntuacion", 0))))
    return verdict, "ia"


async def _compute_stream(
    texto: str = "",
    remitente: str | None = None,
    canal: str = "sms",
    archivo: tuple[bytes, str, str] | None = None,  # (datos, nombre, mime)
    mensaje_id: str | None = None,
) -> AsyncIterator[dict]:
    t0 = time.perf_counter()
    data = st.load()
    perfil, contacts = data["perfil"], data["contactos"]
    family = perfil.get("familiar")
    image = None
    origen = "texto"

    if archivo:
        content, filename, mime = archivo
        mime = (mime or "").lower()
        if mime.startswith(AUDIO_TYPES):
            origen = "nota_de_voz"
            yield {"tipo": "paso", "texto": "Escuchando la nota de voz…", "estado": "en_curso"}
            try:
                transcript = await elevenlabs.transcribe(content, filename, mime)
            except elevenlabs.ElevenLabsError as exc:
                yield {"tipo": "error", "texto": f"No he podido escuchar la nota de voz: {exc}"}
                return
            texto = (texto + "\n" + transcript).strip() if texto else transcript
            yield {"tipo": "paso", "texto": f"Nota de voz transcrita: «{transcript[:120]}»", "estado": "hecho", "transcripcion": transcript}
        elif mime in IMAGE_TYPES:
            origen = "captura"
            image = (content, mime)
        else:
            yield {"tipo": "error", "texto": "Tipo de archivo no compatible. Comparte un texto, una captura o una nota de voz."}
            return

    if not texto and not image:
        yield {"tipo": "error", "texto": "No hay nada que analizar."}
        return

    yield {"tipo": "paso", "texto": "Leyendo el mensaje y buscando señales de alarma…", "estado": "en_curso"}
    rules = await asyncio.to_thread(analyze_rules, texto or "", remitente, contacts)
    n_ent = sum(len(v) for k, v in rules.entities.to_dict().items() if k != "importes")
    yield {"tipo": "paso", "texto": f"Revisión rápida: {len([s for s in rules.signals if s.weight > 0])} señales de alarma, {n_ent} enlaces/teléfonos/cuentas encontrados", "estado": "hecho"}

    strong = any(s.id in {"enlace_imita_marca", "iban_extranjero", "familiar_desconocido", "dominio_reciente"} for s in rules.signals)
    verdict = None
    fuente = "reglas"
    if settings.claude_enabled:
        yield {"tipo": "paso", "texto": "La IA está investigando el mensaje…", "estado": "en_curso"}
        try:
            async for ev in investigate(texto, remitente, canal, rules, contacts, family, image):
                if ev["tipo"] == "veredicto":
                    verdict, fuente = _merge_with_rules(ev["datos"], rules, strong)
                else:
                    yield ev
        except AgentError as exc:
            log.warning("Fallo del agente, uso reglas: %s", exc)
            yield {"tipo": "paso", "texto": f"{exc}. Uso el análisis automático de respaldo.", "estado": "aviso"}
    image_unchecked = bool(image and verdict is None)
    if verdict is None:
        if image and not texto:
            yield {"tipo": "error", "texto": "Para analizar capturas de pantalla hace falta la IA (configura ANTHROPIC_API_KEY)."}
            return
        verdict = explain_rules(rules)

    limitation = None
    if image_unchecked:
        limitation = "Revisión parcial: analizamos el texto. La captura queda sin revisar."
        verdict["mensaje_voz"] = f"{limitation} {verdict['mensaje_voz']}"
    verdict["acciones"] = _actions(verdict["nivel"])
    result = {
        "id": st.new_id("an"),
        "fecha": st.now_iso(),
        "fuente": fuente,
        "origen": origen,
        "limitacion": limitation,
        "canal": canal,
        "remitente": remitente,
        "texto": texto,
        "mensaje_id": mensaje_id,
        "latencia_ms": int((time.perf_counter() - t0) * 1000),
        "veredicto": verdict,
        "detalle_reglas": rules.to_dict(),
    }

    yield {"tipo": "resultado", "datos": result}


async def analyze_stream(texto: str = "", remitente: str | None = None, canal: str = "sms",
                         archivo: tuple[bytes, str, str] | None = None,
                         mensaje_id: str | None = None, automatico: bool = False) -> AsyncIterator[dict]:
    """Calcula el análisis y aplica sus efectos una vez para cada SMS guardado."""
    if mensaje_id:
        message = st.find_message(st.load(), mensaje_id)
        if message is None:
            yield {"tipo": "error", "texto": "El mensaje ya no está en la bandeja."}
            return
        if message.get("resultado"):
            yield {"tipo": "resultado", "datos": message["resultado"]}
            return
        if mensaje_id in _in_progress:
            yield {"tipo": "pendiente", "mensaje_id": mensaje_id}
            return
        texto, remitente, canal, archivo = message["texto"], message["remitente"], message["canal"], None
        _in_progress.add(mensaje_id)

    steps = []
    try:
        async for event in _compute_stream(texto, remitente, canal, archivo, mensaje_id):
            if event["tipo"] == "paso":
                steps.append(event)
            if event["tipo"] == "resultado":
                result = event["datos"]
                result["pasos"] = steps
                if not _record_result(result, automatico):
                    yield {"tipo": "error", "texto": "El mensaje ya no está en la bandeja."}
                    return
            yield event
    finally:
        if mensaje_id:
            _in_progress.discard(mensaje_id)


async def analyze(**kwargs) -> dict:
    """Versión no streaming: devuelve solo el resultado final."""
    steps = []
    async with aclosing(analyze_stream(**kwargs)) as stream:
        async for ev in stream:
            if ev["tipo"] == "resultado":
                return ev["datos"]
            if ev["tipo"] == "pendiente":
                return {"pendiente": True, "mensaje_id": ev["mensaje_id"]}
            if ev["tipo"] == "error":
                return {"error": ev["texto"], "pasos": steps}
            steps.append(ev)
    return {"error": "Sin resultado", "pasos": steps}


def _build_alert(result: dict, perfil: dict) -> dict:
    v = result["veredicto"]
    return {
        "id": st.new_id("al"),
        "fecha": result["fecha"],
        "nivel": v["nivel"],
        "titulo": v["titulo"],
        "tipo_estafa": v.get("tipo_estafa"),
        "resumen": v["explicacion"],
        "remitente": result.get("remitente"),
        "canal": result.get("canal"),
        "texto": (result.get("texto") or "")[:500],
        "persona": perfil.get("nombre"),
        "notificada": False,
    }

def _record_result(result: dict, automatico: bool) -> bool:
    mensaje_id = result["mensaje_id"]
    verdict = result["veredicto"]
    level = verdict["nivel"]

    def _do(s):
        message = st.find_message(s, mensaje_id) if mensaje_id else None
        if mensaje_id and (message is None or message.get("resultado")):
            return None
        alert = shield = None
        if level in {"rojo", "amarillo"}:
            alert = _build_alert(result, s["perfil"])
            result["alerta_id"] = alert["id"]
            if level == "rojo" and not settings.telegram_enabled:
                alert["notificada"] = True
            s["alertas"].insert(0, alert)
            s["alertas"] = s["alertas"][:100]
            if level == "rojo" and s["perfil"].get("escudo_bancario", True):
                shield = bank.new_shield(f"Posible estafa: {verdict.get('tipo_estafa') or verdict['titulo']}", alert["id"])
                s["banco"]["escudo"] = shield
                result["escudo_activado"] = True
        if message is not None:
            message["analisis"] = {"nivel": level, "titulo": verdict["titulo"], "id": result["id"]}
            message["resultado"] = result
        return alert, shield

    committed = st.update(_do)
    if committed is None:
        return False
    alert, shield = committed
    if alert:
        bus.publish("familia", "alerta", {"id": alert["id"], "nivel": level})
        bus.publish("banco", "alerta", alert)
    if shield:
        bank.publish_shield(shield)
    if alert and level == "rojo":
        if settings.telegram_enabled:
            asyncio.create_task(notify_family(alert))
        else:
            bus.publish("familia", "aviso_familiar", {"id": alert["id"], "notificada": True})
    if mensaje_id:
        bus.publish("usuario", "analisis_mensaje", {"id": mensaje_id, "automatico": automatico})
    return True


async def notify_family(alert: dict) -> dict:
    """Avisa al familiar: siempre por el panel en tiempo real y, si está configurado, por Telegram."""
    snapshot = st.load()
    registered = next((a for a in snapshot["alertas"] if a["id"] == alert["id"]), None)
    if registered is None or registered.get("notificada"):
        return {"id": alert["id"], "notificada": bool(registered and registered["notificada"]), "telegram": False}
    perfil = snapshot["perfil"]
    fam = perfil.get("familiar") or {}
    text = (
        f"⚠️ Centinela: {perfil.get('nombre', 'Tu familiar')} ha recibido un posible timo.\n"
        f"{alert['titulo']}\n{alert['resumen']}\n"
        f"Remitente: {alert.get('remitente') or 'desconocido'}. Llámale para tranquilizarle."
    )
    sent_telegram = False
    if settings.telegram_enabled:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": text},
                )
                sent_telegram = r.status_code == 200
        except httpx.HTTPError:
            log.warning("No se pudo enviar el aviso por Telegram")

    def _do(s):
        for a in s["alertas"]:
            if a["id"] == alert["id"]:
                a["notificada"] = True
                a["notificada_a"] = fam.get("nombre")
                return True
        return False

    if not st.update(_do):
        return {"id": alert["id"], "notificada": False, "telegram": sent_telegram}
    payload = {**alert, "notificada": True, "telegram": sent_telegram, "mensaje": text}
    bus.publish("familia", "aviso_familiar", {"id": alert["id"], "notificada": True})
    return payload
