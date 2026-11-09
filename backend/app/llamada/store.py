"""Estado en memoria del Banco Demo (independiente del state.json de Centinela)."""
from __future__ import annotations

import copy
import threading
from typing import Callable, TypeVar

from .seed import SEED

T = TypeVar("T")
_lock = threading.RLock()
_state: dict = {}


def reset() -> None:
    global _state
    with _lock:
        _state = copy.deepcopy(SEED)


def snapshot() -> dict:
    with _lock:
        return copy.deepcopy(_state)


def mutate(fn: Callable[[dict], T]) -> T:
    """Aplica `fn(estado)` bajo el lock y devuelve su resultado."""
    with _lock:
        return fn(_state)


reset()
