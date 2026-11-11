"""La IA no puede dar por tranquilo (verde) un mensaje que las reglas marcan en rojo (11-11-2026).

Antes, solo cuatro señales concretas (enlace que imita a una marca, IBAN extranjero, familiar desconocido,
dominio reciente) impedían un verde de Claude. El falso hijo que pide un Bizum urgente da rojo en reglas sin
ninguna de esas cuatro cuando se pega el mensaje sin remitente, así que un verde de la IA pasaba tal cual.
Además, al subir un verde a amarillo se conservaba el texto y la voz de la IA («todo bien»): ahora, si la red
de seguridad salta y las reglas tienen veredicto, manda el de las reglas entero (nivel, texto y voz coherentes).
"""
import asyncio

from app import analyzer
from app.analyzer import NOTA_RED_DE_SEGURIDAD, _merge_with_rules
from app.config import settings
from app.rules import analyze_rules

FALSO_HIJO = ("Hola mamá, se me ha roto el móvil y este es mi número nuevo. ¿Me haces un Bizum de 480 €? "
              "Es urgente, mañana te lo devuelvo, no me puedes llamar ahora.")
STRONG = {"enlace_imita_marca", "iban_extranjero", "familiar_desconocido", "dominio_reciente"}


def _verde():
    return {"nivel": "verde", "puntuacion": 5, "titulo": "Parece un mensaje normal", "tipo_estafa": None,
            "explicacion": "No vemos nada raro.", "pruebas": ["Parece normal"], "consejo": "Tranquilo.",
            "mensaje_voz": "Todo bien, puedes estar tranquilo."}


def test_el_falso_hijo_sin_remitente_es_rojo_sin_pruebas_fuertes():
    r = analyze_rules(FALSO_HIJO, None, [])
    assert r.level == "rojo"
    assert not ({s.id for s in r.signals} & STRONG)


def test_un_verde_de_la_ia_ante_un_rojo_de_las_reglas_usa_el_veredicto_de_las_reglas():
    r = analyze_rules(FALSO_HIJO, None, [])
    v, fuente = _merge_with_rules(_verde(), r, strong_evidence=False)
    assert v["nivel"] == "rojo" and fuente == "reglas"
    assert "tranquilo" not in v["mensaje_voz"].lower()  # la voz ya no dice «todo bien»
    assert NOTA_RED_DE_SEGURIDAD in v["pruebas"]


def test_un_amarillo_o_rojo_de_la_ia_se_respeta():
    r = analyze_rules(FALSO_HIJO, None, [])
    v, fuente = _merge_with_rules({"nivel": "amarillo", "puntuacion": 55, "pruebas": []}, r, False)
    assert (v["nivel"], v["puntuacion"], fuente) == ("amarillo", 55, "ia")
    v, fuente = _merge_with_rules({"nivel": "rojo", "puntuacion": 90, "pruebas": []}, r, True)
    assert (v["nivel"], fuente) == ("rojo", "ia")


def test_si_las_reglas_no_dan_rojo_ni_hay_pruebas_fuertes_decide_la_ia():
    r = analyze_rules("Hola, ¿comemos el domingo en casa de la abuela?", None, [])
    assert r.level == "verde"
    v, fuente = _merge_with_rules(_verde(), r, False)
    assert (v["nivel"], fuente) == ("verde", "ia")


def test_las_pruebas_fuertes_siguen_impidiendo_el_verde():
    r = analyze_rules("Hola mamá, este es mi número nuevo, guárdalo", "+34711000999", [])
    assert {s.id for s in r.signals} & STRONG and r.level != "verde"
    v, fuente = _merge_with_rules(_verde(), r, True)
    assert v["nivel"] == r.level and fuente == "reglas"


def test_flujo_completo_con_una_ia_que_dice_verde(monkeypatch, tmp_path):
    """De punta a punta por analyze_stream, con un agente simulado que responde verde."""
    monkeypatch.setattr(settings, "anthropic_api_key", "falsa")
    monkeypatch.setattr(settings, "force_offline", False)

    async def ia_que_dice_verde(*args, **kwargs):
        yield {"tipo": "veredicto", "datos": _verde()}

    monkeypatch.setattr(analyzer, "investigate", ia_que_dice_verde)

    async def run():
        async for ev in analyzer.analyze_stream(texto=FALSO_HIJO, remitente=None):
            if ev["tipo"] == "resultado":
                return ev["datos"]

    resultado = asyncio.run(run())
    assert resultado["veredicto"]["nivel"] == "rojo"
    assert resultado["fuente"] == "reglas"
