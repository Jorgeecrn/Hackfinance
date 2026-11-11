import os
import sys
from pathlib import Path

os.environ["FORCE_OFFLINE"] = "1"  # tests deterministas: sin red ni API keys
os.environ["ADMIN_REMOTO"] = "1"  # TestClient no llega desde 127.0.0.1; test_seguridad_gasto.py prueba la protección
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Cada test usa su propio estado y lista de reportes."""
    from app import budget, state, tools

    monkeypatch.setattr(state, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(budget, "GASTO_FILE", tmp_path / "gasto.json")
    monkeypatch.setattr(tools, "REPORTS_FILE", tmp_path / "reports.json")
    yield
