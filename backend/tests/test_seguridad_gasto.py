"""Rutas de administración solo desde el portátil, tope de gasto diario y reglas nuevas (11-11-2026).

Ideas tomadas de hackaton-finance-antifraude: seguridad de la API local (ADR 0013) y control de costes de la IA
(ai/budget.py). Las reglas nuevas cubren dos huecos que el motor de antifraude sí detectaba; los mensajes de
abajo están redactados de nuevo (no copiados de su conjunto de evaluación).
"""
import asyncio
import json
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import agent, budget, elevenlabs
from app.config import settings
from app.llamada import agent as llamada_agent
from app.main import app
from app.rules import analyze_rules

ADMIN_POST = ["/api/demo/reset", "/api/llamada/demo/reset", "/api/banco/escudo/desactivar"]
ADMIN_GET = ["/api/alertas", "/api/llamada/cases", "/api/gasto"]


@pytest.fixture
def protegido(monkeypatch):
    monkeypatch.setattr(settings, "admin_remoto", False)


# ------------------------------------------------------------------ rutas de administración
@pytest.mark.parametrize("ruta", ADMIN_POST)
def test_admin_post_bloqueado_desde_otro_dispositivo(protegido, ruta):
    movil = TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.50", 50000))
    r = movil.post(ruta)
    assert r.status_code == 403
    assert "ordenador de la demo" in r.json()["detail"]


@pytest.mark.parametrize("ruta", ADMIN_GET)
def test_admin_get_bloqueado_desde_otro_dispositivo(protegido, ruta):
    assert TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.50", 50000)).get(ruta).status_code == 403


def test_simular_mensaje_y_decidir_caso_bloqueados(protegido):
    movil = TestClient(app, base_url="http://127.0.0.1", client=("10.0.0.7", 50000))
    assert movil.post("/api/demo/entrante", json={"texto": "hola"}).status_code == 403
    assert movil.post("/api/llamada/cases/x/decision", json={"decision": "release"}).status_code == 403
    assert movil.post("/api/llamada/demo/call", json={"active": True}).status_code == 403
    assert movil.post("/api/banco/transferencias/x/aprobar").status_code == 403


@pytest.mark.parametrize("ruta", ["/api/perfil", "/api/banco", "/api/llamada/state", "/api/mensajes",
                                  "/api/eventos/familia", "/api/eventos/usuario", "/api/eventos/banco",
                                  "/api/compartido/sin-id", "/openapi.json"])
def test_lecturas_y_eventos_rechazados_desde_otro_dispositivo(ruta):
    movil = TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.50", 50000))
    assert movil.get(ruta).status_code == 403


@pytest.mark.parametrize(("metodo", "ruta"), [("PUT", "/api/perfil"), ("POST", "/api/llamada/transfers"),
                                            ("POST", "/api/analizar"), ("POST", "/share-target")])
def test_escrituras_rechazadas_antes_de_procesar_el_cuerpo(metodo, ruta):
    movil = TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.50", 50000))
    assert movil.request(metodo, ruta).status_code == 403


def test_host_ajeno_y_origen_ajeno_rechazados_en_loopback():
    local = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    assert local.get("/api/perfil", headers={"Host": "ajeno.example"}).status_code == 400
    assert local.post("/api/demo/reset", headers={"Origin": "http://127.0.0.1:9000"}).status_code == 403
    assert local.post("/api/demo/reset", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    same_origin = {"Origin": "http://127.0.0.1:8000", "Sec-Fetch-Site": "same-origin"}
    assert local.post("/api/demo/reset", headers=same_origin).status_code == 200
    assert local.post("/api/analizar", data={"texto": "Hola"}, headers=same_origin).status_code == 200
    share = local.post("/share-target", files={"text": (None, "Mensaje de prueba")}, headers=same_origin,
                       follow_redirects=False)
    assert share.status_code == 303


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_admin_permitido_desde_el_portatil(protegido, host):
    portatil = TestClient(app, base_url="http://127.0.0.1", client=(host, 50000))
    assert portatil.post("/api/demo/reset").status_code == 200
    assert portatil.get("/api/gasto").status_code == 200


def test_tunel_se_trata_como_remoto(protegido):
    """cloudflared/ngrok reenvían desde 127.0.0.1 pero añaden cabeceras de reenvío."""
    tunel = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000), headers={"X-Forwarded-For": "203.0.113.9"})
    assert tunel.post("/api/demo/reset").status_code == 403


