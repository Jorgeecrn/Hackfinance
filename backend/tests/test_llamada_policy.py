"""Política de decisión determinista del escudo de llamada."""
from app.llamada.policy import CLOSING_TEXTS, decide, hard_rule_applies


def A(risk="low", flags=(), typology="ninguna"):
    return {"message": "x", "typology": typology, "risk": risk, "redFlags": list(flags), "readyToDecide": True}


def test_hard_rule_beats_low_risk():
    d = decide(["llamada_activa"], A("low", ["cuenta_segura"]), ready=True)
    assert d["action"] == "hold" and d["rule"] == "R1_suplantacion"


def test_hard_rule_needs_call():
    assert not hard_rule_applies(["beneficiario_nuevo"], A("low", ["suplantacion_banco"]))
    d = decide(["beneficiario_nuevo"], A("low", ["suplantacion_banco"]), ready=True)
    assert d["action"] == "execute" and d["rule"] == "R4_riesgo_bajo"


def test_hard_rule_without_assessment_is_false():
    assert not hard_rule_applies(["llamada_activa"], None)


def test_high_holds_even_if_not_ready():
    d = decide(["llamada_activa"], A("high"), ready=False)
    assert d["action"] == "hold" and d["rule"] == "R2_riesgo_alto"


def test_medium_reviews():
    d = decide(["llamada_activa"], A("medium"), ready=True)
    assert d["action"] == "review" and d["rule"] == "R3_riesgo_medio"


def test_low_ready_executes():
    d = decide(["llamada_activa"], A("low"), ready=True)
    assert d["action"] == "execute" and d["rule"] == "R4_riesgo_bajo"


def test_low_not_ready_reviews():
    d = decide(["llamada_activa"], A("low"), ready=False)
    assert d["action"] == "review" and d["rule"] == "R5_sin_decision"
    assert "límite de turnos sin decisión" in d["reasons"]


def test_agent_failure_reviews():
    d = decide(["llamada_activa", "beneficiario_nuevo"], None, ready=False)
    assert d["action"] == "review" and d["rule"] == "R5_sin_decision"
    assert "agente no disponible" in d["reasons"]


def test_reasons_include_signals_and_assessment():
    d = decide(["llamada_activa"], A("high", ["urgencia"], "falso_empleado_banco"), ready=True)
    text = " ".join(d["reasons"])
    assert "llamada_activa" in text and "high" in text and "falso_empleado_banco" in text and "urgencia" in text


def test_closing_hold_text_is_literal():
    assert CLOSING_TEXTS["hold"] == "Hemos retenido esta transferencia para protegerte. Cuelga y llámanos al número de tu tarjeta."
    assert set(CLOSING_TEXTS) == {"execute", "hold", "review"}
