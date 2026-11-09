"""Orquestación del escudo de llamada: transferencia → riesgo → agente → política.

Embudo: las reglas se aplican a todas las transferencias; el agente solo entra
cuando la puntuación llega al umbral. Ante cualquier fallo del agente, la
transferencia arriesgada no se ejecuta y pasa a un analista.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .. import tools
from ..config import settings
from . import agent, store
from .seed import FLAGGED_IBANS
from .policy import CLOSING_TEXTS, decide, hard_rule_applies
from .risk import THRESHOLD, evaluate_risk, normalize_iban

STATUS_BY_ACTION = {"execute": "ejecutada", "hold": "retenida", "review": "pendiente"}
OPEN_FOR_ANALYST = {"retenida", "pendiente"}


class ServiceError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _now().isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------- estado y demo
def get_state() -> dict:
    s = store.snapshot()
    return {
        "client": s["client"], "accounts": s["accounts"], "beneficiaries": s["beneficiaries"],
        "movements": s["movements"], "callActive": s["callActive"],
        "agentEnabled": settings.claude_enabled, "model": agent.MODEL,
    }


def set_call(active: bool) -> dict:
    def _do(s):
        s["callActive"] = bool(active)
        return {"callActive": s["callActive"]}
    return store.mutate(_do)


def reset() -> dict:
    store.reset()
    return {"ok": True}


def internal_transfer(amount: float) -> dict:
    def _do(s):
        acc = s["accounts"]
        if amount > acc["ahorro"]["balance"]:
            raise ServiceError(422, "Saldo insuficiente en la cuenta de ahorro")
        acc["ahorro"]["balance"] = round(acc["ahorro"]["balance"] - amount, 2)
        acc["corriente"]["balance"] = round(acc["corriente"]["balance"] + amount, 2)
        mov = {"type": "internal_in", "amount": round(amount, 2), "ts": _iso(), "name": "Traspaso desde ahorro"}
        s["movements"].insert(0, mov)
        return {"accounts": acc, "movement": mov}
    return store.mutate(_do)


# ---------------------------------------------------------------- utilidades internas
def _execute(s: dict, amount: float, iban: str, name: str, concept: str) -> dict:
    acc = s["accounts"]["corriente"]
    if amount > acc["balance"]:
        raise ServiceError(422, "Saldo insuficiente")
    acc["balance"] = round(acc["balance"] - amount, 2)
    mov = {"type": "transfer_out", "amount": round(amount, 2), "ts": _iso(), "name": name, "iban": iban, "concept": concept}
    s["movements"].insert(0, mov)
    return mov


def _find_case(s: dict, *, case_id: str | None = None, conv_id: str | None = None) -> dict | None:
    for c in s["cases"]:
        if (case_id and c["id"] == case_id) or (conv_id and c["conversationId"] == conv_id):
            return c
    return None


def _set_transfer_status(s: dict, transfer_id: str, status: str) -> None:
    for t in s["transfers"]:
        if t["id"] == transfer_id:
            t["status"] = status


def _finalize(s: dict, case: dict, assessment: dict | None, ready: bool) -> None:
    signal_ids = [x["id"] for x in case["signals"]]
    decision = decide(signal_ids, assessment, ready)
    if decision["action"] == "execute":
        try:
            _execute(s, case["amount"], case["iban"], case["beneficiaryName"], case["concept"])
        except ServiceError:
            decision = {**decision, "action": "review", "reasons": decision["reasons"] + ["saldo insuficiente al ejecutar"]}
    case["status"] = STATUS_BY_ACTION[decision["action"]]
    case["decision"] = {**decision, "ts": _iso()}
    case["outcome"] = {"action": decision["action"], "text": CLOSING_TEXTS[decision["action"]]}
    _set_transfer_status(s, case["transferId"], case["status"])


def _view(case: dict) -> dict:
    done = case["status"] != "en_conversacion"
    message = None if done else next((t["text"] for t in reversed(case["transcript"]) if t["role"] == "agent"), None)
    return {"conversationId": case["conversationId"], "done": done, "message": message,
            "outcome": case.get("outcome") if done else None}


def _agent_input(case: dict) -> tuple[dict, list[dict], list[dict]]:
    transfer = {"amount": case["amount"], "beneficiaryName": case["beneficiaryName"], "concept": case["concept"]}
    return transfer, [dict(x) for x in case["signals"]], [dict(t) for t in case["transcript"]]


async def _ask_agent(case: dict) -> dict | None:
    try:
        return await agent.next_turn(*_agent_input(case))
    except agent.AgentUnavailable:
        return None


# ---------------------------------------------------------------- transferencias
async def request_transfer(amount: float, iban: str, beneficiary_name: str, concept: str,
                           call_active: bool, iban_pasted: bool) -> dict:
    iban = normalize_iban(iban)
    if not tools.analyze_iban(iban)["valido"]:
        raise ServiceError(422, "El IBAN no es válido")

    def _create(s):
        if amount > s["accounts"]["corriente"]["balance"]:
            raise ServiceError(422, "Saldo insuficiente")
        risk = evaluate_risk(amount, iban, call_active, iban_pasted, s["beneficiaries"], s["movements"],
                             FLAGGED_IBANS, _now())
        tx = {"id": _id("tx"), "ts": _iso(), "amount": round(amount, 2), "iban": iban,
              "beneficiaryName": beneficiary_name, "concept": concept, "score": risk["score"]}
        s["transfers"].insert(0, tx)
        if risk["score"] < THRESHOLD:
            _execute(s, amount, iban, beneficiary_name, concept)
            tx["status"] = "ejecutada"
            return {"status": "executed", "transfer": dict(tx)}, None
        tx["status"] = "en_conversacion"
        case = {
            "id": _id("case"), "conversationId": _id("conv"), "transferId": tx["id"], "createdAt": _iso(),
            "amount": round(amount, 2), "beneficiaryName": beneficiary_name, "iban": iban, "concept": concept,
            "callActive": call_active, "score": risk["score"], "signals": risk["signals"],
            "status": "en_conversacion", "agentTurns": 0, "transcript": [], "assessment": None,
            "decision": None, "outcome": None, "awaiting": True,
        }
        s["cases"].insert(0, case)
        return None, {k: (list(v) if isinstance(v, list) else v) for k, v in case.items()}

    executed, case = store.mutate(_create)
    if executed:
        return executed

    assessment = await _ask_agent(case)

    def _first_turn(s):
        c = _find_case(s, case_id=case["id"])
        if c is None:
            raise ServiceError(404, "Conversación no encontrada")
        c["awaiting"] = False
        if assessment is None:
            _finalize(s, c, None, ready=False)
        else:
            # En el primer turno el agente siempre pregunta: su readyToDecide se ignora.
            c["agentTurns"] = 1
            c["assessment"] = assessment
            c["transcript"].append({"role": "agent", "text": assessment["message"], "ts": _iso()})
        return {"status": "on_hold", **_view(c)}

    return store.mutate(_first_turn)


async def reply(conv_id: str, text: str) -> dict:
    def _add(s):
        c = _find_case(s, conv_id=conv_id)
        if c is None:
            raise ServiceError(404, "Conversación no encontrada")
        if c["status"] != "en_conversacion" or c["awaiting"]:
            raise ServiceError(409, "Esta conversación ya no admite respuestas")
        c["transcript"].append({"role": "client", "text": text, "ts": _iso()})
        c["awaiting"] = True
        return {"id": c["id"], "amount": c["amount"], "beneficiaryName": c["beneficiaryName"],
                "concept": c["concept"], "signals": c["signals"], "transcript": list(c["transcript"])}

    snapshot = store.mutate(_add)
    assessment = await _ask_agent(snapshot)

    def _after(s):
        c = _find_case(s, case_id=snapshot["id"])
        if c is None:
            raise ServiceError(404, "Conversación no encontrada")
        c["awaiting"] = False
        if assessment is None:
            _finalize(s, c, None, ready=False)
            return _view(c)
        c["agentTurns"] += 1
        c["assessment"] = assessment
        signal_ids = [x["id"] for x in c["signals"]]
        ready = assessment["readyToDecide"]
        if ready or hard_rule_applies(signal_ids, assessment) or c["agentTurns"] >= agent.MAX_AGENT_TURNS:
            _finalize(s, c, assessment, ready=ready)
        else:
            c["transcript"].append({"role": "agent", "text": assessment["message"], "ts": _iso()})
        return _view(c)

    return store.mutate(_after)


# ---------------------------------------------------------------- analista
def list_cases() -> list[dict]:
    return store.snapshot()["cases"]


def analyst_decision(case_id: str, decision: str) -> dict:
    def _do(s):
        c = _find_case(s, case_id=case_id)
        if c is None:
            raise ServiceError(404, "Caso no encontrado")
        if c["status"] not in OPEN_FOR_ANALYST:
            raise ServiceError(409, "Este caso ya está resuelto")
        if decision == "release":
            _execute(s, c["amount"], c["iban"], c["beneficiaryName"], c["concept"])  # 422 si no hay saldo
            c["status"] = "liberada"
        else:
            c["status"] = "bloqueada"
        c["analystDecision"] = {"decision": decision, "ts": _iso()}
        _set_transfer_status(s, c["transferId"], c["status"])
        return dict(c)

    return store.mutate(_do)