def test_admin_remoto_no_desactiva_la_proteccion_del_perfil_local(monkeypatch):
    monkeypatch.setattr(settings, "admin_remoto", True)
    assert TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.50", 50000)).post("/api/demo/reset").status_code == 403


def test_configuracion_de_entrega_prevalece_sobre_variables_heredadas():
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {**os.environ, "CENTINELA_DEMO_LOCAL": "1", "ADMIN_REMOTO": "1", "FORCE_OFFLINE": "0",
           "ONLINE_CHECKS": "1", "ANTHROPIC_API_KEY": "falsa", "ELEVENLABS_API_KEY": "falsa",
           "TELEGRAM_BOT_TOKEN": "falso", "TELEGRAM_CHAT_ID": "falso", "PYTHONDONTWRITEBYTECODE": "1"}
    code = """
from app.config import settings
assert settings.anthropic_api_key == "falsa" and settings.elevenlabs_api_key == "falsa"
assert settings.telegram_bot_token == "falso"
assert settings.demo_local and settings.force_offline
assert not settings.online_checks and not settings.admin_remoto
assert not settings.claude_enabled and not settings.elevenlabs_enabled and not settings.telegram_enabled
"""
    subprocess.run([sys.executable, "-c", code], env=env, cwd=Path(__file__).resolve().parents[1], check=True)


# ------------------------------------------------------------------ tope de gasto
def test_tope_de_llamadas_a_claude(monkeypatch):
    monkeypatch.setattr(settings, "ia_max_llamadas_dia", 2)
    budget.reserve_claude(100)
    budget.reserve_claude(100)
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve_claude(100)
    assert budget.status()["uso"]["claude_llamadas"] == 2


def test_reserva_por_el_peor_caso_y_ajuste_con_el_uso_real(monkeypatch):
    monkeypatch.setattr(settings, "ia_max_tokens_dia", 10_000)
    reservado = budget.reserve_claude(8000)
    assert budget.status()["uso"]["claude_tokens"] == 8000
    with pytest.raises(budget.BudgetExceeded):  # no cabe otra llamada de peor caso
        budget.reserve_claude(8000)
    budget.settle_claude(reservado, NS(input_tokens=1200, output_tokens=300))
    assert budget.status()["uso"]["claude_tokens"] == 1500
    budget.reserve_claude(8000)  # ahora sí cabe


def test_sin_usage_se_queda_la_reserva():
    reservado = budget.reserve_claude(2000)
    budget.settle_claude(reservado, None)
    assert budget.status()["uso"]["claude_tokens"] == 2000


def test_el_contador_se_reinicia_cada_dia():
    ayer = (date.today() - timedelta(days=1)).isoformat()
    budget.GASTO_FILE.write_text(json.dumps({"dia": ayer, "claude_llamadas": 999, "claude_tokens": 10**9,
                                             "voz_caracteres": 10**9, "transcripciones": 999}))
    assert budget.status()["uso"] == {"claude_llamadas": 0, "claude_tokens": 0, "voz_caracteres": 0, "transcripciones": 0}


def test_el_contador_no_guarda_textos():
    budget.reserve_voice(len("Cuidado: muy probablemente es una estafa"))
    guardado = budget.GASTO_FILE.read_text()
    assert "estafa" not in guardado and set(json.loads(guardado)) == {
        "dia", "claude_llamadas", "claude_tokens", "voz_caracteres", "transcripciones"}


