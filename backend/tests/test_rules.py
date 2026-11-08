import json
from pathlib import Path

from app.rules import analyze_rules, explain_rules

CONTACTS = [{"nombre": "Lucía", "relacion": "hija", "telefono": "+34600111222"},
            {"nombre": "Javier", "relacion": "hijo", "telefono": "+34600333444"},
            {"nombre": "Centro de salud", "relacion": "médico", "telefono": "+34915555555"}]


def test_hijo_en_apuros_is_red():
    r = analyze_rules("Hola mamá, este es mi número nuevo. Hazme un bizum de 500€ urgente, no se lo digas a papá", "+34711234567", CONTACTS)
    assert r.level == "rojo"
    ids = {s.id for s in r.signals}
    assert {"familiar_numero_nuevo", "pide_dinero", "familiar_desconocido"} <= ids


def test_fake_bank_link_is_red():
    r = analyze_rules("MyInvestor: su cuenta ha sido bloqueada. Verifique sus datos en https://myinvestor-seguridad.com", "MyInvestor", CONTACTS)
    assert r.level == "rojo"


def test_real_otp_is_green():
    r = analyze_rules("Tu código de verificación de MyInvestor es 482913. No compartas este código con nadie.", "MyInvestor", CONTACTS)
    assert r.level == "verde"


def test_known_family_contact_is_green():
    r = analyze_rules("Mamá, hazme un Bizum de 25€ de la cena cuando puedas. Un beso", "+34600333444", CONTACTS)
    assert r.level == "verde"


def test_explanation_has_required_fields():
    r = analyze_rules("Correos: paquete retenido, pague 1,99€ en correos-envio.xyz", None, CONTACTS)
    v = explain_rules(r)
    for key in ("nivel", "titulo", "explicacion", "pruebas", "consejo", "mensaje_voz", "acciones"):
        assert key in v
    assert v["nivel"] in ("rojo", "amarillo")


def test_demo_samples_are_classified_as_labeled():
    samples = json.loads((Path(__file__).resolve().parents[1] / "data" / "demo_messages.json").read_text(encoding="utf-8"))
    for s in samples:
        r = analyze_rules(s["texto"], s["remitente"], CONTACTS)
        flagged = r.level != "verde"
        assert flagged == (s["tipo"] == "estafa"), (s["titulo"], r.level, [x.id for x in r.signals])
