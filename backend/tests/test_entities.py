from app.entities import extract_entities


def test_urls_without_scheme_and_with_scheme():
    e = extract_entities("Pague en correos-envio.xyz/pago o en https://bit.ly/abc. Gracias.")
    assert "correos-envio.xyz/pago" in e.urls
    assert "https://bit.ly/abc" in e.urls


def test_no_false_urls_from_abbreviations_or_numbers():
    e = extract_entities("Sr.García, son 1.500 € p.ej. mañana")
    assert e.urls == []
    assert e.amounts == [1500.0]


def test_phones_spanish_and_international():
    e = extract_entities("Llama al 612 345 678 o al +44 7700 900123")
    assert "612345678" in e.phones
    assert "+447700900123" in e.phones


def test_iban_is_not_overcaptured():
    e = extract_entities("Transfiera a LT12 1000 0111 0100 1000 para liberar su premio")
    assert e.ibans == ["LT121000011101001000"]


def test_emails_are_not_urls():
    e = extract_entities("Escribe a soporte@myinvestor.es")
    assert e.emails == ["soporte@myinvestor.es"]
    assert e.urls == []
