"""Herramientas de investigación que usa el agente (y el motor de reglas).

Todas son deterministas y rápidas. Las que consultan internet (RDAP, Safe Browsing)
tienen timeout corto y degradan con elegancia si no hay red.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlparse

import httpx

from .config import DATA_DIR, settings
from .entities import IBAN_LENGTHS, normalize

SHORTENERS = {
    "bit.ly", "tinyurl.com", "cutt.ly", "t.ly", "is.gd", "ow.ly", "rebrand.ly", "shorturl.at",
    "t.co", "goo.gl", "rb.gy", "s.id", "tiny.cc", "bl.ink", "short.io", "acortar.link", "v.gd",
}
SUSPICIOUS_TLDS = {
    "xyz", "top", "icu", "click", "live", "shop", "online", "site", "vip", "cc", "buzz", "link",
    "club", "store", "website", "tk", "ml", "ga", "cf", "gq", "monster", "rest", "cam", "sbs",
    "cfd", "bond", "lat", "ws", "fun", "work", "help", "support", "info",
}
SECOND_LEVEL = {"com.es", "org.es", "gob.es", "nom.es", "edu.es", "co.uk", "org.uk", "com.mx", "com.ar", "com.br"}
LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

COUNTRY_PREFIXES = {
    "+34": "España", "+44": "Reino Unido", "+33": "Francia", "+351": "Portugal", "+49": "Alemania",
    "+39": "Italia", "+1": "EE. UU./Canadá", "+212": "Marruecos", "+213": "Argelia", "+234": "Nigeria",
    "+225": "Costa de Marfil", "+221": "Senegal", "+237": "Camerún", "+371": "Letonia", "+370": "Lituania",
    "+372": "Estonia", "+40": "Rumanía", "+48": "Polonia", "+7": "Rusia", "+380": "Ucrania",
    "+86": "China", "+91": "India", "+92": "Pakistán", "+880": "Bangladés", "+63": "Filipinas",
    "+52": "México", "+54": "Argentina", "+57": "Colombia", "+51": "Perú", "+58": "Venezuela",
    "+593": "Ecuador", "+56": "Chile", "+55": "Brasil", "+31": "Países Bajos", "+32": "Bélgica",
    "+41": "Suiza", "+352": "Luxemburgo", "+353": "Irlanda", "+356": "Malta", "+357": "Chipre",
    "+90": "Turquía", "+971": "Emiratos Árabes", "+44 7": "Reino Unido (móvil)",
}
IBAN_COUNTRIES = {
    "ES": "España", "PT": "Portugal", "FR": "Francia", "DE": "Alemania", "IT": "Italia", "GB": "Reino Unido",
    "IE": "Irlanda", "NL": "Países Bajos", "BE": "Bélgica", "LT": "Lituania", "LV": "Letonia", "EE": "Estonia",
    "PL": "Polonia", "RO": "Rumanía", "BG": "Bulgaria", "CY": "Chipre", "MT": "Malta", "LU": "Luxemburgo",
    "CH": "Suiza", "AT": "Austria", "HR": "Croacia", "GR": "Grecia", "TR": "Turquía", "AE": "Emiratos Árabes",
    "MA": "Marruecos", "UA": "Ucrania", "DK": "Dinamarca", "SE": "Suecia", "FI": "Finlandia", "CZ": "Chequia",
}


# ---------------------------------------------------------------- datos de referencia
@lru_cache(maxsize=1)
def official_entities() -> list[dict]:
    return json.loads((DATA_DIR / "official_domains.json").read_text(encoding="utf-8"))["entidades"]


@lru_cache(maxsize=1)
def known_campaigns() -> list[dict]:
    return json.loads((DATA_DIR / "known_campaigns.json").read_text(encoding="utf-8"))["campanas"]


@lru_cache(maxsize=1)
def spanish_banks() -> dict[str, str]:
    return json.loads((DATA_DIR / "spanish_banks.json").read_text(encoding="utf-8"))["entidades"]


# Lista de números/enlaces reportados por la comunidad (en memoria + fichero)
REPORTS_FILE = DATA_DIR / "reports.json"


def _load_reports() -> dict:
    if REPORTS_FILE.exists():
        try:
            return json.loads(REPORTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"telefonos": {}, "dominios": {}}


def add_report(phones: list[str], domains: list[str]) -> dict:
    data = _load_reports()
    for p in phones:
        key = normalize_phone(p)
        data["telefonos"][key] = data["telefonos"].get(key, 0) + 1
    for d in domains:
        data["dominios"][d] = data["dominios"].get(d, 0) + 1
    REPORTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


# ---------------------------------------------------------------- utilidades
def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def host_of(url: str) -> str:
    if not re.match(r"^[a-z]+://", url, re.IGNORECASE):
        url = "http://" + url
    host = (urlparse(url).hostname or "").lower().strip(".")
    return host


def registrable_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+") and len(digits) == 9:
        digits = "+34" + digits
    return digits


# ---------------------------------------------------------------- herramienta: enlaces
_rdap_cache: dict[str, tuple[float, dict]] = {}


def domain_age_days(domain: str) -> dict:
    """Consulta RDAP (registro público de dominios) para saber cuándo se creó."""
    if not settings.online_checks or settings.force_offline:
        return {"disponible": False, "motivo": "consultas online desactivadas"}
    if domain in _rdap_cache and time.time() - _rdap_cache[domain][0] < 3600:
        return _rdap_cache[domain][1]
    result: dict = {"disponible": False}
    try:
        r = httpx.get(f"https://rdap.org/domain/{domain}", timeout=3.0, follow_redirects=True)
        if r.status_code == 200:
            for ev in r.json().get("events", []):
                if ev.get("eventAction") == "registration":
                    created = datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00"))
                    days = (datetime.now(timezone.utc) - created).days
                    result = {"disponible": True, "creado": created.date().isoformat(), "dias": days}
                    break
        elif r.status_code == 404:
            result = {"disponible": True, "no_registrado": True}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        result = {"disponible": False, "motivo": f"sin respuesta ({type(exc).__name__})"}
    _rdap_cache[domain] = (time.time(), result)
    return result


def safe_browsing(url: str) -> dict:
    if not settings.google_safe_browsing_key or settings.force_offline:
        return {"disponible": False}
    body = {
        "client": {"clientId": "centinela", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    try:
        r = httpx.post(
            "https://safebrowsing.googleapis.com/v4/threatMatches:find",
            params={"key": settings.google_safe_browsing_key}, json=body, timeout=3.0,
        )
        if r.status_code == 200:
            return {"disponible": True, "peligroso": bool(r.json().get("matches"))}
    except httpx.HTTPError:
        pass
    return {"disponible": False}


def analyze_url(url: str) -> dict:
    """Investiga un enlace: imitación de marcas, acortadores, TLD sospechosos, antigüedad."""
    host = host_of(url)
    domain = registrable_domain(host)
    findings: list[str] = []
    risk = 0
    imitates = None
    official = None

    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        findings.append("El enlace usa una dirección IP en lugar de un nombre: típico de webs fraudulentas.")
        risk += 35
    if host.startswith("xn--") or ".xn--" in host:
        findings.append("El dominio usa caracteres especiales (punycode) que pueden imitar letras normales.")
        risk += 30
    if domain in SHORTENERS:
        findings.append(f"Es un acortador de enlaces ({domain}): oculta la web real de destino.")
        risk += 25
    tld = domain.rsplit(".", 1)[-1]
    if tld in SUSPICIOUS_TLDS:
        findings.append(f"Termina en «.{tld}», una extensión muy usada en campañas de fraude.")
        risk += 15

    # ¿Es un dominio oficial o una imitación?
    label = normalize(domain.split(".")[0]).translate(LEET)
    host_flat = normalize(host).translate(LEET).replace("-", "").replace(".", "")
    for ent in official_entities():
        if any(domain == d or host.endswith("." + d) for d in ent["dominios"]):
            official = ent["nombre"]
            break
    if official:
        findings.append(f"Es un dominio oficial de {official}.")
        risk = max(0, risk - 40)
    else:
        for ent in official_entities():
            for brand in ent["marcas"]:
                if len(brand) < 4:
                    # marcas cortas (dgt, gls...) solo si aparecen como palabra separada
                    if re.search(rf"(^|[.-]){re.escape(brand)}([.-]|$)", host):
                        imitates = ent["nombre"]
                elif brand in host_flat:
                    imitates = ent["nombre"]
                else:
                    # Compara cada trozo del nombre (incluidos subdominios: «mylnvestor.es-validar.com»)
                    off_labels = [normalize(d.split(".")[0]) for d in ent["dominios"]]
                    host_labels = {label} | {normalize(p).translate(LEET) for p in re.split(r"[.-]", host) if len(p) >= 4}
                    if any(0 < levenshtein(hl, ol) <= (1 if len(ol) <= 6 else 2) for hl in host_labels for ol in off_labels):
                        imitates = ent["nombre"]
                if imitates:
                    break
            if imitates:
                off = ", ".join(next(e["dominios"] for e in official_entities() if e["nombre"] == imitates))
                findings.append(f"Imita a {imitates}, pero NO es su web oficial (la oficial es {off}).")
                risk += 50
                break

    reports = _load_reports()["dominios"].get(domain, 0)
    if reports:
        findings.append(f"Otros usuarios han reportado este dominio {reports} vez/veces.")
        risk += min(40, 20 * reports)

    age = domain_age_days(domain) if domain not in SHORTENERS and not official else {"disponible": False}
    if age.get("disponible"):
        if age.get("no_registrado"):
            findings.append("El dominio ni siquiera está registrado.")
            risk += 20
        elif age.get("dias") is not None:
            if age["dias"] < 30:
                findings.append(f"El dominio se creó hace solo {age['dias']} días ({age['creado']}).")
                risk += 35
            elif age["dias"] < 180:
                findings.append(f"El dominio es reciente: creado el {age['creado']}.")
                risk += 15

    sb = safe_browsing(url)
    if sb.get("disponible") and sb.get("peligroso"):
        findings.append("Google Safe Browsing lo tiene marcado como peligroso.")
        risk += 60

    return {
        "url": url,
        "dominio": domain,
        "oficial_de": official,
        "imita_a": imitates,
        "antiguedad": age,
        "hallazgos": findings,
        "riesgo": min(100, risk),
    }


# ---------------------------------------------------------------- herramienta: teléfonos
def analyze_phone(phone: str, contacts: list[dict] | None = None) -> dict:
    norm = normalize_phone(phone)
    findings: list[str] = []
    risk = 0
    country = None
    for prefix in sorted(COUNTRY_PREFIXES, key=len, reverse=True):
        if " " in prefix:
            continue
        if norm.startswith(prefix):
            country = COUNTRY_PREFIXES[prefix]
            break
    if country and country != "España":
        findings.append(f"Es un número extranjero ({country}).")
        risk += 25
    local = norm[3:] if norm.startswith("+34") else ""
    if local[:3] in {"803", "806", "807", "905"}:
        findings.append("Es un número de tarificación especial (muy caro de llamar).")
        risk += 40

    contact = None
    for c in contacts or []:
        if normalize_phone(c.get("telefono", "")) == norm:
            contact = c
            break
    if contact:
        findings.append(f"Está en tus contactos de confianza como «{contact.get('nombre')}».")
        risk = max(0, risk - 30)
    else:
        findings.append("No está en tus contactos de confianza.")

    reports = _load_reports()["telefonos"].get(norm, 0)
    if reports:
        findings.append(f"Otros usuarios lo han reportado {reports} vez/veces como fraude.")
        risk += min(50, 25 * reports)

    return {"telefono": norm, "pais": country, "contacto": contact, "hallazgos": findings, "riesgo": min(100, risk)}


# ---------------------------------------------------------------- herramienta: IBAN
def _iban_valid(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", iban):
        return False
    expected = IBAN_LENGTHS.get(iban[:2])
    if expected and len(iban) != expected:
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def analyze_iban(iban: str, claimed_entity: str | None = None) -> dict:
    iban = iban.replace(" ", "").upper()
    findings: list[str] = []
    risk = 0
    valid = _iban_valid(iban)
    country_code = iban[:2]
    country = IBAN_COUNTRIES.get(country_code, country_code)
    bank = None
    if not valid:
        findings.append("El IBAN no es válido (el dígito de control no cuadra).")
        risk += 20
    if country_code == "ES" and len(iban) >= 8:
        code = iban[4:8]
        bank = spanish_banks().get(code, f"entidad española con código {code}")
        findings.append(f"Es una cuenta de {bank}.")
    elif country_code != "ES":
        findings.append(f"Es una cuenta de otro país: {country}. El dinero saldría de España.")
        risk += 35
    if claimed_entity and bank and normalize(claimed_entity) not in normalize(bank):
        findings.append(f"El mensaje dice ser de {claimed_entity}, pero la cuenta es de {bank}.")
        risk += 30
    return {"iban": iban, "valido": valid, "pais": country, "entidad": bank, "hallazgos": findings, "riesgo": min(100, risk)}


# ---------------------------------------------------------------- herramienta: campañas
def search_campaigns(text: str, top_k: int = 2) -> list[dict]:
    norm = normalize(text)
    results = []
    for camp in known_campaigns():
        hits = [w for w in camp["palabras"] if w in norm]
        if not hits:
            continue
        score = len(hits) / max(4, min(len(camp["palabras"]), 8))
        results.append({
            "id": camp["id"], "nombre": camp["nombre"], "titulo": camp.get("titulo", camp["nombre"]), "coincidencias": hits,
            "similitud": round(min(1.0, score), 2), "consejo": camp["consejo"],
        })
    results.sort(key=lambda r: r["similitud"], reverse=True)
    return [r for r in results[:top_k] if r["similitud"] >= 0.25]


# ---------------------------------------------------------------- herramienta: contactos
def lookup_contact(query: str, contacts: list[dict] | None) -> dict:
    q = normalize(query)
    matches = [
        c for c in contacts or []
        if q and (q in normalize(c.get("nombre", "")) or q in normalize(c.get("relacion", ""))
                  or normalize_phone(query) == normalize_phone(c.get("telefono", "")))
    ]
    return {"consulta": query, "encontrados": matches}