def test_agente_sin_presupuesto_no_llama_a_claude(monkeypatch):
    monkeypatch.setattr(settings, "ia_max_llamadas_dia", 0)

    def no_llamar():
        raise AssertionError("no debe llamar a Claude sin presupuesto")

    monkeypatch.setattr(agent, "client", no_llamar)
    rules = analyze_rules("Hola mamá, este es mi número nuevo", None, [])

    async def consumir():
        async for _ in agent.investigate("Hola mamá, este es mi número nuevo", None, "sms", rules, [], None):
            pass

    with pytest.raises(agent.AgentError, match="tope diario"):
        asyncio.run(consumir())


def test_escudo_de_llamada_sin_presupuesto_pasa_al_analista(monkeypatch):
    monkeypatch.setattr(settings, "ia_max_llamadas_dia", 0)
    llamadas = []

    async def create(**kwargs):
        llamadas.append(kwargs)

    falso = NS(messages=NS(create=create))
    with pytest.raises(llamada_agent.AgentUnavailable):
        asyncio.run(llamada_agent.next_turn({"amount": 8500.0, "beneficiaryName": "X", "concept": ""}, [], [],
                                            client=falso))
    assert llamadas == []


def test_voz_y_transcripcion_respetan_el_tope(monkeypatch):
    monkeypatch.setattr(settings, "elevenlabs_api_key", "clave-falsa")
    monkeypatch.setattr(settings, "force_offline", False)
    monkeypatch.setattr(settings, "voz_max_caracteres_dia", 10)
    monkeypatch.setattr(settings, "voz_max_transcripciones_dia", 0)
    with pytest.raises(elevenlabs.ElevenLabsError, match="tope diario"):
        asyncio.run(elevenlabs.synthesize("Este texto tiene más de diez caracteres"))
    with pytest.raises(elevenlabs.ElevenLabsError, match="tope diario"):
        asyncio.run(elevenlabs.transcribe(b"audio", "nota.ogg", "audio/ogg"))


def test_voz_al_tope_responde_204_y_la_app_usa_la_voz_del_navegador(monkeypatch):
    monkeypatch.setattr(settings, "elevenlabs_api_key", "clave-falsa")
    monkeypatch.setattr(settings, "force_offline", False)
    monkeypatch.setattr(settings, "voz_max_caracteres_dia", 0)
    assert TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)).post("/api/voz", json={"texto": "Hola"}).status_code == 204


# ------------------------------------------------------------------ reglas nuevas
@pytest.mark.parametrize("texto", [
    "Se ha realizado un pago con Bizum de 350,00 EUR desde su cuenta. Si no ha sido usted, anule la operación "
    "antes de 20 minutos en https://anular-pagos-bizum.top/cancelar",
    "Compra de 612,00 EUR en MediaMarkt con su tarjeta. Si usted no la ha autorizado, cancélela aquí: "
    "http://cancelar-compra.info/tarjeta",
])
def test_falso_cargo_con_enlace_para_anularlo(texto):
    r = analyze_rules(texto, None, [])
    assert "combo_cargo_enlace" in {s.id for s in r.signals}
    assert r.level in ("amarillo", "rojo")


def test_falso_gestor_pide_confirmar_identidad_con_datos_de_acceso():
    texto = ("Estimado cliente: estamos renovando el registro de dispositivos de la banca online. Entre en nuestra "
             "web y confirme su identidad con sus datos de acceso para seguir operando. Su gestor personal.")
    r = analyze_rules(texto, None, [])
    assert "pide_credenciales" in {s.id for s in r.signals}
    assert r.level in ("amarillo", "rojo")


@pytest.mark.parametrize("texto", [
    # aviso real: «si no has sido tú» pero sin enlace, te manda a tu canal de siempre
    "Has enviado un Bizum de 20,00 EUR a JAVIER M. Si no has sido tú, llama al número que aparece en tu tarjeta.",
    "Pago con tarjeta de 34,90 EUR en Mercadona. Si no reconoce esta operación, contacte con su oficina.",
])
def test_aviso_real_de_operacion_sin_enlace_sigue_en_verde(texto):
    assert analyze_rules(texto, None, []).level == "verde", texto
