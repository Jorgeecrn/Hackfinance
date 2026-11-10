"""API del Banco Demo con escudo de llamada (/api/llamada/...)."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from . import service

router = APIRouter(prefix="/api/llamada", tags=["escudo de llamada"])


class Context(BaseModel):
    callActive: bool = False
    ibanPasted: bool = False


class TransferIn(BaseModel):
    amount: float = Field(..., gt=0, le=1_000_000)
    iban: str = Field(..., min_length=5, max_length=42)
    beneficiaryName: str = Field(..., min_length=1, max_length=80)
    concept: str = Field("", max_length=140)
    context: Context = Context()


class AmountIn(BaseModel):
    amount: float = Field(..., gt=0, le=1_000_000)


class ReplyIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class DecisionIn(BaseModel):
    decision: Literal["release", "block"]
    actor: Literal["analista", "familia"] = "analista"


class CallIn(BaseModel):
    active: bool


def _call(fn, *args):
    try:
        return fn(*args)
    except service.ServiceError as exc:
        raise HTTPException(exc.status, exc.detail) from exc


async def _acall(fn, *args):
    try:
        return await fn(*args)
    except service.ServiceError as exc:
        raise HTTPException(exc.status, exc.detail) from exc


@router.get("/state")
def state():
    return service.get_state()


@router.post("/internal-transfer")
def internal_transfer(body: AmountIn):
    return _call(service.internal_transfer, body.amount)


@router.post("/transfers")
async def transfers(body: TransferIn):
    return await _acall(service.request_transfer, body.amount, body.iban, body.beneficiaryName.strip(),
                        body.concept.strip(), body.context.callActive, body.context.ibanPasted)


@router.post("/conversations/{conv_id}/messages")
async def conversation_message(conv_id: str, body: ReplyIn):
    return await _acall(service.reply, conv_id, body.text)


@router.get("/cases")
def cases():
    return service.list_cases()


@router.post("/cases/{case_id}/decision")
async def case_decision(case_id: str, body: DecisionIn):
    return _call(service.analyst_decision, case_id, body.decision, body.actor)


@router.post("/demo/call")
def demo_call(body: CallIn):
    return service.set_call(body.active)


@router.post("/demo/reset")
def demo_reset():
    return service.reset()
