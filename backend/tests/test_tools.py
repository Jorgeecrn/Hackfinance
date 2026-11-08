from app import tools


def test_lookalike_domain_detected():
    r = tools.analyze_url("https://myinvestor-seguridad.com/login")
    assert r["imita_a"] == "MyInvestor"
    assert r["riesgo"] >= 50


def test_leet_lookalike_detected():
    r = tools.analyze_url("http://bbva-cIientes.top")
    assert r["imita_a"] == "BBVA"


def test_official_domain_is_trusted():
    r = tools.analyze_url("https://www.myinvestor.es/ayuda")
    assert r["oficial_de"] == "MyInvestor"
    assert r["imita_a"] is None
    assert r["riesgo"] == 0


def test_shortener_flagged():
    r = tools.analyze_url("bit.ly/3xYz")
    assert any("acortador" in h for h in r["hallazgos"])


def test_iban_validation_and_country():
    ok = tools.analyze_iban("ES91 2100 0418 4502 0005 1332")
    assert ok["valido"] and ok["pais"] == "España" and ok["entidad"] == "CaixaBank"
    foreign = tools.analyze_iban("LT601010012345678901")
    assert foreign["pais"] == "Lituania" and foreign["riesgo"] >= 35


def test_iban_mismatch_with_claimed_entity():
    r = tools.analyze_iban("ES9121000418450200051332", "MyInvestor")
    assert any("dice ser de MyInvestor" in h for h in r["hallazgos"])


def test_phone_contact_and_foreign():
    contacts = [{"nombre": "Lucía", "telefono": "+34 600 111 222"}]
    assert tools.analyze_phone("600111222", contacts)["contacto"]["nombre"] == "Lucía"
    foreign = tools.analyze_phone("+371 2012 3456", contacts)
    assert foreign["pais"] == "Letonia" and foreign["contacto"] is None


def test_reports_raise_risk():
    before = tools.analyze_phone("+34711234567")["riesgo"]
    tools.add_report(["+34711234567"], [])
    after = tools.analyze_phone("+34711234567")["riesgo"]
    assert after > before


def test_campaign_search():
    res = tools.search_campaigns("Hola mamá, se me ha roto el móvil, este es mi número nuevo, necesito un bizum urgente")
    assert res and res[0]["id"] == "hijo_en_apuros"
