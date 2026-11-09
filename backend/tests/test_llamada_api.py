"""Escudo de llamada (Banco Demo): estado, API y escenarios de la demo."""
import pytest
from fastapi.testclient import TestClient

from app.llamada import agent, seed, store
from app.llamada.policy import CLOSING_TEXTS
from app.main import app

client = TestClient(app)
BASE = "/api/llamada"


@pytest.fixture(autouse=True)
def fresh_bank():
    store.reset()
    yield
    store.reset()


def test_store_reset_restores_seed():
    store.mutate(lambda s: s["accounts"]["corriente"].update(balance=1))
    store.reset()
    snap = store.snapshot()
    assert snap["accounts"]["corriente"]["balance"] == 2300.0
    snap["accounts"]["corriente"]["balance"] = 5
    assert store.snapshot()["accounts"]["corriente"]["balance"] == 2300.0


# ---------------------------------------------------------------- utilidades
def A(risk="low", ready=False, flags=(), typology="ninguna", message="¿Estás hablando por teléfono con alguien?"):
    return {"message": message, "typology": typology, "risk": risk, "redFlags": list(flags), "readyToDecide": ready}


@pytest.fixture
def fake_agent(monkeypatch):
    calls = []

    def install(script):
        queue = list(script)

        async def next_turn(transfer, signals, transcript, client=None):
            calls.append([dict(t) for t in transcript])
            item = queue.pop(0)
            if item == "FAIL":
                raise agent.AgentUnavailable("agente no disponible")
            return item

        monkeypatch.setattr(agent, "next_turn", next_turn)
        return calls

    return install


def transfer(preset, call=False, **over):
    p = {**seed.PRESETS[preset], **over}
    body = {"amount": p["amount"], "iban": p["iban"], "beneficiaryName": p["beneficiaryName"],
            "concept": p["concept"], "context": {"callActive": call, "ibanPasted": p["ibanPasted"]}}
    return client.post(f"{BASE}/transfers", json=body)


def reply(conv_id, text="Sí"):
    return client.post(f"{BASE}/conversations/{conv_id}/messages", json={"text": text})


def balance():
    return client.get(f"{BASE}/state").json()["accounts"]["corriente"]["balance"]


def cases():
    return client.get(f"{BASE}/cases").json()


def open_estafa_case(fake_agent, second):
    calls = fake_agent([A("medium"), second])
    assert client.post(f"{BASE}/internal-transfer", json={"amount": 8000}).status_code == 200
    client.post(f"{BASE}/demo/call", json={"active": True})
    r = transfer("estafa", call=True)
    assert r.status_code == 200 and r.json()["status"] == "on_hold"
    return r.json(), calls


# ---------------------------------------------------------------- tests
def test_state_shape():
    s = client.get(f"{BASE}/state").json()
    assert s["client"]["name"] == "Carmen López" and s["client"]["bank"] == "Banco Demo"
    assert s["accounts"]["ahorro"]["balance"] == 14000.0
    assert s["callActive"] is False and s["agentEnabled"] is False and s["model"] == "claude-haiku-5-5"


def test_scenario_normal_executes_without_agent(fake_agent):
    calls = fake_agent([])
    r = transfer("normal")
    assert r.status_code == 200 and r.json()["status"] == "executed"
    assert balance() == 2100.0 and calls == [] and cases() == []


def test_scenario_casero_low_risk_executes(fake_agent):
    fake_agent([A("low", ready=True), A("low", ready=True, message="Gracias")])
    r = transfer("casero", call=True).json()
    assert r["status"] == "on_hold" and r["done"] is False and r["message"]
    out = reply(r["conversationId"], "Hablo con mi casero, es el alquiler").json()
    assert out["done"] is True and out["outcome"]["action"] == "execute"
    assert out["outcome"]["text"] == CLOSING_TEXTS["execute"]
    assert balance() == 1700.0
    assert cases()[0]["status"] == "ejecutada"


def test_scenario_estafa_held_and_analyst_blocks(fake_agent):
    r, calls = open_estafa_case(fake_agent, A("medium", flags=["suplantacion_banco"]))
    out = reply(r["conversationId"], "Sí, es del banco, me dicen que hay un ataque").json()
    assert out["done"] is True and out["outcome"]["action"] == "hold"
    assert out["outcome"]["text"] == CLOSING_TEXTS["hold"]
    case = cases()[0]
    assert case["status"] == "retenida" and case["score"] == 100 and case["decision"]["rule"] == "R1_suplantacion"
    assert [t["role"] for t in case["transcript"]] == ["agent", "client"]
    assert calls[1][-1]["text"].startswith("Sí, es del banco")
    d = client.post(f"{BASE}/cases/{case['id']}/decision", json={"decision": "block"})
    assert d.status_code == 200 and d.json()["status"] == "bloqueada"
    assert balance() == 10300.0


