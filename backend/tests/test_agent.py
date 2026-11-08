"""Prueba el bucle del agente con un cliente de Claude simulado (sin red)."""
import asyncio
import json
from types import SimpleNamespace as NS

from app import agent
from app.rules import analyze_rules


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _fake_client(responses):
    msgs = FakeMessages(responses)
    return NS(beta=NS(messages=msgs)), msgs


VERDICT = {
    "nivel": "rojo", "puntuacion": 92, "titulo": "Es un timo", "tipo_estafa": "Falso banco",
    "explicacion": "La web imita a MyInvestor.", "pruebas": ["La web no es la oficial"],
    "consejo": "No pulses el enlace.", "mensaje_voz": "Cuidado, es un timo.",
}


def test_agent_tool_loop_then_verdict(monkeypatch):
    responses = [
        NS(stop_reason="tool_use", model="m", content=[
            NS(type="tool_use", id="t1", name="analizar_enlace", input={"url": "https://myinvestor-seguridad.com"}),
        ]),
        NS(stop_reason="end_turn", model="m", content=[NS(type="text", text=json.dumps(VERDICT))]),
    ]
    fake, msgs = _fake_client(responses)
    monkeypatch.setattr(agent, "client", lambda: fake)
    rules = analyze_rules("Verifique en https://myinvestor-seguridad.com", "MyInvestor", [])

    async def run():
        return [ev async for ev in agent.investigate("Verifique en https://myinvestor-seguridad.com", "MyInvestor", "sms", rules, [], None)]

    events = asyncio.run(run())
    assert events[-1]["tipo"] == "veredicto"
    assert events[-1]["datos"]["nivel"] == "rojo"
    assert events[-1]["datos"]["herramientas_usadas"][0]["herramienta"] == "analizar_enlace"
    # el resultado de la herramienta se devolvió a Claude
    tool_result = msgs.calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "MyInvestor" in tool_result["content"]
    # usa salida estructurada y fallback por defecto
    assert msgs.calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert msgs.calls[0]["fallbacks"] == "default"


def test_agent_refusal_raises(monkeypatch):
    fake, _ = _fake_client([NS(stop_reason="refusal", model="m", content=[])])
    monkeypatch.setattr(agent, "client", lambda: fake)
    rules = analyze_rules("hola", None, [])

    async def run():
        return [ev async for ev in agent.investigate("hola", None, "sms", rules, [], None)]

    try:
        asyncio.run(run())
        raise AssertionError("debería fallar")
    except agent.AgentError:
        pass
