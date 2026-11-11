# 🛡️ Centinela

> **Protección inteligente contra estafas para personas mayores: investiga mensajes sospechosos, alerta a la familia y bloquea fraudes bancarios en tiempo real.**

Proyecto desarrollado en el marco del **HackFinance · Madrid Engineering Week**  
Retos e integraciones técnicas: **GPTadvisor** · **MyInvestor** · **Claude (Anthropic)** · **ElevenLabs**.

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
| 🏦 **Escudo Bancario en Transferencias** | Detección de operaciones bajo coacción o falsos empleados bancarios. Si existe riesgo o llamada en curso, interviene un agente conversacional para romper el guion de la estafa o activar retención preventiva. |

---

## 🛠️ Stack Tecnológico e Integraciones

- **Anthropic Claude (`claude-3-5-sonnet` / `claude-3-5-haiku`):** Agente investigador autónomo con *tool use*, extracción estructurada de entidades sospechosas e intervención socrática en llamadas de riesgo.
- **ElevenLabs:**
  - `Scribe`: Transcripción de audios de mensajería para auditoría de ingeniería social.
  - `TTS Natural`: Lectura asistida de veredictos adaptada a personas mayores.
- **FastAPI (Python 3.11):** Backend asíncrono con arquitectura dirigida por eventos y streaming unidireccional vía Server-Sent Events (SSE).
- **PWA / Frontend:** Interfaz de alto contraste y tipografía escalada (HTML5, Vanilla JS, CSS sin transpilación), con soporte de Web Share Target.
- **Simulación Bancaria (MyInvestor / GPTadvisor):** Reglas deterministas de antifraude, retención cautelar y protocolo de doble factor familiar.

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
- Claves de API de **Anthropic** y **ElevenLabs** *(opcionales: el sistema cuenta con motor determinista de respaldo sin dependencias externas)*.

### Arranque Rápido
- **En macOS:** Doble clic en `iniciar.command` (si Gatekeeper lo bloquea: clic derecho → *Abrir*).
- **En Windows:** Doble clic en `iniciar.bat`.

### Instalación Manual

1. Clonar el repositorio y acceder a la carpeta raíz:
   ```bash
   git clone <URL_DEL_REPOSITORIO> centinela
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

4. Configurar variables de entorno:
   ```bash
   cp .env.example .env
   ```

---

## ⚙️ Variables de Entorno (`.env`)

| Variable | Propósito | Requerido |
|---|---|:---:|
| `ANTHROPIC_API_KEY` | Habilita el agente investigador y el escudo conversacional | No (modo reglas) |
| `CLAUDE_MODEL` | Modelo asignado al agente (def: `claude-3-5-sonnet-latest`) | No |
| `ELEVENLABS_API_KEY` | Transcripción de audios y lectura de alertas con voz natural | No (voz nativa) |
| `ELEVENLABS_VOICE_ID` | Identificador de voz para los avisos en ElevenLabs | No |
| `GOOGLE_SAFE_BROWSING_KEY` | Comprobación de URLs sospechosas contra Google Safe Browsing | No |
| `TELEGRAM_BOT_TOKEN` | Token para envío de notificaciones directas al tutor familiar | No |
| `TELEGRAM_CHAT_ID` | Identificador de chat en Telegram | No |
| `SHIELD_MINUTES` | Duración del bloqueo preventivo tras alerta roja (def: `60`) | No |
| `SHIELD_AMOUNT_THRESHOLD` | Umbral en euros para activación de retención (def: `300`) | No |

---

## 🖥️ Enlaces de Interfaz

Con el backend en ejecución (`uvicorn app.main:app --host 0.0.0.0 --port 8000` dentro de `backend/`):

- **App Principal (Senior / Banco):** `http://localhost:8000/`
- **Panel Familiar:** `http://localhost:8000/familia.html`
- **Panel de Simulación de Escenarios:** `http://localhost:8000/demo.html`
- **Consola del Analista de Fraude:** `http://localhost:8000/llamada/analista.html`
- **Documentación Swagger OpenAPI:** `http://localhost:8000/docs`

---

## 🧪 Pruebas y Benchmark

```bash
# Ejecutar tests unitarios automáticos (sin conexión externa ni claves)
cd backend && python -m pytest -q

# Ejecutar benchmark sobre dataset de 74 casos etiquetados (40 fraudes, 34 benignos)
cd .. && python eval/run_eval.py --modo reglas    # Modo determinista (gratuito)
python eval/run_eval.py --modo ia                 # Modo agente completo con Claude
```

Los resultados con métricas de *precision*, *recall*, falsos positivos y latencia se almacenan en `eval/resultados_<modo>.md`.

---

## 🗺️ Trabajo Futuro

- [ ] **Cliente nativo Android:** Implementación de `NotificationListenerService` para inspección en segundo plano de SMS y WhatsApp sin intervención manual.
- [ ] **Detección acústica de voz clonada:** Filtro preventivo de huella de deepfake previo al análisis lingüístico del audio.
- [ ] **Integración bancaria PSD2:** Conexión directa con APIs de banca abierta para retención real de transferencias.

---

## 👥 Equipo

Desarrollado para el **HackFinance · Madrid Engineering Week**.

- Jorge — [GitHub](https://github.com/) / [LinkedIn](https://linkedin.com/)
- Colaborador 2 — [GitHub](https://github.com/) / [LinkedIn](https://linkedin.com/)
- Colaborador 3 — [GitHub](https://github.com/) / [LinkedIn](https://linkedin.com/)

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más información.