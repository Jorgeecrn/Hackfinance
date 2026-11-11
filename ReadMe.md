# 🛡️ Centinela

> **Protección inteligente contra estafas para personas mayores: investiga mensajes sospechosos, alerta a la familia y bloquea fraudes bancarios en tiempo real.**

Proyecto desarrollado en el marco del **HackFinance · Madrid Engineering Week**  
Retos e integraciones técnicas: **GPTadvisor** · **MyInvestor** · **Claude (Anthropic)** · **ElevenLabs**.

**Perfil de entrega.** Banco Demo simula mensajes, llamadas y transferencias con datos ficticios. La demo local usa reglas deterministas, revisión humana y voz del sistema si hay una voz española local. Claude, ElevenLabs, Telegram, RDAP y Safe Browsing están apagados.

---

## 📌 El Problema

- **Fraudes dirigidos de alta frecuencia:** Campañas continuas como el timo del «hijo en apuros» vía WhatsApp o SMS con suplantación de entidades bancarias, Correos y la DGT dirigidas contra personas mayores.
- **Evolución con IA generativa:** Uso incipiente de notas de voz clonadas mediante IA, anulando los filtros habituales de sospecha en el receptor.
- **Defensas desconectadas:** Las soluciones estándar (filtros antispam de operadoras o SMS nativos) no son transversales, no aportan contexto pedagógico y no involucran de forma proactiva al entorno familiar ni al banco.

---

## 💡 Nuestra Solución

Centinela actúa como una capa de protección activa en formato PWA (Progressive Web App) conectada con la operatoria bancaria:

| Módulo | Funcionalidad |
|---|---|
| 🔍 **Agente Investigador Multimodal** | Claude analiza enlaces (antigüedad de dominio, RDAP, Safe Browsing), números de teléfono e IBANs contrastándolos con campañas conocidas. |
| 🎙️ **Análisis de Voz y Accesibilidad** | Transcribe audios entrantes vía **ElevenLabs Scribe** y reproduce el veredicto con síntesis de voz natural y empática para usuarios senior. |
| 🧾 **Dictámenes con Pruebas** | Veredictos basados en evidencias explícitas (🟢 / 🟡 / 🔴) en lugar de índices de probabilidad ambiguos. |
| 👪 **Consola de Supervisión Familiar** | Alertas en tiempo real a familiares designados (panel web y bot de Telegram) con facultad de autorizar o pausar transferencias retenidas. |
| 🏦 **Escudo Bancario en Transferencias** | El servidor combina señales de riesgo. Los pagos a cuentas marcadas y los pagos a destinatarios nuevos con una alerta roja activa exigen revisión humana, con cualquier importe. El agente conversacional es opcional. |

---

## 🛠️ Stack Tecnológico e Integraciones

- **Anthropic Claude (modelo configurable):** Agente investigador autónomo con *tool use*, extracción estructurada de entidades sospechosas e intervención socrática en llamadas de riesgo.
- **ElevenLabs:**
  - `Scribe`: Transcripción de audios de mensajería para auditoría de ingeniería social.
  - `TTS Natural`: Lectura asistida de veredictos adaptada a personas mayores.
- **FastAPI (Python 3.11):** Backend asíncrono con arquitectura dirigida por eventos y streaming unidireccional vía Server-Sent Events (SSE).
- **PWA / Frontend:** Interfaz de alto contraste y tipografía escalada (HTML5, Vanilla JS, CSS sin transpilación), con soporte de Web Share Target.
- **Simulación Bancaria (MyInvestor / GPTadvisor):** Reglas deterministas de antifraude, retención cautelar y revisión desde los paneles de familia y analista.

---

## 🏗️ Arquitectura del Sistema

```
 App Banco / Senior (PWA)          Panel Familia               Consola Analista
 (Transferencias / Alertas)         (Supervisión)             (Resolución casos)
         │                                │                            │
         ▼ (SSE / REST)                   ▼ (SSE)                      ▼ (SSE)
 ─────────────────────────────────────────────────────────────────────────────────
                                FastAPI Backend
 ─────────────────────────────────────────────────────────────────────────────────
   ├── analyzer.py       Orquestador: audio → texto → reglas → agente → veredicto
   ├── elevenlabs.py     Integración Scribe (STT) y TTS de alta fidelidad
   ├── rules.py          Prefiltro determinista de señales rápidas (<50 ms)
   ├── agent.py          Agente Claude con tool use y salida JSON estructurada
   │     └── tools.py    Consultas RDAP, análisis IBAN, verificación de contactos
   ├── llamada/          Motor de riesgo para transferencias bajo llamada activa
   └── bank.py           Gestor del escudo bancario: retención, aprobación y anulación
```

---

## 🚀 Puesta en Marcha

### Requisitos previos
- Python 3.11 o superior.
- Entorno Python preparado con las dependencias de `requirements.txt`. La demo usa el modo local sin claves de API.

