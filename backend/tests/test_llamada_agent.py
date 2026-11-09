"""Agente del escudo de llamada con un cliente de Claude simulado (sin red)."""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.llamada import agent

VALID = {"message": "¿Estás hablando por teléfono con alguien ahora mismo?", "typology": "ninguna",
         "risk": "medium", "redFlags": [], "readyToDecide": False}
TRANSFER = {"amount": 8500.0, "beneficiaryName": "Cuenta segura", "concept": "Protección de fondos"}
SIGNALS = [{"id": "llamada_activa", "weight": 35, "detail": "El cliente está en una llamada"}]


def resp(payload, stop="end_turn"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return NS(stop_reason=stop, content=[NS(type="thinking", thinking=""), NS(type="text", text=text)])


class FakeMessages:
    def __init__(self, responses, delay=0.0):
        self.responses = list(responses)
        self.calls = []
        self.delay = delay

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.responses.pop(0)


def fake(responses, delay=0.0):
    msgs = FakeMessages(responses, delay)
    return NS(messages=msgs), msgs


def run(client, transcript=()):
    return asyncio.run(agent.next_turn(TRANSFER, SIGNALS, list(transcript), client=client))


def test_valid_turn_parsed_and_request_shape():
    client, msgs = fake([resp(VALID)])
    out = run(client, [{"role": "agent", "text": "Hola"}, {"role": "client", "text": "Sí, es del banco"}])
    assert out == VALID
    call = msgs.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "low"
    user_text = call["messages"][0]["content"]
    assert "8.500" in user_text and "El cliente está en una llamada" in user_text
    assert "Sí, es del banco" in user_text
    assert "35" not in user_text and "puntuación" not in user_text.lower()


def test_invalid_json_retries_once_then_unavailable():
    client, msgs = fake([resp("no json"), resp("no json")])
    with pytest.raises(agent.AgentUnavailable):
        run(client)
    assert len(msgs.calls) == 2


def test_retry_recovers():
    client, msgs = fake([resp("no json"), resp(VALID)])
    assert run(client) == VALID
    assert len(msgs.calls) == 2


def test_schema_violation_is_failure():
    bad = {**VALID, "risk": "very_high"}
    missing = {k: v for k, v in VALID.items() if k != "message"}
    client, _ = fake([resp(bad), resp(missing)])
    with pytest.raises(agent.AgentUnavailable):
        run(client)


def test_timeout_is_failure(monkeypatch):
    monkeypatch.setattr(agent, "TIMEOUT_S", 0.05)
    client, msgs = fake([resp(VALID), resp(VALID)], delay=1.0)
    with pytest.raises(agent.AgentUnavailable):
        run(client)
    assert len(msgs.calls) == 2


def test_refusal_is_failure():
    client, _ = fake([resp("", stop="refusal"), resp("", stop="refusal")])
    with pytest.raises(agent.AgentUnavailable):
        run(client)


def test_offline_without_client_raises_without_calling(monkeypatch):
    monkeypatch.setattr(agent, "get_client", lambda: pytest.fail("no debe crear cliente"))
    with pytest.raises(agent.AgentUnavailable):
        run(None)
