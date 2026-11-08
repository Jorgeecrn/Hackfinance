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
 PWA (HTML/JS, sin build)                    Panel familia      Banco simulado     Control demo
 index.html · Ajustes · bandeja · alertas    familia.html       banco.html         demo.html
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
- **http://localhost:8000/** → app de la persona mayor (ábrela en el móvil o en modo móvil del navegador)
- **http://localhost:8000/familia.html** → panel del familiar
- **http://localhost:8000/banco.html** → banco simulado con el escudo
- **http://localhost:8000/demo.html** → panel del presentador para enviar mensajes simulados
- **http://localhost:8000/docs** → documentación interactiva de la API

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

## Guion de la demo (3 minutos)

1. Abre `demo.html` en el portátil y la app (`/`) en un móvil. Pulsa en la pantalla del móvil una vez para permitir el sonido.
2. Envía **«Falso MyInvestor: cuenta bloqueada»**. En el móvil aparece la alerta 🔴, la investigación (enlace que imita a MyInvestor) y el aviso hablado.
3. Envía **«Falso hijo con número nuevo»**. Alerta 🔴, aviso a Lucía (panel de familia) y escudo bancario activado.
4. En `banco.html` pulsa «Preset: pagar al hijo» → la operación queda **retenida**. En `familia.html` Lucía la **cancela**: el dinero no sale.
5. Envía **«Lucía de verdad»** y **«Código real de verificación»** → 🟢: no hay falsas alarmas.
6. En el móvil: «Comprobar un mensaje» → «Grabar» y lee un mensaje en voz alta, o sube una nota de voz.
7. Cierra con la tabla de métricas de `eval/resultados_ia.md`.

## Estructura del repositorio

```
backend/app/        API, agente, reglas, herramientas, ElevenLabs, banco simulado
backend/data/       dominios oficiales, campañas conocidas, bancos españoles, ejemplos de demo
backend/tests/      tests (pytest)
frontend/           PWA (index, familia, banco, demo), service worker, manifest, iconos
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
