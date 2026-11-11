from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))


def test_health_offline():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ia"] is False


def test_profile_roundtrip():
    r = client.put("/api/perfil", json={"nombre": "Pepa", "proteccion_activa": False})
    assert r.json()["nombre"] == "Pepa" and r.json()["proteccion_activa"] is False
    assert client.get("/api/perfil").json()["nombre"] == "Pepa"


def test_analyze_scam_creates_alert_and_shield():
    r = client.post("/api/analizar", data={
        "texto": "Hola mamá, se me ha roto el móvil, este es mi número nuevo. Necesito un bizum de 600€ urgente",
        "remitente": "+34711234567",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["veredicto"]["nivel"] == "rojo"
    assert body["escudo_activado"] is True
    assert client.get("/api/alertas").json()[0]["id"] == body["alerta_id"]
    assert client.get("/api/banco").json()["escudo"]["activo"] is True


def test_analyze_legit_no_alert():
    r = client.post("/api/analizar", data={"texto": "Hola mamá, ¿comemos el domingo?", "remitente": "+34600111222"})
    assert r.json()["veredicto"]["nivel"] == "verde"
    assert client.get("/api/alertas").json() == []


def test_empty_analysis_rejected():
    assert client.post("/api/analizar", data={"texto": ""}).status_code == 422


def test_image_without_ai_gives_clear_error():
    r = client.post("/api/analizar", files={"archivo": ("c.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 422 and "IA" in r.json()["error"]


def test_stream_endpoint_emits_result():
    with client.stream("POST", "/api/analizar/stream", data={"texto": "DGT: multa pendiente, pague hoy en dgt-multas.info"}) as r:
        text = "".join(r.iter_text())
    assert "event: paso" in text and "event: resultado" in text


def test_bank_shield_holds_new_beneficiary_and_family_cancels():
    client.post("/api/banco/escudo/activar")
    tx = client.post("/api/banco/transferencia", json={"beneficiario": "Desconocido", "iban": "ES7921000813610123456789", "importe": 680}).json()
    assert tx["estado"] == "retenida"
    saldo = client.get("/api/banco").json()["saldo"]
    cancelled = client.post(f"/api/banco/transferencias/{tx['id']}/cancelar").json()
    assert cancelled["estado"] == "cancelada"
    assert client.get("/api/banco").json()["saldo"] == saldo


def test_bank_known_beneficiary_passes_with_shield():
    client.post("/api/banco/escudo/activar")
    tx = client.post("/api/banco/transferencia", json={"beneficiario": "Lucía", "iban": "ES91 2100 0418 4502 0005 1332", "importe": 500}).json()
    assert tx["estado"] == "completada"


def test_demo_incoming_and_inbox():
    m = client.post("/api/demo/entrante", json={"canal": "sms", "remitente": "DGT", "texto": "Multa pendiente"}).json()
    assert client.get("/api/mensajes").json()[0]["id"] == m["id"]


def test_share_target_flow():
    r = client.post("/share-target", data={"text": "Hola mamá, número nuevo"}, follow_redirects=False)
    assert r.status_code == 303
    share_id = r.headers["location"].split("compartido=")[1]
    data = client.get(f"/api/compartido/{share_id}").json()
    assert "número nuevo" in data["texto"]


def test_tts_without_elevenlabs_returns_204():
    assert client.post("/api/voz", json={"texto": "hola"}).status_code == 204


def test_report_endpoint():
    r = client.post("/api/reportar", json={"telefonos": ["+34711234567"], "enlaces": ["https://estafa.xyz/a"]})
    assert r.json()["ok"] is True


def test_texto_con_captura_sin_ia_identifica_cobertura_parcial():
    response = client.post("/api/analizar", data={"texto": "Hola, foto adjunta."},
                           files={"archivo": ("c.png", b"PNG sintetico", "image/png")})
    assert response.status_code == 200
    result = response.json()
    assert result["origen"] == "captura" and result["fuente"] == "reglas"
    assert "captura queda sin revisar" in result["limitacion"]
    assert result["limitacion"] in result["veredicto"]["mensaje_voz"]
    assert client.get("/api/alertas").json() == []
