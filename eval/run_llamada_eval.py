"""Evaluación manual del escudo de llamada con el modelo real (antes de la demo).

Ejecuta guiones de conversación contra el agente y comprueba que el resultado
es estable: el escenario 3 (víctima guiada) debe terminar retenido y el
escenario 2 (casero) ejecutado.

Uso (desde la raíz del repo, con ANTHROPIC_API_KEY en .env):
    python eval/run_llamada_eval.py --veces 3
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.llamada import agent, seed  # noqa: E402
from app.llamada.policy import decide, hard_rule_applies  # noqa: E402
from app.llamada.risk import evaluate_risk  # noqa: E402

NOW = datetime.now(timezone.utc)

GUIONES = [
    {
        "nombre": "estafa (víctima guiada)",
        "preset": "estafa",
        "traspaso_previo": True,
        "esperado": "hold",
        "respuestas": [
            "Sí, estoy hablando con el departamento de seguridad del banco, me dicen que hay un ataque en mi cuenta.",
            "Me han dicho que es una cuenta segura del banco y que no lo cuente en la oficina porque hay un empleado implicado.",
            "Es para proteger mis ahorros, ellos me lo devuelven mañana.",
        ],
    },
    {
        "nombre": "casero (legítima con llamada)",
        "preset": "casero",
        "traspaso_previo": False,
        "esperado": "execute",
        "respuestas": [
            "Sí, estoy hablando con Antonio, mi casero. Le pago el alquiler de noviembre como cada mes; antes le pagaba en efectivo.",
            "Nadie me ha pedido que no lo cuente, es mi casero de toda la vida.",
            "Sí, el piso de la calle Mayor, llevo diez años allí.",
        ],
    },
]


async def run_guion(g: dict) -> dict:
    p = seed.PRESETS[g["preset"]]
    movements = list(seed.SEED["movements"])
    if g["traspaso_previo"]:
        movements.append({"type": "internal_in", "amount": 8000.0, "ts": (NOW - timedelta(minutes=4)).isoformat()})
    risk = evaluate_risk(p["amount"], p["iban"], True, p["ibanPasted"], seed.SEED["beneficiaries"], movements,
                         seed.FLAGGED_IBANS, NOW)
    transfer = {"amount": p["amount"], "beneficiaryName": p["beneficiaryName"], "concept": p["concept"]}
    signal_ids = [s["id"] for s in risk["signals"]]
    transcript: list[dict] = []
    assessment = None
    ready = False
    try:
        assessment = await agent.next_turn(transfer, risk["signals"], transcript)
        transcript.append({"role": "agent", "text": assessment["message"]})
        turns = 1
        for answer in g["respuestas"]:
            transcript.append({"role": "client", "text": answer})
            assessment = await agent.next_turn(transfer, risk["signals"], transcript)
            turns += 1
            ready = assessment["readyToDecide"]
            if ready or hard_rule_applies(signal_ids, assessment) or turns >= agent.MAX_AGENT_TURNS:
                break
            transcript.append({"role": "agent", "text": assessment["message"]})
    except agent.AgentUnavailable:
        assessment = None
    decision = decide(signal_ids, assessment, ready)
    return {"decision": decision, "assessment": assessment, "transcript": transcript}


async def main(veces: int) -> int:
    if not settings.claude_enabled:
        print("Falta ANTHROPIC_API_KEY en .env (o FORCE_OFFLINE está activo): esta evaluación necesita el modelo real.")
        return 1
    print(f"Modelo: {agent.MODEL} · {veces} ejecuciones por guion\n")
    print(f"{'guion':32} {'#':>2}  {'acción':8} {'regla':18} {'risk':7} redFlags")
    fallos = 0
    for g in GUIONES:
        for i in range(1, veces + 1):
            r = await run_guion(g)
            d, a = r["decision"], r["assessment"] or {}
            ok = d["action"] == g["esperado"]
            fallos += not ok
            print(f"{g['nombre']:32} {i:>2}  {d['action']:8} {d['rule']:18} {a.get('risk', '-'):7} "
                  f"{','.join(a.get('redFlags', [])) or '-'}{'' if ok else '   <-- FALLO (esperado ' + g['esperado'] + ')'}")
            if not ok:
                for t in r["transcript"]:
                    print(f"      {'Escudo' if t['role'] == 'agent' else 'Cliente'}: {t['text']}")
    print(f"\n{'Todo estable' if not fallos else f'{fallos} ejecución(es) no dieron el resultado esperado'}.")
    return 0 if not fallos else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--veces", type=int, default=3)
    sys.exit(asyncio.run(main(parser.parse_args().veces)))
