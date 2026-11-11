"""Análisis de SMS simulados con clientes locales concurrentes."""
import asyncio

import httpx
from fastapi.testclient import TestClient

from app import analyzer
from app.events import bus
from app.main import app


SMS = {"texto": "Hola mamá, este es mi número nuevo. Necesito un Bizum de 600 euros urgente.",
       "remitente": "+34711000222"}
LOCAL = ("127.0.0.1", 50000)
URL = "http://127.0.0.1"


def test_reintento_y_dos_clientes_comparten_un_resultado(monkeypatch):
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        compute = analyzer._compute_stream
        events = []
        publish = bus.publish

        def observe(channel, name, data):
            events.append((channel, name, data))
            publish(channel, name, data)

        async def slow(*args):
            entered.set()
            await release.wait()
            async for event in compute(*args):
                yield event

        monkeypatch.setattr(bus, "publish", observe)
        monkeypatch.setattr(analyzer, "_compute_stream", slow)
        transport = httpx.ASGITransport(app=app, client=LOCAL)
        async with httpx.AsyncClient(transport=transport, base_url=URL) as local:
            send = asyncio.create_task(local.post("/api/demo/entrante", json=SMS))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                message = (await local.get("/api/mensajes")).json()[0]
                pending = await local.post("/api/analizar", data={"mensaje_id": message["id"], "texto": "Otro texto"})
                assert pending.status_code == 202 and pending.json()["pendiente"]
            finally:
                release.set()
            result = (await send).json()["resultado"]
            retry = await local.post("/api/analizar", data={"mensaje_id": message["id"], "texto": "Otro texto"})
            assert retry.json() == result and result["texto"] == SMS["texto"]
            assert result["veredicto"]["nivel"] == "rojo"
            assert len((await local.get("/api/alertas")).json()) == 1
            assert (await local.get("/api/banco")).json()["escudo"]["alerta_id"] == result["alerta_id"]
        assert len([event for event in events if event[:2] == ("familia", "alerta")]) == 1
        assert len([event for event in events if event[:2] == ("familia", "escudo")]) == 1
        assert len([event for event in events if event[:2] == ("familia", "aviso_familiar")]) == 1

    asyncio.run(run())


def test_reinicio_invalida_sms_en_analisis(monkeypatch):
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        compute = analyzer._compute_stream

        async def slow(*args):
            entered.set()
            await release.wait()
            async for event in compute(*args):
                yield event

        monkeypatch.setattr(analyzer, "_compute_stream", slow)
        transport = httpx.ASGITransport(app=app, client=LOCAL)
        async with httpx.AsyncClient(transport=transport, base_url=URL) as local:
            send = asyncio.create_task(local.post("/api/demo/entrante", json=SMS))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                message = (await local.get("/api/mensajes")).json()[0]
                assert (await local.post("/api/demo/reset")).status_code == 200
            finally:
                release.set()
            await send
            assert (await local.get("/api/mensajes")).json() == []
            assert (await local.get("/api/alertas")).json() == []
            assert not (await local.get("/api/banco")).json()["escudo"]["activo"]
            assert (await local.post("/api/analizar", data={"mensaje_id": message["id"]})).status_code == 422

    asyncio.run(run())


def test_si_falla_el_calculo_se_puede_reintentar(monkeypatch):
    compute = analyzer._compute_stream
    attempts = 0

    async def fail_once(*args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            yield {"tipo": "error", "texto": "Fallo simulado"}
            return
        async for event in compute(*args):
            yield event

    monkeypatch.setattr(analyzer, "_compute_stream", fail_once)
    with TestClient(app, base_url=URL, client=LOCAL) as local:
        msg = local.post("/api/demo/entrante", json=SMS).json()
        assert "resultado" not in msg
        assert local.get("/api/alertas").json() == []
        result = local.post("/api/analizar", data={"mensaje_id": msg["id"]}).json()
        assert result["veredicto"]["nivel"] == "rojo"
        assert len(local.get("/api/alertas").json()) == 1 and attempts == 2


def test_proteccion_apagada_deja_el_sms_disponible_para_revision_manual():
    with TestClient(app, base_url=URL, client=LOCAL) as local:
        local.put("/api/perfil", json={"proteccion_activa": False})
        msg = local.post("/api/demo/entrante", json=SMS).json()
        assert "resultado" not in msg and local.get("/api/alertas").json() == []
        result = local.post("/api/analizar", data={"mensaje_id": msg["id"]}).json()
        assert result["texto"] == SMS["texto"] and result["veredicto"]["nivel"] == "rojo"
