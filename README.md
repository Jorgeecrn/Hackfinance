# 🛡️ Centinela

**Protección contra estafas por mensajes para personas mayores, con IA que investiga, habla y frena el dinero.**

Centinela es una app web instalable (PWA) que revisa los SMS, mensajes de WhatsApp, capturas y notas de voz que recibe una persona mayor, **investiga** si son una estafa (comprueba enlaces, teléfonos y números de cuenta), se lo **explica en voz alta** con palabras sencillas, **avisa a un familiar de confianza** y, si el timo es grave, activa un **escudo bancario** que retiene las transferencias a cuentas nuevas hasta que el familiar las revise.

> Proyecto para el HackFinance · Madrid Engineering Week (GPTadvisor · MyInvestor · Claude · ElevenLabs).

---

## ¿Qué problema resuelve?

- El timo del «hijo en apuros» («Hola mamá, este es mi número nuevo») y los SMS que suplantan a bancos, Correos o la DGT llegan a diario. En enero de 2026 la Policía Nacional y la Guardia Civil lanzaron una alerta conjunta sobre el fraude del falso hijo.
- Ya hay casos en España con **notas de voz con voz clonada por IA**.
- Las personas mayores son el objetivo principal y las soluciones actuales (filtros de spam, Google Messages) solo funcionan en algunos móviles, solo con SMS, no explican nada y no implican ni a la familia ni al banco.

## ¿Qué hace?

| Función | Cómo |
|---|---|
| 🔍 **Agente investigador** | Claude con *tool use* comprueba cada enlace (¿imita a un banco?, ¿web recién creada?, ¿acortador?), teléfono (¿extranjero?, ¿está en tus contactos?, ¿reportado?) e IBAN (¿válido?, ¿de qué país y banco?), y lo compara con campañas de estafa conocidas. |
| 🧾 **Pruebas, no porcentajes** | El veredicto (🟢🟡🔴) viene con las pruebas concretas: «La web se creó hace 2 días e imita a MyInvestor». |
| 🎙️ **Notas de voz** | Transcribe audios de WhatsApp con **ElevenLabs Scribe** y los analiza (el timo del falso hijo llega cada vez más como audio). También permite **leer el mensaje en voz alta** a quien no sabe copiar y pegar. |
| 🔊 **Avisos hablados** | El veredicto se lee con una voz tranquila de **ElevenLabs** (o la voz de un familiar, con su consentimiento). |
| 👪 **Familiar de confianza** | Recibe la alerta al momento (panel en tiempo real y, opcionalmente, Telegram) y aprueba o cancela operaciones retenidas. |
| 🏦 **Escudo bancario** | Tras una alerta roja, el banco retiene durante 60 min los pagos ≥ 300 € a beneficiarios nuevos (simulado: muestra la integración con un banco como MyInvestor). |
| 📲 **PWA instalable** | Interruptor de protección en Ajustes, bandeja de mensajes con semáforo, «Compartir → Centinela» desde WhatsApp (Web Share Target), letra grande y alto contraste. |
| 🛟 **Modo de respaldo** | Sin claves de API funciona con un motor de reglas determinista (milisegundos), que también sirve de red de seguridad para la IA. |

## Arquitectura

```
 App de Banco Demo (PWA, HTML/JS sin build)  Panel familia      Control demo
 index.html · Inicio · Transferir ·          familia.html       demo.html
   Protección (Centinela) · Perfil
        │  fetch + SSE (pasos en directo)           │ SSE              │ SSE
        ▼                                           ▼                  ▼
 FastAPI (backend/app/main.py) ─────────── bus de eventos (events.py)
   ├─ analyzer.py   orquesta: nota de voz → texto → reglas → agente → acciones
   ├─ elevenlabs.py Scribe (voz→texto) · TTS (texto→voz)
   ├─ rules.py      prefiltro determinista: señales + entidades (ms)
   ├─ agent.py      Claude: tool use + salida estructurada (JSON schema)
   │     └─ tools.py analizar_enlace · analizar_telefono · analizar_iban
   │                 buscar_campanas · buscar_contacto  (RDAP, Safe Browsing opcional)
   ├─ bank.py       escudo bancario: retener / aprobar / cancelar
   └─ state.py      estado de la demo en JSON (perfil, contactos, alertas, banco)
```

Decisiones clave:
- **La IA investiga, las herramientas comprueban.** Claude decide qué comprobar y redacta la explicación; los hechos (antigüedad de una web, país de un IBAN, si un número está en tus contactos) salen de herramientas deterministas, así que la IA no se los inventa.
- **Red de seguridad.** Si hay pruebas objetivas fuertes (web que imita a una entidad, cuenta extranjera, falso familiar desde número desconocido), el resultado nunca baja de 🟡 aunque la IA diga 🟢. Si la IA falla o no responde, se usa el motor de reglas.
- **Pocas falsas alarmas.** El prompt y las reglas tratan explícitamente los mensajes legítimos que se parecen a timos (SMS reales con código «no lo compartas», familiares guardados que piden un Bizum normal).
- **Privacidad.** No se guarda audio. Solo se analizan los mensajes que llegan o que el usuario comparte.

