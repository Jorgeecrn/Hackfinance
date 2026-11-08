"""API de Centinela (FastAPI). Sirve también la PWA (carpeta /frontend)."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import bank, elevenlabs, state as st, tools
from .analyzer import analyze, analyze_stream, notify_family
from .config import DATA_DIR, FRONTEND_DIR, settings
from .events import bus, sse_format

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("centinela")

app = FastAPI(title="Centinela API", version="1.0.0", description="Detector de estafas por mensajes para personas mayores")

MAX_UPLOAD = 15 * 1024 * 1024
_shares: dict[str, dict] = {}


# ------------------------------------------------------------------ modelos
class Familiar(BaseModel):
    nombre: str = ""
    relacion: str = ""
    telefono: str = ""


class Contacto(BaseModel):
    nombre: str
    relacion: str = ""
    telefono: str


class Perfil(BaseModel):
    nombre: str | None = None
    proteccion_activa: bool | None = None
    leer_en_voz_alta: bool | None = None
    escudo_bancario: bool | None = None
    tamano_letra: str | None = None
    voz_id: str | None = None
    familiar: Familiar | None = None
    contactos: list[Contacto] | None = None


class TTSRequest(BaseModel):
    texto: str = Field(..., max_length=1500)
    voz_id: str | None = None


class Incoming(BaseModel):
    canal: str = "sms"
    remitente: str = ""
    texto: str = Field(..., max_length=4000)


class Transferencia(BaseModel):
    beneficiario: str
    iban: str
    importe: float = Field(..., gt=0)
    concepto: str = ""
    canal: str = "transferencia"


class Reporte(BaseModel):
    telefonos: list[str] = []
    enlaces: list[str] = []


# ------------------------------------------------------------------ utilidades
async def _read_upload(archivo: UploadFile | None) -> tuple[bytes, str, str] | None:
    if archivo is None or not archivo.filename:
        return None
    data = await archivo.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "El archivo es demasiado grande (máximo 15 MB)")
    if not data:
        return None
    return data, archivo.filename, archivo.content_type or ""


# ------------------------------------------------------------------ estado general
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ia": settings.claude_enabled,
        "modelo": settings.claude_model if settings.claude_enabled else None,
        "voz": settings.elevenlabs_enabled,
        "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }


@app.get("/api/perfil")
def get_profile():
    s = st.load()
    return {**s["perfil"], "contactos": s["contactos"]}


@app.put("/api/perfil")
def put_profile(p: Perfil):
    def _do(s):
        data = p.model_dump(exclude_none=True)
        contactos = data.pop("contactos", None)
        s["perfil"].update(data)
        if contactos is not None:
            s["contactos"] = contactos
        return {**s["perfil"], "contactos": s["contactos"]}

    perfil = st.update(_do)
    bus.publish_many(["usuario", "familia"], "perfil", perfil)
    return perfil


# ------------------------------------------------------------------ análisis
@app.post("/api/analizar")
async def analizar(
    texto: str = Form(""),
    remitente: str = Form(""),
    canal: str = Form("manual"),
    mensaje_id: str = Form(""),
    archivo: UploadFile | None = File(None),
):
    upload = await _read_upload(archivo)
    result = await analyze(texto=texto.strip(), remitente=remitente.strip() or None, canal=canal,
                           archivo=upload, mensaje_id=mensaje_id or None)
    if "error" in result:
        return JSONResponse(result, status_code=422)
    return result


@app.post("/api/analizar/stream")
async def analizar_stream(
    texto: str = Form(""),
    remitente: str = Form(""),
    canal: str = Form("manual"),
    mensaje_id: str = Form(""),
    archivo: UploadFile | None = File(None),
):
    """Igual que /api/analizar pero va enviando los pasos de la investigación (SSE)."""
    upload = await _read_upload(archivo)

    async def gen():
        async for ev in analyze_stream(texto=texto.strip(), remitente=remitente.strip() or None, canal=canal,
                                       archivo=upload, mensaje_id=mensaje_id or None):
            yield f"event: {ev['tipo']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/transcribir")
async def transcribir(archivo: UploadFile = File(...)):
    upload = await _read_upload(archivo)
    if not upload:
        raise HTTPException(400, "Falta el audio")
    try:
        texto = await elevenlabs.transcribe(*upload)
    except elevenlabs.ElevenLabsError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"texto": texto}


@app.post("/api/voz")
async def voz(req: TTSRequest):
    """Devuelve el audio MP3 con ElevenLabs. 204 si no está configurado (la app usa la voz del navegador)."""
    if not settings.elevenlabs_enabled:
        return Response(status_code=204)
    voice = req.voz_id or st.load()["perfil"].get("voz_id") or None
    try:
        audio = await elevenlabs.synthesize(req.texto, voice)
    except elevenlabs.ElevenLabsError as exc:
        log.warning("TTS falló: %s", exc)
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")


# ------------------------------------------------------------------ bandeja y demo
@app.get("/api/mensajes")
def mensajes():
    return st.load()["mensajes"]


@app.post("/api/demo/entrante")
async def demo_entrante(m: Incoming):
    """Simula que al móvil le llega un SMS/WhatsApp (para la demo en directo)."""
    msg = {"id": st.new_id("msg"), "fecha": st.now_iso(), "canal": m.canal, "remitente": m.remitente, "texto": m.texto}

    def _do(s):
        s["mensajes"].insert(0, msg)
        s["mensajes"] = s["mensajes"][:50]

    st.update(_do)
    bus.publish("usuario", "mensaje", msg)
    return msg


@app.get("/api/demo/ejemplos")
def demo_ejemplos():
    return json.loads((DATA_DIR / "demo_messages.json").read_text(encoding="utf-8"))


@app.post("/api/demo/reset")
def demo_reset():
    s = st.reset()
    bus.publish_many(["usuario", "familia", "banco"], "reset", {})
    return {"ok": True, "perfil": s["perfil"]}


# ------------------------------------------------------------------ alertas y familia
@app.get("/api/alertas")
def alertas():
    return st.load()["alertas"]


@app.post("/api/alertas/{alerta_id}/avisar")
async def avisar(alerta_id: str):
    alert = next((a for a in st.load()["alertas"] if a["id"] == alerta_id), None)
    if not alert:
        raise HTTPException(404, "Alerta no encontrada")
    return await notify_family(alert)


@app.post("/api/reportar")
def reportar(r: Reporte):
    dominios = [tools.registrable_domain(tools.host_of(u)) for u in r.enlaces]
    data = tools.add_report(r.telefonos, dominios)
    return {"ok": True, "telefonos": len(data["telefonos"]), "dominios": len(data["dominios"])}


# ------------------------------------------------------------------ banco simulado
@app.get("/api/banco")
def get_banco():
    return bank.get_bank()


@app.post("/api/banco/transferencia")
def transferencia(t: Transferencia):
    return bank.request_transfer(t.beneficiario, t.iban, t.importe, t.concepto, t.canal)


@app.post("/api/banco/transferencias/{tx_id}/{accion}")
def resolver(tx_id: str, accion: str):
    if accion not in {"aprobar", "cancelar"}:
        raise HTTPException(400, "Acción no válida")
    tx = bank.resolve_transfer(tx_id, accion == "aprobar")
    if not tx:
        raise HTTPException(404, "Operación no encontrada o ya resuelta")
    return tx


@app.post("/api/banco/escudo/{accion}")
def escudo(accion: str):
    if accion == "activar":
        return bank.activate_shield("Activado manualmente")
    if accion == "desactivar":
        return bank.deactivate_shield()
    raise HTTPException(400, "Acción no válida")


# ------------------------------------------------------------------ tiempo real
@app.get("/api/eventos/{canal}")
async def eventos(canal: str, request: Request):
    if canal not in {"usuario", "familia", "banco"}:
        raise HTTPException(404)
    q = bus.subscribe(canal)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15)
                    yield sse_format(payload)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(canal, q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ Web Share Target (PWA instalada)
@app.post("/share-target")
async def share_target(
    title: str = Form(""), text: str = Form(""), url: str = Form(""), media: UploadFile | None = File(None),
):
    """Recibe lo que el usuario comparte desde WhatsApp/SMS con «Compartir → Centinela»."""
    upload = await _read_upload(media)
    share_id = st.new_id("sh")
    _shares[share_id] = {
        "texto": "\n".join(x for x in (title, text, url) if x).strip(),
        "archivo": None if not upload else {
            "nombre": upload[1], "tipo": upload[2], "datos": base64.b64encode(upload[0]).decode(),
        },
        "t": time.time(),
    }
    for k in [k for k, v in _shares.items() if time.time() - v["t"] > 600]:
        _shares.pop(k, None)
    return RedirectResponse(f"/?compartido={share_id}", status_code=303)


@app.get("/api/compartido/{share_id}")
def compartido(share_id: str):
    data = _shares.pop(share_id, None)
    if not data:
        raise HTTPException(404, "Contenido compartido no encontrado o caducado")
    return data


# ------------------------------------------------------------------ frontend
@app.get("/sw.js")
def service_worker():
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
