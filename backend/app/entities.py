"""Extracción de entidades de un mensaje: enlaces, teléfonos, IBAN, importes, emails."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# TLDs habituales. Limitar la lista evita falsos positivos tipo "Sr.García" o "p.ej".
COMMON_TLDS = {
    "com", "es", "net", "org", "info", "eu", "io", "co", "me", "app", "dev", "biz",
    "xyz", "top", "icu", "click", "live", "shop", "online", "site", "vip", "cc", "buzz",
    "link", "club", "store", "website", "tk", "ml", "ga", "cf", "gq", "ly", "gl", "to",
    "uk", "fr", "de", "it", "pt", "nl", "be", "ch", "at", "pl", "ru", "cn", "us", "mx",
    "ar", "cl", "pe", "br", "tech", "help", "support", "pro", "fun", "work", "monster",
    "rest", "cam", "sbs", "cfd", "bond", "lat", "ws", "in", "gob", "gov", "cat", "gal",
    "eus", "ai", "ink", "page", "services", "digital", "email", "cloud", "mobi", "art",
}

URL_RE = re.compile(
    r"(?<![@\w.])((?:https?://)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,24})(?![\w-])(?::\d{2,5})?(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
IP_URL_RE = re.compile(r"\bhttps?://\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/[^\s]*)?", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE_RE = re.compile(r"(?:(?:\+|00)\d[\d\s.-]{7,16}\d)|(?<![\d,.])[6-9]\d{2}(?:[\s.-]?\d{2,3}){2,3}(?![\d,])")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b")
AMOUNT_RE = re.compile(
    r"(?:(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s?(?:€|euros?\b|eur\b))|(?:€\s?(\d+(?:[.,]\d{1,2})?))",
    re.IGNORECASE,
)


IBAN_LENGTHS = {"ES": 24, "PT": 25, "FR": 27, "DE": 22, "IT": 27, "GB": 22, "IE": 22, "NL": 18, "BE": 16,
                "LT": 20, "LV": 21, "EE": 20, "PL": 28, "RO": 24, "LU": 20, "MT": 31, "CY": 28, "CH": 21,
                "AT": 20, "BG": 22, "HR": 21, "GR": 27, "DK": 18, "SE": 24, "FI": 18, "CZ": 24}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    """Minúsculas y sin tildes, para buscar palabras clave de forma robusta."""
    return strip_accents(text.lower())


@dataclass
class Entities:
    urls: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    ibans: list[str] = field(default_factory=list)
    amounts: list[float] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enlaces": self.urls,
            "telefonos": self.phones,
            "ibans": self.ibans,
            "importes": self.amounts,
            "emails": self.emails,
        }


def _parse_amount(raw: str) -> float | None:
    raw = raw.replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") >= 1 and len(raw.split(".")[-1]) == 3:
        raw = raw.replace(".", "")  # 1.500 -> 1500
    try:
        return float(raw)
    except ValueError:
        return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_entities(text: str) -> Entities:
    ent = Entities()
    emails = EMAIL_RE.findall(text)
    ent.emails = _dedupe(emails)
    text_no_emails = EMAIL_RE.sub(" ", text)

    urls = [m.group(0) for m in IP_URL_RE.finditer(text_no_emails)]
    for m in URL_RE.finditer(text_no_emails):
        url, tld = m.group(1), m.group(2).lower()
        if tld not in COMMON_TLDS:
            continue
        urls.append(url.rstrip(".,;:!?)»\"'"))
    ent.urls = _dedupe(urls)

    ibans = []
    for m in IBAN_RE.finditer(text.upper()):
        compact = m.group(0).replace(" ", "")
        expected = IBAN_LENGTHS.get(compact[:2])
        if expected:
            if len(compact) < expected:
                continue
            compact = compact[:expected]  # evita comerse palabras que siguen al IBAN
        if 15 <= len(compact) <= 34:
            ibans.append(compact)
    ent.ibans = _dedupe(ibans)

    text_for_phones = IBAN_RE.sub(" ", text.upper())
    phones = []
    for m in PHONE_RE.finditer(text_for_phones):
        raw = m.group(0)
        digits = re.sub(r"[^\d+]", "", raw)
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        n_digits = len(digits.lstrip("+"))
        if digits.startswith("+") and 9 <= n_digits <= 15:
            phones.append(digits)
        elif not digits.startswith("+") and n_digits == 9:
            phones.append(digits)
    ent.phones = _dedupe(phones)

    amounts = []
    for m in AMOUNT_RE.finditer(text):
        value = _parse_amount(m.group(1) or m.group(2) or "")
        if value is not None and value > 0:
            amounts.append(value)
    ent.amounts = amounts
    return ent