## Requisitos

- Python 3.11 o superior
- (Opcional) Clave de API de Anthropic para el agente con Claude
- (Opcional) Clave de API de ElevenLabs para notas de voz y voz natural
- Un navegador moderno (Chrome/Edge/Safari/Firefox). Para instalarla como app y usar «Compartir», Chrome en Android.

## Arranque rápido (doble clic)

- **Mac:** doble clic en `iniciar.command`. La primera vez, si macOS lo bloquea, clic derecho → **Abrir** → **Abrir**.
- **Windows:** doble clic en `iniciar.bat`.

La primera vez prepara el entorno e instala las dependencias (un par de minutos); después arranca en segundos y abre el panel de la demo en el navegador. Deja la ventana abierta mientras la uses. Solo necesitas tener Python 3.11 o superior.

## Instalación

```bash
git clone <URL-del-repo> centinela
cd centinela
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # y rellena las claves que tengas
```

## Configuración (`.env`)

| Variable | Para qué | ¿Obligatoria? |
|---|---|---|
| `ANTHROPIC_API_KEY` | Agente investigador con Claude y análisis de capturas | No (sin ella: modo reglas) |
| `CLAUDE_MODEL` | Modelo (por defecto `claude-opus-5-5`) | No |
| `CLAUDE_EFFORT` | `low` (rápido, recomendado en demo) o `medium` | No |
| `ELEVENLABS_API_KEY` | Transcribir notas de voz y voz natural | No (sin ella: voz del navegador, sin notas de voz) |
| `ELEVENLABS_VOICE_ID` | Voz de los avisos (elige una voz española en la Voice Library) | No |
| `GOOGLE_SAFE_BROWSING_KEY` | Comprobar enlaces contra la lista de Google | No |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Aviso real al móvil del familiar | No |
| `SHIELD_MINUTES`, `SHIELD_AMOUNT_THRESHOLD` | Duración y umbral del escudo bancario | No |

## Ejecución

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abre:
- **http://localhost:8000/** → app de **Banco Demo** con Carmen López: Inicio, Transferir, **Protección** (Centinela integrado) y Perfil. Ábrela en el móvil o en modo móvil del navegador.
- **http://localhost:8000/familia.html** → panel del familiar (avisos y transferencias en revisión)
- **http://localhost:8000/demo.html** → panel del presentador para enviar mensajes simulados
- **http://localhost:8000/docs** → documentación interactiva de la API

Todas las herramientas del equipo (presentador, analista, familiar, SMS de demo, API y «Reiniciar toda la demo») están en la app, en **Perfil → Herramientas de demo**.

> Para probar en el móvil en la misma wifi: `http://<IP-de-tu-portátil>:8000`. La instalación como app, el micrófono y «Compartir» requieren HTTPS fuera de `localhost`. Para la demo puedes usar un túnel HTTPS (por ejemplo `cloudflared tunnel --url http://localhost:8000` o `ngrok http 8000`).

## Pruebas

```bash
# Tests automáticos (sin red ni claves)
cd backend && python -m pytest -q

# Evaluación de la detección sobre 74 mensajes etiquetados (40 estafas, 34 legítimos)
cd .. && python eval/run_eval.py --modo reglas      # instantáneo y gratis
python eval/run_eval.py --modo ia                   # agente con Claude (necesita ANTHROPIC_API_KEY)
```

Cada ejecución escribe un informe en `eval/resultados_<modo>.md` con precisión, recall, falsas alarmas, latencia y la lista de fallos.

## Guion de la demo (unos 6 minutos)

Una sola historia: Carmen usa la app de su banco, **Banco Demo**, que trae la protección antiestafas de Centinela integrada.

1. **Inicio.** Abre la app (`/`) en un móvil y `demo.html`, `familia.html` y `llamada/analista.html` en el portátil (enlaces en Perfil → Herramientas de demo). Pulsa una vez en el móvil para permitir el sonido. Carmen ve su saldo y el banner «🛡️ Protección antiestafas activa».
2. **Transferencia normal.** Transferir → «escenario 1» → 200 € a Javier: se envía al instante, sin preguntas.
3. **El falso hijo.** En `demo.html` envía **«Falso hijo con número nuevo»**. En el móvil salta la alerta 🔴, se lee en voz alta y Lucía recibe el aviso en `familia.html`. En Inicio aparece «⚠️ Mensaje sospechoso reciente». Carmen intenta pagar al «hijo»: Transferir → «escenario 2», cambia el nombre a «Mi hijo» y envía (sin llamada). Como es una cuenta nueva justo después de un mensaje sospechoso, el Escudo **pausa** la transferencia y pregunta. La transferencia queda en revisión y Lucía la **bloquea** desde `familia.html`: el dinero no sale.
4. **El falso empleado del banco.** Un compañero llama a Carmen y el presentador activa «Llamada activa». Carmen traspasa 8.000 € del ahorro y envía 8.500 € («escenario 3»). El Escudo pregunta y **retiene** la transferencia. En el panel del analista: puntuación, señales, conversación y decisión.
5. **Comprobar a mano.** Protección → «Comprobar un mensaje» → «Grabar» y lee un mensaje en voz alta, o sube una nota de voz o una captura.
6. **Sin falsas alarmas.** Con la llamada activa, «escenario 2» con el casero (600 € de alquiler): una o dos preguntas y se envía.
7. Cierra con la tabla de métricas de `eval/resultados_ia.md`.

