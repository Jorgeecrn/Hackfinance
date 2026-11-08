"""Banco simulado con «Escudo bancario».

Cuando Centinela detecta una estafa grave, el escudo frena durante un tiempo las
transferencias y Bizum a beneficiarios NUEVOS por encima de un umbral. La operación
queda retenida hasta que el familiar de confianza (o el propio cliente, pasado el
plazo) la aprueba. En producción esto sería una integración con la API del banco.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import state as st
from .config import settings
from .events import bus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def shield_active(bank: dict) -> bool:
    until = bank["escudo"].get("activo_hasta")
    return bool(until) and datetime.fromisoformat(until) > _now()


def activate_shield(reason: str, alert_id: str | None = None, minutes: int | None = None) -> dict:
    minutes = minutes or settings.shield_minutes

    def _do(s):
        until = (_now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
        s["banco"]["escudo"] = {"activo_hasta": until, "motivo": reason, "alerta_id": alert_id}
        return s["banco"]["escudo"]

    escudo = st.update(_do)
    bus.publish_many(["banco", "familia", "usuario"], "escudo", {"activo": True, **escudo})
    return escudo


def deactivate_shield() -> dict:
    def _do(s):
        s["banco"]["escudo"] = {"activo_hasta": None, "motivo": None, "alerta_id": None}
        return s["banco"]["escudo"]

    escudo = st.update(_do)
    bus.publish_many(["banco", "familia", "usuario"], "escudo", {"activo": False, **escudo})
    return escudo


def get_bank() -> dict:
    bank = st.load()["banco"]
    bank["escudo"]["activo"] = shield_active(bank)
    bank["umbral_escudo"] = settings.shield_amount_threshold
    return bank


def _norm_iban(iban: str) -> str:
    return iban.replace(" ", "").upper()


def request_transfer(beneficiario: str, iban: str, importe: float, concepto: str = "", canal: str = "transferencia") -> dict:
    def _do(s):
        bank = s["banco"]
        known = any(_norm_iban(b["iban"]) == _norm_iban(iban) for b in bank["beneficiarios_conocidos"])
        tx = {
            "id": st.new_id("tx"),
            "fecha": st.now_iso(),
            "beneficiario": beneficiario,
            "iban": _norm_iban(iban),
            "importe": round(float(importe), 2),
            "concepto": concepto,
            "canal": canal,
            "beneficiario_conocido": known,
        }
        if importe > bank["saldo"]:
            tx.update(estado="rechazada", motivo="Saldo insuficiente")
        elif shield_active(bank) and not known and importe >= settings.shield_amount_threshold:
            tx.update(
                estado="retenida",
                motivo=(
                    "Escudo bancario activo: hace poco recibiste un mensaje con señales de estafa. "
                    "Esta operación a un beneficiario nuevo queda retenida hasta que tu familiar de confianza la revise."
                ),
            )
        else:
            tx.update(estado="completada", motivo="")
            bank["saldo"] = round(bank["saldo"] - tx["importe"], 2)
        bank["transferencias"].insert(0, tx)
        return tx

    tx = st.update(_do)
    event = "transferencia_retenida" if tx["estado"] == "retenida" else "transferencia"
    bus.publish_many(["banco", "familia", "usuario"], event, tx)
    return tx


def resolve_transfer(tx_id: str, approve: bool) -> dict | None:
    def _do(s):
        bank = s["banco"]
        for tx in bank["transferencias"]:
            if tx["id"] == tx_id and tx["estado"] == "retenida":
                if approve:
                    if tx["importe"] > bank["saldo"]:
                        tx.update(estado="rechazada", motivo="Saldo insuficiente")
                    else:
                        tx.update(estado="completada", motivo="Aprobada por el familiar de confianza")
                        bank["saldo"] = round(bank["saldo"] - tx["importe"], 2)
                else:
                    tx.update(estado="cancelada", motivo="Cancelada: posible estafa. El dinero no ha salido de la cuenta.")
                return tx
        return None

    tx = st.update(_do)
    if tx:
        bus.publish_many(["banco", "familia", "usuario"], "transferencia", tx)
    return tx
