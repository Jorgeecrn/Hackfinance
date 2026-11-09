"""Escudo de llamada (Banco Demo): estado, API y escenarios de la demo."""
from app.llamada import store


def test_store_reset_restores_seed():
    store.mutate(lambda s: s["accounts"]["corriente"].update(balance=1))
    store.reset()
    snap = store.snapshot()
    assert snap["accounts"]["corriente"]["balance"] == 2300.0
    snap["accounts"]["corriente"]["balance"] = 5
    assert store.snapshot()["accounts"]["corriente"]["balance"] == 2300.0
