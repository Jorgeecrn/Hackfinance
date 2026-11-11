"""Motor de reglas: análisis rápido y determinista (milisegundos).

Sirve como (1) prefiltro que se pasa al agente de IA, (2) respaldo si no hay IA
y (3) línea base para comparar en la evaluación.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import tools
from .entities import Entities, extract_entities, normalize


@dataclass
class Signal:
    id: str
    label: str           # explicación sencilla para el usuario
    weight: int          # puntos de riesgo (negativo = señal de legitimidad)
    evidence: str = ""


@dataclass
class RuleResult:
    score: int
    level: str
    signals: list[Signal]
    entities: Entities
    url_reports: list[dict] = field(default_factory=list)
    phone_reports: list[dict] = field(default_factory=list)
    iban_reports: list[dict] = field(default_factory=list)
    campaigns: list[dict] = field(default_factory=list)
    sender_report: dict | None = None

    def to_dict(self) -> dict:
        return {
            "puntuacion": self.score,
            "nivel": self.level,
            "senales": [s.__dict__ for s in self.signals],
            "entidades": self.entities.to_dict(),
            "enlaces": self.url_reports,
            "telefonos": self.phone_reports,
            "ibans": self.iban_reports,
            "campanas": self.campaigns,
            "remitente": self.sender_report,
        }


# (id, explicación, peso, patrones sobre texto normalizado sin tildes)
PATTERNS: list[tuple[str, str, int, list[str]]] = [
    ("familiar_numero_nuevo", "Dice ser un familiar que ha cambiado de número", 45, [
        r"(numero nuevo|nuevo numero|cambiado de (numero|movil|telefono)|este es mi (nuevo )?(numero|movil)|se me ha (roto|caido|mojado) el (movil|telefono)|movil (roto|nuevo)|perdi el movil|guarda (este|mi) numero)",
    ]),
    ("trato_familiar", "Se dirige a ti como familiar (mamá, papá, abuelo...)", 10, [
        r"\b(mama|papa|abuela|abuelo|abu|yaya|yayo|hijo|hija|tita|tito)\b",
    ]),
    ("urgencia", "Mete prisa para que no pienses", 15, [
        r"\b(urgente|urgentemente|inmediatamente|cuanto antes|hoy mismo|lo antes posible|ahora mismo|rapido|en las proximas \d+ ?(h|horas)|en \d+ ?(h|horas)|ultimo aviso|ultima oportunidad|de inmediato|antes de las)\b",
        r"\b(antes de \d+ ?(minutos|min|horas|h)|en (los proximos|menos de) \d+ ?(minutos|min))\b",
    ]),
    ("amenaza", "Amenaza con bloqueos, multas o cortes", 20, [
        r"\b(bloquead[oa]s?|suspendid[oa]s?|cancelad[oa]s?|desactivad[oa]s?|restringid[oa]s?|embargo|recargo|sancion|multa|corte de suministro|se cerrara|perdera|caducad[oa]|se (cortara|suspendera|cancelara)|cortaremos|suspenderemos|no ha podido (cobrarse|cobrar))\b",
    ]),
    ("pide_dinero", "Te pide dinero (transferencia, Bizum, pago)", 25, [
        r"\b(transferencia|transfiere|transferir|bizum|hazme un ingreso|ingresa|ingresar|envia(me)? dinero|mandame|presta(me)?|dejame \d+|necesito \d+|pagar? (la|una) (tasa|factura|multa)|abone|abonar|realice el pago|pague|regularice (el pago|su deuda|la deuda|el importe))\b",
    ]),
    ("pide_credenciales", "Pide claves, códigos o datos de tu tarjeta", 35, [
        r"\b(contrasena|clave|pin|cvv|cvc|codigo (que te|que le|de verificacion|sms|recibido)|numero de (la )?tarjeta|datos (de la tarjeta|bancarios|personales)|fecha de caducidad|coordenadas|dime el codigo|reenviame el codigo|facilitenos|confirme sus datos|verifique sus datos|verificar (su|tu) identidad|actualizar (sus|tus) datos)\b",
        # «confirme su identidad con sus datos habituales de acceso» (falso gestor)
        r"\b(confirm\w* (su|tu) identidad|(sus|tus) datos (habituales )?de acceso)\b",
    ]),
    ("secretismo", "Pide que no se lo cuentes a nadie", 25, [
        r"(no se lo digas|que no se entere|no le digas nada|entre tu y yo|no lo cuentes|es un secreto|no llames a)",
    ]),
    ("no_puede_hablar", "Evita hablar por teléfono (no puedes comprobar su voz)", 20, [
        r"(no puedo (hablar|llamar)|no me llames|ahora no puedo hablar|el microfono no (me )?funciona|solo por (mensaje|whatsapp)|escribeme por aqui)",
    ]),
    ("llamada_a_enlace", "Te pide pulsar un enlace para resolverlo", 15, [
        r"\b(pulse|pulsa|haga clic|haz clic|clic aqui|clica|acceda|accede|entre en|entra en|siga el enlace|en el siguiente enlace|desde este enlace|link)\b",
    ]),
    ("premio", "Promete premios, regalos o dinero fácil", 20, [
        r"\b(has ganado|ha ganado|ganador|premio|sorteo|regalo|gratis|felicidades|seleccionad[oa]|reembolso pendiente|devolucion pendiente)\b",
    ]),
    ("inversion_milagro", "Promete ganancias o inversiones garantizadas", 30, [
        r"(rentabilidad garantizada|beneficios garantizados|duplica(r)? tu dinero|ganancias (diarias|seguras|garantizadas)|invierte (solo|ahora)|cripto(moneda)?s?|bitcoin|trading|sin riesgo)",
    ]),
    ("trabajo_facil", "Ofrece trabajo fácil desde casa con pagos rápidos", 25, [
        r"(trabajo desde casa|ganar? \d+ ?(€|euros) al dia|dar likes|valorar (productos|hoteles)|tareas sencillas|reclutador|recursos humanos)",
    ]),
    ("control_remoto", "Pide instalar una aplicación o dar acceso al móvil", 35, [
        r"\b(anydesk|teamviewer|quicksupport|acceso remoto|instale (la|esta) (app|aplicacion)|descargue la aplicacion|instala esta app)\b",
    ]),
    ("bizum_inverso", "Te pide aceptar un Bizum (eso sería enviar dinero, no recibirlo)", 30, [
        r"(acepta(r)? (el|la) (bizum|solicitud)|para recibir el (pago|dinero)|te he enviado (un|una) solicitud|te mande por error|devuelvemelo)",
        # «solicitud de Bizum/pago … para recibir/cobrar / reembolso / devolución … acéptela» (en cualquier orden)
        r"solicitud(es)? de (bizum|pago|dinero|cobro)[^\n]{0,120}?\b(para (recibir|cobrar|que (se )?(te|le) (llegue|ingres))|reembols\w*|devoluc\w*|ingres\w*)[^\n]{0,120}?\b(acept|autoric|aprueb|aprob)\w*",
        r"\b(para (recibir|cobrar)|reembols\w*|devoluc\w*)[^\n]{0,120}?\b(acept|autoric|aprueb|aprob)\w*[^\n]{0,40}\bsolicitud",
        r"\b(acept|autoric|aprueb|aprob)\w*[^\n]{0,40}\bsolicitud(es)? de (bizum|pago|dinero|cobro)[^\n]{0,80}(para (recibir|cobrar|que (se )?(te|le) (llegue|ingres))|reembols|devoluc|ingres)",
    ]),
    ("cuenta_segura", "Te pide mover tu dinero a una «cuenta segura» (ningún banco lo pide)", 45, [
        r"\bcuenta (segura|de seguridad|refugio|puente|protegida)\b",
    ]),
    ("cargo_no_reconocido", "Habla de un cargo o compra que no reconoces para asustarte", 20, [
        r"(si no (reconoce|reconoces|ha realizado|has realizado) (esta|este|la|el) (operacion|compra|cargo|pago)|cargo no reconocido|compra no autorizada|operacion sospechosa)",
    ]),
    # Sin peso: los avisos reales de operaciones también dicen «si no has sido tú». Solo suma junto a un enlace
    # para «anular» la operación (combo_cargo_enlace).
    ("operacion_no_hecha", "Dice que se ha hecho una operación «por si no has sido tú»", 0, [
        r"(si no (ha|has) sido (usted|tu)|si usted no (la|lo)? ?(ha realizado|ha autorizado|reconoce)|si no (la|lo) (reconoce|reconoces|ha autorizado|has autorizado))",
    ]),
]

LEGIT_PATTERNS: list[tuple[str, str, int, list[str]]] = [
    ("aviso_no_compartir", "Incluye el aviso típico de mensajes legítimos («no compartas este código»)", -25, [
        r"(no (lo )?compartas (este|el) codigo|nunca te (pediremos|llamaremos)|no lo facilites a nadie|nadie de .* te lo pedira)",
        # mismas fórmulas con «usted» (los SMS reales de bancos y organismos suelen usarlo)
        r"(no (lo|la) comparta (con nadie|este codigo)|no comparta (este|el|su) (codigo|contrasena|clave|pin)|nunca le (pediremos|llamaremos|pedira|solicitaremos)|ningun empleado (se lo|le) (pedira|solicitara)|no lo facilite a nadie)",
        # consejos de seguridad: describen la estafa y dicen que NO se haga
        r"(para (recibir|cobrar)[^.\n]{0,40}(nunca|no) (tiene|tienes|es necesario|hace falta|debe|debes)[^.\n]{0,15}acept|sin (tener que|necesidad de) acept|no (es necesario|hace falta) acept|(si recibe|si recibes)[^.\n]{0,80}, no (la|lo) (acepte|aceptes))",
    ]),
]

SHORT_OTP = re.compile(r"\b(codigo|code)\b.{0,60}\b\d{4,8}\b")
#: Consejo, no petición: «si recibe una solicitud de Bizum para cobrar, NO la acepte». La negación suele ir
#: después de «solicitud», dentro de lo que coincide con la regla del Bizum inverso.
ACCEPT_NEGATED = re.compile(
    r"\b(no|nunca|jamas)\s+((la|lo|las|los|le|se|debe|deben|tiene|tienes|hay|necesita|necesitas|que|es necesario|hace falta)\s+){0,3}"
    r"(acept|autoric|aprueb|aprob)\w*|\bsin (tener que |necesidad de )?(acept|autoriz|aprob)\w*")


def _level(score: int) -> str:
    if score >= 60:
        return "rojo"
    if score >= 30:
        return "amarillo"
    return "verde"


def _match(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return None


def analyze_rules(text: str, sender: str | None = None, contacts: list[dict] | None = None) -> RuleResult:
    norm = normalize(text)
    entities = extract_entities(text)
    signals: list[Signal] = []

    for sid, label, weight, patterns in PATTERNS + LEGIT_PATTERNS:
        ev = _match(patterns, norm)
        if ev:
            signals.append(Signal(sid, label, weight, ev))

    # Bizum inverso dentro de un consejo («… no la acepte»): no es una petición
    for s_ in [s_ for s_ in signals if s_.id == "bizum_inverso"]:
        pos = norm.find(s_.evidence)
        if ACCEPT_NEGATED.search(norm[max(0, pos - 40):pos + len(s_.evidence) + 5]):
            signals.remove(s_)

    ids = {s.id for s in signals}
    # Combinaciones especialmente peligrosas
    if {"familiar_numero_nuevo", "pide_dinero"} <= ids or ({"trato_familiar", "pide_dinero", "urgencia"} <= ids):
        signals.append(Signal("combo_hijo_apuros", "Patrón del timo del «hijo en apuros»: familiar + dinero", 25))
    if entities.urls and ids & {"premio", "pide_dinero", "pide_credenciales", "inversion_milagro"}:
        signals.append(Signal("enlace_con_peticion", "Te manda a un enlace para pagar, reclamar algo o dar tus datos", 15))
    if ids & {"cargo_no_reconocido", "operacion_no_hecha"} and entities.urls:
        signals.append(Signal("combo_cargo_enlace", "Te asusta con una operación que no has hecho y te manda a un enlace para «anularla»", 35))
    if "amenaza" in ids and (entities.urls or "llamada_a_enlace" in ids):
        signals.append(Signal("combo_amenaza_enlace", "Amenaza y te manda a un enlace para «solucionarlo»", 15))
    if "pide_credenciales" in ids and SHORT_OTP.search(norm) and "aviso_no_compartir" in ids:
        # SMS legítimo con código: no debe penalizarse como petición de credenciales
        signals = [s for s in signals if s.id != "pide_credenciales"]

    # Remitente
    sender_report = None
    if sender:
        sender_digits = re.sub(r"[^\d+]", "", sender)
        if len(sender_digits.lstrip("+")) >= 9:
            sender_report = tools.analyze_phone(sender, contacts)
            if not sender_report["contacto"]:
                if "familiar_numero_nuevo" in ids or "trato_familiar" in ids:
                    signals.append(Signal("familiar_desconocido", "Dice ser de tu familia pero escribe desde un número que no tienes guardado", 25, sender))
                else:
                    signals.append(Signal("remitente_desconocido", "El remitente no está en tus contactos", 5, sender))
            else:
                signals.append(Signal("remitente_conocido", f"El remitente es {sender_report['contacto'].get('nombre')}, de tus contactos", -30, sender))
            if sender_report.get("pais") and sender_report["pais"] != "España":
                signals.append(Signal("remitente_extranjero", f"Escribe desde un número de {sender_report['pais']}", 15, sender))

    # Enlaces
    url_reports = [tools.analyze_url(u) for u in entities.urls[:5]]
    for rep in url_reports:
        if rep["imita_a"]:
            signals.append(Signal("enlace_imita_marca", f"El enlace imita a {rep['imita_a']} pero no es su web oficial", 45, rep["dominio"]))
        elif rep["riesgo"] >= 25:
            signals.append(Signal("enlace_sospechoso", "El enlace tiene características sospechosas", 20, rep["dominio"]))
        elif rep["oficial_de"]:
            signals.append(Signal("enlace_oficial", f"El enlace es de la web oficial de {rep['oficial_de']}", -15, rep["dominio"]))
        if rep.get("antiguedad", {}).get("dias") is not None and rep["antiguedad"]["dias"] < 30:
            signals.append(Signal("dominio_reciente", f"La web se creó hace solo {rep['antiguedad']['dias']} días", 25, rep["dominio"]))

    phone_reports = [tools.analyze_phone(p, contacts) for p in entities.phones[:3]]
    for rep in phone_reports:
        if rep["riesgo"] >= 40:
            signals.append(Signal("telefono_sospechoso", "Te pide llamar a un número sospechoso", 20, rep["telefono"]))

    iban_reports = [tools.analyze_iban(i) for i in entities.ibans[:3]]
    for rep in iban_reports:
        if rep["pais"] != "España":
            signals.append(Signal("iban_extranjero", f"Te da una cuenta bancaria de {rep['pais']}", 25, rep["iban"]))
        if not rep["valido"]:
            signals.append(Signal("iban_invalido", "El número de cuenta no es válido", 10, rep["iban"]))

    campaigns = tools.search_campaigns(text)
    if campaigns and campaigns[0]["similitud"] >= 0.5:
        signals.append(Signal("campana_conocida", f"Se parece a una estafa conocida: {campaigns[0]['nombre']}", 15, campaigns[0]["id"]))

    score = sum(s.weight for s in signals)
    score = max(0, min(100, score))
    return RuleResult(score, _level(score), signals, entities, url_reports, phone_reports, iban_reports, campaigns, sender_report)


def explain_rules(res: RuleResult) -> dict:
    """Construye un veredicto legible usando solo las reglas (modo sin IA)."""
    risky = sorted((s for s in res.signals if s.weight > 0), key=lambda s: -s.weight)
    camp = res.campaigns[0] if res.campaigns else None
    if res.level == "rojo":
        titulo = f"Cuidado: {camp['titulo'][0].lower() + camp['titulo'][1:]}" if camp else "Muy probablemente es una estafa"
    elif res.level == "amarillo":
        titulo = "Cuidado: este mensaje tiene señales sospechosas"
    else:
        titulo = "No vemos señales de estafa"
    pruebas = [s.label + (f" ({s.evidence})" if s.evidence and s.id.startswith(("enlace", "iban", "dominio")) else "") for s in risky[:5]]
    if res.level == "verde":
        pruebas = [s.label for s in res.signals if s.weight < 0] or ["No hemos encontrado peticiones de dinero, claves ni enlaces peligrosos."]
        resumen = "No hemos encontrado peticiones de dinero, claves ni enlaces peligrosos."
    else:
        principales = [s.label[0].lower() + s.label[1:] for s in risky[:3]]
        resumen = "Hemos visto estas señales de alarma: " + (", ".join(principales[:-1]) + " y " + principales[-1] if len(principales) > 1 else principales[0]) + "."
    consejo = camp["consejo"] if camp and res.level != "verde" else (
        "No respondas, no pulses enlaces y no envíes dinero. Si dudas, llama tú directamente a la persona o entidad a su número de siempre."
        if res.level != "verde" else "Aun así, nunca compartas claves ni códigos con nadie."
    )
    tipo = camp["nombre"] if camp and res.level != "verde" else None
    return {
        "nivel": res.level,
        "puntuacion": res.score,
        "titulo": titulo,
        "tipo_estafa": tipo,
        "explicacion": resumen,
        "pruebas": pruebas,
        "consejo": consejo,
        "mensaje_voz": f"{titulo}. {resumen} {consejo}",
        "acciones": _actions(res.level),
    }


def _actions(level: str) -> list[str]:
    if level == "rojo":
        return ["llamar_familiar", "avisar_familiar", "reportar", "escudo_bancario"]
    if level == "amarillo":
        return ["llamar_familiar", "avisar_familiar", "reportar"]
    return []