## 🛡️ Escudo de llamada (Banco Demo)

Integrado en la pestaña Transferir de Banco Demo, para la estafa del **falso empleado del banco**: alguien llama a la víctima y la guía para que ella misma transfiera su dinero a una «cuenta segura». En esta estafa todo es legítimo (el móvil, la huella y el código son del cliente), así que los sistemas antifraude clásicos no la ven.

**Cómo funciona:** cuando una transferencia parece arriesgada, el banco la pone en pausa y un agente de Claude (`claude-haiku-5-5`) mantiene una conversación corta con el cliente, pensada para romper el guion del estafador, antes de ejecutarla.

- **Embudo:** un motor de reglas puntúa el 100 % de las transferencias (llamada activa, beneficiario nuevo, importe inusual, traspaso previo desde el ahorro, cuenta marcada, IBAN pegado). El agente solo entra a partir de 40 puntos.
- **El LLM no decide solo:** devuelve una evaluación estructurada (tipo de estafa, riesgo, alertas) y una política determinista decide entre **ejecutar**, **retener** o **enviar a un analista**. Cada decisión guarda la regla aplicada y sus motivos.
- **Ante fallo, seguridad:** si el agente no responde o falta la clave, la transferencia arriesgada no se ejecuta y pasa al analista.
- **Privacidad:** no se escuchan las llamadas. Solo se usa la señal «hay una llamada en curso» (en la demo, un interruptor en el panel del presentador).

Pantallas (con el servidor en marcha):
- **http://localhost:8000/** → app de Banco Demo; la transferencia está en la pestaña Transferir (`/llamada/` redirige aquí)
- **http://localhost:8000/llamada/presentador.html** → llamada simulada, reinicio de la demo y aviso si falta la clave
- **http://localhost:8000/llamada/analista.html** → casos con puntuación, señales, conversación y botones Liberar / Bloquear

### Guion de la demo (unos 4 minutos)

1. **Contexto (30 s):** el problema y la solución en una frase.
2. **Escenario 1 (20 s):** 200 € a Javier sin llamada → se envía al instante; el agente no aparece.
3. **Escenario 3 (2 min):** un compañero llama a la «víctima» y la guía. El presentador activa «Llamada activa». La víctima traspasa 8.000 € del ahorro y envía 8.500 € a un IBAN pegado. El Escudo pregunta y **retiene** la transferencia.
4. **Panel del analista (40 s):** puntuación, señales, tipo de estafa, conversación y decisión.
5. **Escenario 2 (20 s):** llamada activa, 600 € al casero → una o dos preguntas y se envía.
6. **Cierre (30 s):** coste (céntimos por intervención, solo en una fracción mínima de transferencias), privacidad y hoja de ruta.

En la pantalla de transferencia hay accesos «Demo: rellenar escenario 1 · 2 · 3».

### Evaluación con el modelo real

```bash
python eval/run_llamada_eval.py --veces 3
```

Repite cada guion varias veces y comprueba que el escenario 3 termina siempre retenido y el 2 ejecutado. Los tests (`backend/tests/test_llamada_*.py`) no necesitan red ni claves.

## Estructura del repositorio

```
backend/app/        API, agente, reglas, herramientas, ElevenLabs, banco simulado
backend/app/llamada/  escudo de llamada: riesgo, agente, política, API del Banco Demo
frontend/js/banco/  app de Banco Demo: Inicio, Transferir, Protección (Centinela) y Perfil
frontend/llamada/   presentador y analista del escudo de llamada
backend/data/       dominios oficiales, campañas conocidas, bancos españoles, ejemplos de demo
backend/tests/      tests (pytest)
frontend/           PWA (index = Banco Demo, familia, demo), service worker, manifest, iconos
eval/               conjunto etiquetado y script de evaluación
docs/               plan de trabajo, pitch y documento de una cara
```

## Limitaciones conocidas y siguientes pasos

- Las apps web no pueden leer WhatsApp ni los SMS automáticamente: en la PWA se usa «Compartir → Centinela», pegar, captura o nota de voz. La siguiente fase es una app Android con `NotificationListenerService` para revisar los mensajes al llegar, con el mismo backend.
- La detección de voz sintética en notas de voz no está implementada todavía: hoy se analiza **lo que dice** el audio, que es la señal más fiable.
- El banco es simulado. En producción, el escudo se integraría con la API del banco (marca blanca dentro de su app).
- El conjunto de evaluación lo hemos escrito nosotros: hay que ampliarlo con mensajes reales de familiares y amigos para medir de verdad.

## Licencia

MIT
