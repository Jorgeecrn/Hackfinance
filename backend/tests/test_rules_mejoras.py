"""Mejoras del motor de reglas (10-11-2026).

Huecos encontrados con un sondeo de mensajes NUEVOS (no están en eval/dataset.jsonl), redactados a partir de
tipologías públicas de estafa en España (avisos de INCIBE/OSI, Banco de España, Policía). Los escribió una IA:
sirven como regresiones, no como evaluación independiente. Para no hacer trampa con la métrica, las reglas no
se han ajustado a los mensajes de eval/dataset.jsonl.
"""
import pytest

from app.rules import analyze_rules

DESCONOCIDO = "+34711000999"

BIZUM_INVERSO = [
    "Le hemos enviado una solicitud de Bizum para recibir el reembolso de su compra en Wallapop. Acéptela en su app "
    "para que se le ingrese el dinero.",
    "Hola, ya te he pagado el artículo. Te llegará una solicitud de Bizum para cobrar los 45 €, solo tienes que "
    "aceptarla y el dinero te entra en la cuenta.",
    "Para completar la devolución, acepte la solicitud de pago de 120 € que le ha llegado para recibir su dinero.",
    "Le hemos cobrado dos veces. Para la devolución del importe, autorice la solicitud de dinero que verá en su app.",
    "Su reembolso está listo: apruebe la solicitud de cobro en Bizum para recibirlo hoy.",
    # «no pierda…» no es una negación de «aceptar»
    "No pierda su reembolso de 89 €: acepte la solicitud de Bizum que le hemos enviado para recibirlo.",
]

CONSEJOS = [
    "Recuerde: si recibe una solicitud de Bizum para cobrar un reembolso, no la acepte. Para recibir dinero nunca "
    "tiene que aceptar nada.",
    "Consejo de seguridad: para recibir un Bizum no es necesario aceptar ninguna solicitud de pago.",
    "Con Bizum puede recibir dinero sin tener que aceptar ninguna solicitud.",
    "Su banco nunca le pedirá sus claves por SMS. No comparta su contraseña con nadie.",
]


@pytest.mark.parametrize("texto", BIZUM_INVERSO)
def test_bizum_inverso_en_cualquier_orden(texto):
    r = analyze_rules(texto, DESCONOCIDO, [])
    assert "bizum_inverso" in {s.id for s in r.signals}, texto
    assert r.level in ("amarillo", "rojo"), texto


@pytest.mark.parametrize("texto", CONSEJOS)
def test_consejos_de_seguridad_no_alertan(texto):
    r = analyze_rules(texto, None, [])
    assert "bizum_inverso" not in {s.id for s in r.signals}, texto
    assert r.level == "verde", texto


def test_otp_legitimo_con_usted_es_verde():
    r = analyze_rules("Su código de verificación es 482913. No lo comparta con nadie. Ningún empleado se lo pedirá.",
                      None, [])
    assert r.level == "verde"
    assert "pide_credenciales" not in {s.id for s in r.signals}


def test_cuenta_segura_alerta():
    r = analyze_rules("Su gestor de CaixaBank: para proteger sus ahorros de un ataque informático debe traspasarlos a "
                      "una cuenta segura. Le llamaremos para indicarle el IBAN.", DESCONOCIDO, [])
    assert "cuenta_segura" in {s.id for s in r.signals}
    assert r.level in ("amarillo", "rojo")


def test_cargo_no_reconocido_con_telefono_alerta():
    r = analyze_rules("BBVA: se ha realizado un cargo de 899,00 EUR en su tarjeta. Si no reconoce esta operación, "
                      "llame inmediatamente al 912 345 678.", None, [])
    assert "cargo_no_reconocido" in {s.id for s in r.signals}
    assert r.level in ("amarillo", "rojo")


def test_corte_de_suministro_con_acortador_alerta():
    r = analyze_rules("Iberdrola: su factura no ha podido cobrarse y el suministro se cortará mañana. Regularice el "
                      "pago aquí: bit.ly/3xYzAb", None, [])
    assert r.level in ("amarillo", "rojo")


def test_saltos_de_linea_cortan_el_bizum_inverso():
    texto = "Le enviamos una solicitud de pago por la cuota del club.\n\nAcepte el reglamento para recibir el carné."
    assert "bizum_inverso" not in {s.id for s in analyze_rules(texto, None, []).signals}


@pytest.mark.parametrize("texto", [
    "Iberdrola: su factura de octubre de 54,20€ ya está disponible en su área de cliente.",
    "Tu reembolso de 34,99 € ha sido procesado y lo verás en tu cuenta en 3-5 días hábiles.",
    "Has recibido un Bizum de 15,00 EUR de LAURA G. Concepto: cena viernes.",
])
def test_notificaciones_reales_siguen_en_verde(texto):
    assert analyze_rules(texto, None, []).level == "verde", texto
