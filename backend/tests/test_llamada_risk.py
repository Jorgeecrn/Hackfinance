"""Motor de riesgo del escudo de llamada (función pura)."""
import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.llamada import seed
from app.llamada.risk import THRESHOLD, WEIGHTS, evaluate_risk

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def internal_in(minutes_ago: float, amount: float = 8000.0) -> dict:
    return {"type": "internal_in", "amount": amount, "ts": (NOW - timedelta(minutes=minutes_ago)).isoformat()}


def ctx(**over):
    base = dict(
        amount=200.0, iban=seed.JAVIER_IBAN, call_active=False, iban_pasted=False,
        beneficiaries=copy.deepcopy(seed.SEED["beneficiaries"]),
        movements=copy.deepcopy(seed.SEED["movements"]),
        flagged=list(seed.FLAGGED_IBANS), now=NOW,
    )
    base.update(over)
    return evaluate_risk(**base)


def ids(result):
    return [s["id"] for s in result["signals"]]


def test_threshold_is_40():
    assert THRESHOLD == 40


def test_scenario_normal_scores_0():
    r = ctx()
    assert r["score"] == 0 and r["signals"] == []


def test_scenario_casero_scores_55():
    r = ctx(amount=600.0, iban=seed.CASERO_IBAN, call_active=True)
    assert r["score"] == 55
    assert ids(r) == ["llamada_activa", "beneficiario_nuevo"]


def test_scenario_estafa_caps_at_100():
    movements = copy.deepcopy(seed.SEED["movements"]) + [internal_in(5)]
    r = ctx(amount=8500.0, iban=seed.ESTAFA_IBAN, call_active=True, iban_pasted=True, movements=movements)
    assert r["score"] == 100
    assert ids(r) == ["llamada_activa", "beneficiario_nuevo", "importe_inusual", "traspaso_previo_ahorro", "iban_pegado"]


@pytest.mark.parametrize("signal,over", [
    ("llamada_activa", {"call_active": True}),
    ("beneficiario_nuevo", {"iban": seed.CASERO_IBAN}),
    ("importe_inusual", {"amount": 1000.0}),
    ("traspaso_previo_ahorro", {"movements": copy.deepcopy(seed.SEED["movements"]) + [internal_in(10)]}),
    ("iban_pegado", {"iban_pasted": True}),
])
def test_each_signal_weight(signal, over):
    r = ctx(**over)
    assert ids(r) == [signal]
    assert r["score"] == WEIGHTS[signal]


def test_flagged_account_weight():
    r = ctx(iban=seed.FLAGGED_IBANS[0], beneficiaries=[{"name": "x", "iban": seed.FLAGGED_IBANS[0]}])
    assert ids(r) == ["cuenta_destino_marcada"] and r["score"] == 25


def test_weights_match_spec():
    assert WEIGHTS == {"llamada_activa": 35, "beneficiario_nuevo": 20, "importe_inusual": 20,
                       "traspaso_previo_ahorro": 20, "cuenta_destino_marcada": 25,
                       "alerta_estafa_reciente": 25, "iban_pegado": 10}


def test_unusual_amount_is_strict():
    assert "importe_inusual" not in ids(ctx(amount=750.0))
    assert "importe_inusual" in ids(ctx(amount=750.01))


def test_no_outgoing_history_disables_unusual():
    assert "importe_inusual" not in ids(ctx(amount=99999.0, movements=[]))


def test_internal_transfer_older_than_30_min_ignored():
    movements = copy.deepcopy(seed.SEED["movements"]) + [internal_in(31)]
    assert "traspaso_previo_ahorro" not in ids(ctx(movements=movements))


def test_iban_normalized_for_known_and_flagged():
    assert "beneficiario_nuevo" not in ids(ctx(iban="es66 2100 0418 4012 3456 7891"))
    flagged = seed.FLAGGED_IBANS[0]
    messy = " ".join(flagged[i:i + 4] for i in range(0, len(flagged), 4)).lower()
    assert "cuenta_destino_marcada" in ids(ctx(iban=messy))


def test_signals_have_detail_text():
    r = ctx(amount=8500.0, iban=seed.ESTAFA_IBAN, call_active=True)
    assert all(isinstance(s["detail"], str) and s["detail"] for s in r["signals"])
    assert all(s["weight"] == WEIGHTS[s["id"]] for s in r["signals"])


ALERT = "Hace 5 min recibió un mensaje con señales de estafa: falso hijo"


def test_recent_alert_signal_weight_and_detail():
    r = ctx(recent_alert=ALERT)
    assert ids(r) == ["alerta_estafa_reciente"] and r["score"] == 25
    assert r["signals"][0]["detail"] == ALERT


def test_alert_plus_new_beneficiary_is_45():
    assert ctx(amount=600.0, iban=seed.CASERO_IBAN, recent_alert=ALERT)["score"] == 45


def test_alert_plus_call_plus_new_is_80():
    assert ctx(amount=600.0, iban=seed.CASERO_IBAN, call_active=True, recent_alert=ALERT)["score"] == 80


def test_lucia_is_known_beneficiary():
    assert "beneficiario_nuevo" not in ids(ctx(iban=seed.LUCIA_IBAN))
