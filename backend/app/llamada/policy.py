"""Política de decisión determinista: el LLM evalúa, esta función decide.

Combina las señales del motor de riesgo con la evaluación del agente y devuelve
la acción final con la regla aplicada y sus motivos (explicable y auditable).
"""
from __future__ import annotations

HARD_FLAGS = {"suplantacion_banco", "cuenta_segura"}

CLOSING_TEXTS: dict[str, str] = {
    "execute": "Listo. Tu transferencia se ha enviado.",
    "hold": "Hemos retenido esta transferencia para protegerte. Cuelga y llámanos al número de tu tarjeta.",
    "review": "Un empleado del banco va a revisar esta transferencia. Tu dinero no se ha movido.",
}


MANDATORY_REVIEW_TEXT = "Tu dinero sigue en tu cuenta. La transferencia queda en revisión."


def mandatory_review_rule(signal_ids: list[str]) -> str | None:
    if "cuenta_destino_marcada" in signal_ids:
        return "R6_cuenta_marcada"
    if {"alerta_estafa_reciente", "beneficiario_nuevo"} <= set(signal_ids):
        return "R7_escudo_destino_nuevo"
    return None


def hard_rule_applies(signal_ids: list[str], assessment: dict | None) -> bool:
    if not assessment or "llamada_activa" not in signal_ids:
        return False
    return bool(HARD_FLAGS & set(assessment.get("redFlags", [])))


def _reasons(signal_ids: list[str], assessment: dict | None) -> list[str]:
    reasons = [f"señales: {', '.join(signal_ids) or 'ninguna'}"]
    if assessment:
        reasons.append(f"riesgo del agente: {assessment['risk']}")
        reasons.append(f"tipología: {assessment['typology']}")
        reasons.append(f"alertas: {', '.join(assessment.get('redFlags', [])) or 'ninguna'}")
    return reasons


def decide(signal_ids: list[str], assessment: dict | None, ready: bool) -> dict:
    reasons = _reasons(signal_ids, assessment)
    risk = assessment.get("risk") if assessment else None

    review_rule = mandatory_review_rule(signal_ids)
    if review_rule:
        return {"action": "review", "rule": review_rule, "reasons": reasons}
    if hard_rule_applies(signal_ids, assessment):
        action, rule = "hold", "R1_suplantacion"
    elif risk == "high":
        action, rule = "hold", "R2_riesgo_alto"
    elif risk == "medium":
        action, rule = "review", "R3_riesgo_medio"
    elif risk == "low" and ready:
        action, rule = "execute", "R4_riesgo_bajo"
    else:
        action, rule = "review", "R5_sin_decision"
        reasons.append("agente no disponible" if assessment is None else "límite de turnos sin decisión")
    return {"action": action, "rule": rule, "reasons": reasons}
