"""Motor de riesgo por reglas: barato, se aplica al 100 % de las transferencias.

Función pura: recibe la transferencia, el contexto y el historial y devuelve la
puntuación (0-100) y las señales activadas. No usa la edad del cliente.
"""
from __future__ import annotations

from datetime import datetime, timedelta

THRESHOLD = 40
RECENT_INTERNAL = timedelta(minutes=30)
UNUSUAL_FACTOR = 3

WEIGHTS: dict[str, int] = {
    "llamada_activa": 35,
    "beneficiario_nuevo": 20,
    "importe_inusual": 20,
    "traspaso_previo_ahorro": 20,
    "cuenta_destino_marcada": 25,
    "alerta_estafa_reciente": 25,
    "iban_pegado": 10,
}


def normalize_iban(s: str) -> str:
    return "".join(s.split()).upper()


def eur(n: float) -> str:
    """8500 -> «8.500 €»; 750.5 -> «750,50 €»."""
    whole = float(n).is_integer()
    txt = f"{n:,.0f}" if whole else f"{n:,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def evaluate_risk(amount: float, iban: str, call_active: bool, iban_pasted: bool,
                  beneficiaries: list[dict], movements: list[dict], flagged: list[str],
                  now: datetime, recent_alert: str | None = None) -> dict:
    target = normalize_iban(iban)
    hits: dict[str, str] = {}

    if call_active:
        hits["llamada_activa"] = "El cliente está en una llamada mientras ordena la transferencia"

    if target not in {normalize_iban(b["iban"]) for b in beneficiaries}:
        hits["beneficiario_nuevo"] = "Es la primera vez que envía dinero a esta cuenta"

    outgoing = [m["amount"] for m in movements if m.get("type") == "transfer_out"]
    if outgoing:
        avg = sum(outgoing) / len(outgoing)
        if amount > UNUSUAL_FACTOR * avg:
            hits["importe_inusual"] = f"{eur(amount)} es más de {UNUSUAL_FACTOR} veces su media ({eur(round(avg, 2))})"

    for m in movements:
        if m.get("type") != "internal_in":
            continue
        age = now - datetime.fromisoformat(m["ts"])
        if timedelta(0) <= age <= RECENT_INTERNAL:
            mins = int(age.total_seconds() // 60)
            hits["traspaso_previo_ahorro"] = f"Hace {mins} min traspasó {eur(m['amount'])} del ahorro a la cuenta corriente"
            break

    if target in {normalize_iban(f) for f in flagged}:
        hits["cuenta_destino_marcada"] = "La cuenta de destino está marcada como sospechosa"

    if recent_alert:
        hits["alerta_estafa_reciente"] = recent_alert

    if iban_pasted:
        hits["iban_pegado"] = "El número de cuenta se pegó en lugar de escribirse"

    signals = [{"id": sid, "weight": w, "detail": hits[sid]} for sid, w in WEIGHTS.items() if sid in hits]
    score = min(100, sum(s["weight"] for s in signals))
    return {"score": score, "signals": signals}
