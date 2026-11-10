"""Datos ficticios del Banco Demo: la clienta Carmen López y los escenarios de la demo.

Banco y personas inventados; ningún dato corresponde a una entidad real.
"""
from __future__ import annotations

JAVIER_IBAN = "ES6621000418401234567891"
CASERO_IBAN = "ES6201822370420201504358"
ESTAFA_IBAN = "ES4920383000001000123456"
LUCIA_IBAN = "ES9121000418450200051332"

# Cuentas que el banco ya tiene marcadas como sospechosas (mulas).
FLAGGED_IBANS = ["ES9814650100941900123456"]


def _out(amount: float, ts: str) -> dict:
    return {"type": "transfer_out", "amount": amount, "ts": ts, "name": "Javier López", "iban": JAVIER_IBAN,
            "concept": "Ayuda mensual"}


SEED: dict = {
    "client": {"name": "Carmen López", "bank": "Banco Demo"},
    "accounts": {
        "corriente": {"iban": "ES6000491500051234567892", "balance": 2300.0},
        "ahorro": {"balance": 14000.0},
    },
    "beneficiaries": [{"name": "Javier López", "iban": JAVIER_IBAN}, {"name": "Lucía López", "iban": LUCIA_IBAN}],
    # Historial: media de salidas = 250 €
    "movements": [
        _out(350.0, "2026-10-28T10:00:00+00:00"),
        _out(200.0, "2026-10-01T10:00:00+00:00"),
        _out(350.0, "2026-09-15T10:00:00+00:00"),
        _out(200.0, "2026-09-01T10:00:00+00:00"),
        _out(200.0, "2026-08-01T10:00:00+00:00"),
        _out(200.0, "2026-07-01T10:00:00+00:00"),
    ],
    "transfers": [],
    "cases": [],
    "callActive": False,
}

PRESETS: dict = {
    "normal": {"beneficiaryName": "Javier López", "iban": JAVIER_IBAN, "amount": 200.0,
               "concept": "Ayuda mensual", "ibanPasted": False},
    "casero": {"beneficiaryName": "Antonio Ruiz", "iban": CASERO_IBAN, "amount": 600.0,
               "concept": "Alquiler noviembre", "ibanPasted": False},
    # Requiere un traspaso previo de 8.000 € del ahorro a la corriente.
    "estafa": {"beneficiaryName": "Cuenta segura Banco Demo", "iban": ESTAFA_IBAN, "amount": 8500.0,
               "concept": "Protección de fondos", "ibanPasted": True},
}
