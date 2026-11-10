"""Comprobaciones del frontend que se pueden hacer sin navegador (páginas servidas y service worker)."""
import re

from fastapi.testclient import TestClient

from app.config import FRONTEND_DIR
from app.main import app

client = TestClient(app)


def _shell_paths() -> list[str]:
    sw = (FRONTEND_DIR / "sw.js").read_text(encoding="utf-8")
    block = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
    return re.findall(r'"([^"]+)"', block)


def test_sw_shell_files_exist():
    sw = (FRONTEND_DIR / "sw.js").read_text(encoding="utf-8")
    assert "centinela-v3" in sw
    for path in _shell_paths():
        rel = "index.html" if path == "/" else path.lstrip("/")
        assert (FRONTEND_DIR / rel).is_file(), f"sw.js cachea un archivo que no existe: {path}"


def test_index_is_bank_app():
    html = client.get("/").text
    assert "Banco Demo" in html and "js/banco/app.js" in html
    assert 'js/app.js"' not in html


def test_removed_pages_gone():
    assert client.get("/banco.html").status_code == 404


def test_llamada_redirects_to_app():
    html = client.get("/llamada/").text
    assert 'location.replace("/")' in html
    assert '<meta http-equiv="refresh" content="0; url=/">' in html


def test_presenter_links_app_root():
    html = client.get("/llamada/presentador.html").text
    assert 'href="/"' in html
    assert 'href="/llamada/"' not in html


def test_app_has_protection_copy():
    html = client.get("/").text
    assert "con tecnología Centinela" in html
    assert "requiere permiso de notificaciones (Android)" in html


def test_share_target_redirects_to_app():
    r = client.post("/share-target", data={"text": "hola"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/?compartido=")