### Arranque Rápido

Una vez preparado el entorno, abre el lanzador correspondiente. El lanzador no instala dependencias.
- **En macOS:** Doble clic en `iniciar.command` (si Gatekeeper lo bloquea: clic derecho → *Abrir*).
- **En Windows:** Doble clic en `iniciar.bat`.

### Instalación Manual

1. Clonar el repositorio y acceder a la carpeta raíz:
   ```bash
   git clone https://github.com/Jorgeecrn/Hackfinance.git centinela
   cd centinela
   ```

2. Crear y activar el entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate       # En Windows: .venv\Scripts\activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Arrancar desde la raíz:
   ```bash
   python iniciar_demo.py
   ```

Si el puerto 8000 está ocupado por otro proceso, indica `--puerto 8001`. Usa la misma dirección local en todas las pestañas.

---

## ⚙️ Variables de Entorno (`.env`)

Los lanzadores fuerzan `CENTINELA_DEMO_LOCAL=1`, `FORCE_OFFLINE=1`, `ONLINE_CHECKS=0` y `ADMIN_REMOTO=0`. El perfil de entrega prevalece sobre un `.env` previo. Las claves de esta tabla corresponden a un futuro ensayo autorizado del perfil configurable.

| Variable | Propósito | Requerido |
|---|---|:---:|
| `ANTHROPIC_API_KEY` | Habilita el agente investigador y el escudo conversacional | No (modo reglas) |
| `CLAUDE_MODEL` | Modelo asignado al agente (valor en `backend/app/config.py`) | No |
| `ELEVENLABS_API_KEY` | Transcripción de audios y lectura de alertas con voz natural | No (voz nativa) |
| `ELEVENLABS_VOICE_ID` | Identificador de voz para los avisos en ElevenLabs | No |
| `GOOGLE_SAFE_BROWSING_KEY` | Comprobación de URLs sospechosas contra Google Safe Browsing | No |
| `TELEGRAM_BOT_TOKEN` | Token para envío de notificaciones directas al tutor familiar | No |
| `TELEGRAM_CHAT_ID` | Identificador de chat en Telegram | No |
| `SHIELD_MINUTES` | Duración del bloqueo preventivo tras alerta roja (def: `60`) | No |
| `SHIELD_AMOUNT_THRESHOLD` | Umbral de la API bancaria anterior. Banco Demo revisa cualquier importe si hay alerta activa y destinatario nuevo | No |

---

## 🖥️ Enlaces de Interfaz

El lanzador escucha en `127.0.0.1` y abre Banco Demo. Usa el mismo portátil para la demo. Puedes mostrar la app a tamaño móvil con las herramientas del navegador.

- **App Principal (Senior / Banco):** `http://127.0.0.1:8000/`
- **Panel Familiar:** `http://127.0.0.1:8000/familia.html`
- **Panel de Simulación de Escenarios:** `http://127.0.0.1:8000/demo.html`
- **Consola del Analista de Fraude:** `http://127.0.0.1:8000/llamada/analista.html`
- **Presentador de llamada simulada:** `http://127.0.0.1:8000/llamada/presentador.html`
- **Esquema de la API:** `http://127.0.0.1:8000/openapi.json`

El perfil local valida el host y el origen de las escrituras. Las rutas privadas y los canales SSE rechazan acceso remoto. Los eventos de familia anuncian el cambio con datos mínimos y el panel consulta el detalle por la API.



## 🧪 Pruebas y Benchmark

```bash
# Ejecutar tests unitarios automáticos (sin conexión externa ni claves)
cd backend && python -m pytest -q

# Ejecutar las reglas sobre 74 casos de desarrollo (40 fraudes, 34 legítimos)
cd .. && python eval/run_eval.py --modo reglas    # Modo determinista (gratuito)
# El modo ia requiere un perfil configurable y autorización de gasto.
```

Los resultados se guardan en `eval/resultados_<modo>.md`. Son métricas del banco de desarrollo. Para una evaluación independiente se necesita otro conjunto con etiquetas revisadas. Las reglas se han afinado viendo este mismo conjunto (por ejemplo, el caso 13, un falso cargo con teléfono, se detecta desde una regla añadida tras verlo), así que el resultado no es una medida independiente.

---

## 🗺️ Trabajo Futuro

- [ ] **Cliente nativo Android:** Implementación de `NotificationListenerService` para inspección en segundo plano de SMS y WhatsApp sin intervención manual.
- [ ] **Detección acústica de voz clonada:** Filtro preventivo de huella de deepfake previo al análisis lingüístico del audio.
- [ ] **Integración bancaria PSD2:** Conexión directa con APIs de banca abierta para retención real de transferencias.

---

## 👥 Equipo

Desarrollado para el **HackFinance · Madrid Engineering Week**.

- Diego Almajano 
- Alejandro Bolivar 
- Jorge Carnerero
- Jonathan Flores
- Álvaro Moran

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más información.
