"""Orquestador del análisis: nota de voz -> texto, reglas, agente IA y acciones de protección."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

import httpx

from . import bank, elevenlabs, state as st
from .agent import AgentError, investigate
from .config import settings
from .events import bus
from .rules import _actions, analyze_rules, explain_rules

log = logging.getLogger("centinela.analyzer")

AUDIO_TYPES = ("audio/",)
IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")


def _merge_with_rules(verdict: dict, rules_level: str, strong_evidence: bool) -> dict:
    """Red de seguridad: si hay pruebas objetivas fuertes (web que imita a un banco,
    cuenta extranjera...) nunca devolvemos verde."""
    if strong_evidence and verdict.get("nivel") == "verde":
        verdict["nivel"] = "amarillo"
        verdict["puntuacion"] = max(int(verdict.get("puntuacion", 0)), 40)
        verdict.setdefault("pruebas", []).append(
            "Nuestras comprobaciones automáticas han encontrado señales objetivas de riesgo, así que mejor comprobarlo antes de actuar."
        )
    verdict["puntuacion"] = max(0, min(100, int(verdict.get("puntuacion", 0))))
    return verdict


async def analyze_stream(
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
                    verdict = _merge_with_rules(ev["datos"], rules.level, strong)
                    fuente = "ia"
                else:
                    yield ev
        except AgentError as exc:
            log.warning("Fallo del agente, uso reglas: %s", exc)
            yield {"tipo": "paso", "texto": f"{exc}. Uso el análisis automático de respaldo.", "estado": "aviso"}
    if verdict is None:
        if image and not texto:
            yield {"tipo": "error", "texto": "Para analizar capturas de pantalla hace falta la IA (configura ANTHROPIC_API_KEY)."}
            return
        verdict = explain_rules(rules)

    verdict["acciones"] = _actions(verdict["nivel"])
    result = {
        "id": st.new_id("an"),
        "fecha": st.now_iso(),
        "fuente": fuente,
        "origen": origen,
        "canal": canal,
        "remitente": remitente,
        "texto": texto,
        "mensaje_id": mensaje_id,
        "latencia_ms": int((time.perf_counter() - t0) * 1000),
        "veredicto": verdict,
        "detalle_reglas": rules.to_dict(),
    }

    # Acciones de protección automáticas
    if verdict["nivel"] in ("rojo", "amarillo"):
        alert = _register_alert(result, perfil)
        result["alerta_id"] = alert["id"]
        if verdict["nivel"] == "rojo" and perfil.get("escudo_bancario", True):
            bank.activate_shield(f"Posible estafa: {verdict.get('tipo_estafa') or verdict.get('titulo')}", alert["id"])
            result["escudo_activado"] = True
            yield {"tipo": "paso", "texto": "Escudo bancario activado: las transferencias a cuentas nuevas quedan en pausa", "estado": "hecho"}
        if verdict["nivel"] == "rojo":
            asyncio.create_task(notify_family(alert))
    if mensaje_id:
        _attach_to_message(mensaje_id, result)

    yield {"tipo": "resultado", "datos": result}


async def analyze(**kwargs) -> dict:
    """Versión no streaming: devuelve solo el resultado final."""
    steps = []
    async for ev in analyze_stream(**kwargs):
        if ev["tipo"] == "resultado":
            ev["datos"]["pasos"] = steps
            return ev["datos"]
        if ev["tipo"] == "error":
            return {"error": ev["texto"], "pasos": steps}
        steps.append(ev)
    return {"error": "Sin resultado", "pasos": steps}


def _register_alert(result: dict, perfil: dict) -> dict:
    v = result["veredicto"]
    alert = {
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

    def _do(s):
        s["alertas"].insert(0, alert)
        s["alertas"] = s["alertas"][:100]

    st.update(_do)
    bus.publish_many(["familia", "banco"], "alerta", alert)
    return alert


def _attach_to_message(mensaje_id: str, result: dict) -> None:
    def _do(s):
        for m in s["mensajes"]:
            if m["id"] == mensaje_id:
                m["analisis"] = {"nivel": result["veredicto"]["nivel"], "titulo": result["veredicto"]["titulo"], "id": result["id"]}
                m["resultado"] = result

    st.update(_do)


async def notify_family(alert: dict) -> dict:
    """Avisa al familiar: siempre por el panel en tiempo real y, si está configurado, por Telegram."""
    perfil = st.load()["perfil"]
    fam = perfil.get("familiar") or {}
    text = (
        f"⚠️ Centinela: {perfil.get('nombre', 'Tu familiar')} ha recibido un posible timo.\n"
        f"{alert['titulo']}\n{alert['resumen']}\n"
        f"Remitente: {alert.get('remitente') or 'desconocido'}. Llámale para tranquilizarle."
    )
    sent_telegram = False
    if settings.telegram_bot_token and settings.telegram_chat_id and not settings.force_offline:
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

    st.update(_do)
    payload = {**alert, "notificada": True, "telegram": sent_telegram, "mensaje": text}
    bus.publish("familia", "aviso_familiar", payload)
    return payload