def test_analyst_release_executes(fake_agent):
    r, _ = open_estafa_case(fake_agent, A("high", ready=True))
    reply(r["conversationId"])
    case = cases()[0]
    assert case["status"] == "retenida"
    d = client.post(f"{BASE}/cases/{case['id']}/decision", json={"decision": "release"})
    assert d.json()["status"] == "liberada"
    assert balance() == 1800.0


def test_turn_limit_goes_to_review(fake_agent):
    fake_agent([A("low")] * 4)
    r = transfer("casero", call=True).json()
    assert reply(r["conversationId"]).json()["done"] is False
    assert reply(r["conversationId"]).json()["done"] is False
    out = reply(r["conversationId"]).json()
    assert out["done"] is True and out["outcome"]["action"] == "review"
    case = cases()[0]
    assert case["status"] == "pendiente" and case["decision"]["rule"] == "R5_sin_decision" and case["agentTurns"] == 4


def test_agent_unavailable_goes_to_review(fake_agent):
    fake_agent(["FAIL"])
    r = transfer("casero", call=True).json()
    assert r["status"] == "on_hold" and r["done"] is True and r["outcome"]["action"] == "review"
    assert r["outcome"]["text"] == CLOSING_TEXTS["review"]
    case = cases()[0]
    assert case["status"] == "pendiente" and "agente no disponible" in case["decision"]["reasons"]
    assert balance() == 2300.0


def test_agent_failure_mid_conversation_goes_to_review(fake_agent):
    fake_agent([A("low"), "FAIL"])
    r = transfer("casero", call=True).json()
    out = reply(r["conversationId"]).json()
    assert out["outcome"]["action"] == "review" and cases()[0]["status"] == "pendiente"


def test_insufficient_balance_rejected_before_risk(fake_agent):
    calls = fake_agent([])
    r = transfer("casero", call=True, amount=5000)
    assert r.status_code == 422 and "Saldo insuficiente" in r.text
    assert cases() == [] and calls == []


def test_invalid_input(fake_agent):
    fake_agent([A("low")])
    assert transfer("casero", iban="ES00 1234").status_code == 422
    assert transfer("casero", amount=0).status_code == 422
    r = transfer("casero", call=True).json()
    assert reply(r["conversationId"], "   ").status_code == 422
    assert client.post(f"{BASE}/internal-transfer", json={"amount": 999999}).status_code == 422


def test_reply_after_decision_conflicts(fake_agent):
    fake_agent([A("low"), A("low", ready=True)])
    r = transfer("casero", call=True).json()
    reply(r["conversationId"])
    assert reply(r["conversationId"]).status_code == 409
    assert balance() == 1700.0


def test_release_without_balance_keeps_case(fake_agent):
    r, _ = open_estafa_case(fake_agent, A("high", ready=True))
    reply(r["conversationId"])
    case = cases()[0]
    store.mutate(lambda s: s["accounts"]["corriente"].update(balance=100.0))
    d = client.post(f"{BASE}/cases/{case['id']}/decision", json={"decision": "release"})
    assert d.status_code == 422 and "Saldo insuficiente" in d.text
    assert cases()[0]["status"] == "retenida"


def test_decision_on_closed_or_unknown_case(fake_agent):
    assert client.post(f"{BASE}/cases/nope/decision", json={"decision": "block"}).status_code == 404
    fake_agent([A("low"), A("low", ready=True)])
    r = transfer("casero", call=True).json()
    reply(r["conversationId"])
    cid = cases()[0]["id"]
    assert client.post(f"{BASE}/cases/{cid}/decision", json={"decision": "block"}).status_code == 409
    assert client.post(f"{BASE}/cases/{cid}/decision", json={"decision": "otra"}).status_code == 422


def test_reset_invalidates_conversation(fake_agent):
    fake_agent([A("low"), A("low", ready=True)])
    r = transfer("casero", call=True).json()
    assert client.post(f"{BASE}/demo/reset").json() == {"ok": True}
    assert reply(r["conversationId"]).status_code == 404
    assert balance() == 2300.0


def test_demo_call_toggle():
    assert client.post(f"{BASE}/demo/call", json={"active": True}).json() == {"callActive": True}
    assert client.get(f"{BASE}/state").json()["callActive"] is True


def test_centinela_untouched(fake_agent):
    fake_agent([])
    transfer("normal")
    client.post(f"{BASE}/demo/reset")
    bank = client.get("/api/banco").json()
    assert bank["saldo"] == 12450.3 and "MyInvestor" in bank["entidad"]
