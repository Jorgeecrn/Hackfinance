# App de banco unificada — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir la demo en la app normal de Banco Demo con Centinela dentro como extensión: un solo banco, una sola Carmen, y el escudo por mensaje convertido en una señal más del motor de riesgo.

**Architecture:** El backend del escudo de llamada (`backend/app/llamada/`) pasa a ser el único banco. Añade la señal `alerta_estafa_reciente`, que sale del escudo de Centinela, y el campo `actor` en las decisiones; publica el evento `caso` en el bus existente. El frontend en `/` es una app de banco de 4 pestañas hecha con módulos ES (`js/banco/*`), que reutiliza la lógica de `js/app.js` (Centinela) y de `js/llamada/cliente.js`. El panel de familia pasa a usar los casos de Banco Demo.

**Tech Stack:** FastAPI, Pydantic 2, pytest; HTML/CSS/JS sin build (módulos ES), `js/common.js`, `styles.css`.

**Spec:** `docs/superpowers/specs/2026-11-10-app-banco-unificada-design.md`

## Global Constraints

- Rama `experimento`. Commits en español, terminados con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No modificar `backend/app/{bank,analyzer,agent,rules,tools,state,events,config}.py`. Los endpoints `/api/banco/*` deben responder igual. Los 87 tests actuales deben seguir pasando.
- Banco: **Banco Demo**. Clienta: **Carmen López**. Beneficiaria nueva: **Lucía López, `ES9121000418450200051332`**.
- Señal `alerta_estafa_reciente`, peso **25**. Su detalle sigue el formato `"Hace {n} min recibió un mensaje con señales de estafa: {motivo}"`.
- Puntuaciones que deben salir:

  | Caso | Puntos |
  |---|---|
  | Alerta + beneficiario nuevo | 45 |
  | Alerta + Lucía o Javier | 25 |
  | Llamada + alerta + beneficiario nuevo | 80 |
  | Escenarios 1 / 2 / 3 sin alerta | 0 / 55 / 100 |

- Decisión: campo `actor: "analista" | "familia"` (por defecto `"analista"`), que se guarda en `analystDecision.actor`. Evento SSE `caso` en el canal `familia`.
- App en `/`, con las pestañas **Inicio · Transferir · Protección · Perfil**.
  - Bizum, Tarjetas, Notificaciones y Seguridad son decorativos y muestran el toast `"Próximamente"`.
  - La etiqueta de Protección es `"con tecnología Centinela"`.
  - La nota de la bandeja es `"requiere permiso de notificaciones (Android)"`.
  - Banner de Inicio, por prioridad:
    1. `"📞 Llamada en curso"`
    2. `"⚠️ Mensaje sospechoso reciente: los pagos a cuentas nuevas se revisarán"`
    3. `"🛡️ Protección antiestafas activa"`
- **Herramientas de demo** (al final de Perfil):
  - enlaces a `/llamada/presentador.html`, `/llamada/analista.html`, `/familia.html`, `/demo.html` y `/docs`;
  - botón «Reiniciar toda la demo», que hace `POST /api/demo/reset` + `POST /api/llamada/demo/reset`.
- Estilo de banco moderno y legible: `data-letra="normal"` fijo, sin la escala «grande». Todo texto dinámico se pinta con `el()` o `textContent`; nunca `innerHTML` con datos.
- Caché del service worker: `centinela-v3`.

## Review Focus

1. **Service worker:** el service worker que tiene instalado alguien que ya abrió la app antigua no debe servir archivos borrados (`js/app.js`, `banco.html`). Hay que subir la versión de caché y que la lista SHELL solo contenga archivos existentes. *(Task 4: `test_sw_shell_files_exist`)*
2. **Escudo caducado:** si la alerta tiene más de 60 min (el escudo ya caducó), la señal no se activa. *(Task 2: `test_expired_shield_no_signal`)*
3. **`state.json` ilegible:** si el estado de Centinela está ilegible o falla al leerse, la transferencia sigue su curso sin la señal; no da un 500. *(Task 2: `test_centinela_state_failure_ignored`)*
4. **Doble decisión:** si el familiar y el analista deciden el mismo caso, la segunda decisión da 409 y el dinero sale como mucho una vez. *(Task 3: `test_family_after_analyst_conflicts`)*
5. **Compartir desde WhatsApp:** «Compartir → Banco Demo» (`/share-target` → `/?compartido=id`) debe llevar a Protección y analizar lo compartido. *(Task 6, paso de verificación por HTTP + navegador)*

---

## File Structure

```
backend/app/llamada/seed.py        + Lucía en beneficiaries
backend/app/llamada/risk.py        + WEIGHTS["alerta_estafa_reciente"]=25, parámetro recent_alert
backend/app/llamada/service.py     + _centinela_alert(now), actor, bus.publish("familia","caso",...)
backend/app/llamada/router.py      + DecisionIn.actor
backend/tests/test_llamada_risk.py · test_llamada_api.py · test_frontend_static.py (nuevo)
frontend/index.html                app de banco (reescrito)
frontend/banco.css                 estilos de la app de banco (nuevo)
frontend/js/banco/core.js          estado compartido, navegación, refresco (nuevo)
frontend/js/banco/app.js           entrada: init de módulos, SSE, sondeo, SW (nuevo)
frontend/js/banco/inicio.js        Inicio + traspaso (nuevo)
frontend/js/banco/transferir.js    trasladado de js/llamada/cliente.js (nuevo)
frontend/js/banco/proteccion.js    trasladado de js/app.js (nuevo)
frontend/js/banco/perfil.js        Perfil + herramientas de demo (nuevo)
frontend/familia.html, js/familia.js   casos de Banco Demo
frontend/llamada/index.html        redirección a /
frontend/llamada/presentador.html  enlace App → /
frontend/demo.html                 quitar enlace Banco
frontend/sw.js                     SHELL nuevo, centinela-v3
BORRAR: frontend/banco.html, js/banco.js, js/app.js, js/llamada/cliente.js
README.md                          guion unificado
```

---

### Task 1: Lucía beneficiaria y señal `alerta_estafa_reciente` (pura)

**Files:** Modify `backend/app/llamada/seed.py`, `backend/app/llamada/risk.py`. Test: `backend/tests/test_llamada_risk.py`.

**Interfaces:**
- Produces:
  - `seed.LUCIA_IBAN = "ES9121000418450200051332"`. `SEED["beneficiaries"]` pasa a ser `[Javier, {"name": "Lucía López", "iban": LUCIA_IBAN}]`.
  - `WEIGHTS["alerta_estafa_reciente"] = 25`, insertado **después** de `cuenta_destino_marcada` y antes de `iban_pegado`.
  - `evaluate_risk(..., now, recent_alert: str | None = None)`: si `recent_alert` es una cadena no vacía, se activa la señal con `detail = recent_alert`. El servicio construye la frase completa.

- [ ] **Step 1: Tests**
  - Actualiza `test_weights_match_spec` para que incluya `"alerta_estafa_reciente": 25`.
  - `test_recent_alert_signal_weight_and_detail`: `ctx(recent_alert="Hace 5 min recibió un mensaje con señales de estafa: falso hijo")` → `ids == ["alerta_estafa_reciente"]`, `score == 25` y el `detail` es exactamente esa cadena.
  - `test_alert_plus_new_beneficiary_is_45`: casero + `recent_alert` → `45`.
  - `test_alert_plus_call_plus_new_is_80`: llamada + casero (600 €) + alerta → `80`.
  - `test_lucia_is_known_beneficiary`: `iban=seed.LUCIA_IBAN` → sin `beneficiario_nuevo`.
  - Los tests de los escenarios 0 / 55 / 100 existentes siguen igual, sin pasar `recent_alert`.
- [ ] **Step 2:** `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_llamada_risk.py -q` → FAIL.
- [ ] **Step 3:** Implementa los cambios en `seed.py` y `risk.py`.
- [ ] **Step 4:** Ejecuta la suite completa (`pytest -q`) → todo PASS. Revisa si algún test de API dependía de que Lucía fuera beneficiaria nueva (no debería).
- [ ] **Step 5:** Commit `feat(llamada): Lucía como beneficiaria y señal de alerta reciente por mensaje`.

---

### Task 2: El servicio lee el escudo de Centinela

**Files:** Modify `backend/app/llamada/service.py`. Test: `backend/tests/test_llamada_api.py`.

**Interfaces:**
- Consumes: `app.state.load()`, `app.bank.shield_active(bank: dict) -> bool`, `app.config.settings.shield_minutes`. El escudo tiene la forma `state["banco"]["escudo"] = {"activo_hasta": iso | None, "motivo": str | None, ...}`.
- Produces: `_centinela_alert(now: datetime) -> str | None` en `service.py`.
  - Si el escudo está activo: `minutes = max(0, round(settings.shield_minutes - (activo_hasta - now)/60s))` y devuelve `f"Hace {minutes} min recibió un mensaje con señales de estafa: {motivo}"`.
  - Si no está activo, devuelve `None`.
  - Cualquier excepción → `log.warning` y `None`.
  - `request_transfer` lo llama **antes** de `store.mutate` (para no anidar el lock de Centinela dentro del de Banco Demo) y lo pasa como `recent_alert`.

- [ ] **Step 1: Tests**, con el `fake_agent` existente. Para crear la alerta se usa el flujo real de Centinela, en modo offline por reglas: `client.post("/api/analizar", data={"texto": "Hola mamá, se me ha roto el móvil, este es mi número nuevo. Necesito un bizum de 600€ urgente", "remitente": "+34711234567"})`, que activa el escudo.
  - `test_sms_alert_then_new_beneficiary_goes_to_agent`: alerta → `transfer("casero")` **sin llamada** → `on_hold`; el caso tiene `score == 45` y la señal `alerta_estafa_reciente`, cuyo detalle empieza por `"Hace "` y contiene `"recibió un mensaje con señales de estafa"`.
  - `test_sms_alert_then_pay_lucia_executes`: alerta → transferencia de 25 € a Lucía (`seed.LUCIA_IBAN`) → `executed`.
  - `test_alert_ignored_when_shield_disabled`: `client.put("/api/perfil", json={"escudo_bancario": False})` + el mismo SMS → `transfer("casero")` → `executed` y sin caso.
  - `test_expired_shield_no_signal`: alerta y después `monkeypatch` de `app.bank._now` a +61 min → `transfer("casero")` → `executed`.
  - `test_centinela_state_failure_ignored`: `monkeypatch` de `app.state.load` para que lance `RuntimeError` → `transfer("normal")` → 200 `executed`.
  - `test_reset_both_demos_clears_alert`: alerta → `POST /api/demo/reset` → `transfer("casero")` → `executed`.
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3:** Implementa `_centinela_alert` y conéctalo en `request_transfer`. Importa `from .. import bank as centinela_bank, state as centinela_state` y llama a `centinela_state.load` a través del módulo, para que el `monkeypatch` funcione.
- [ ] **Step 4:** `pytest -q` (la suite completa) → PASS.
- [ ] **Step 5:** Commit `feat(llamada): el escudo por mensaje de Centinela es una señal del banco`.

---

### Task 3: El familiar decide y recibe los casos en tiempo real

**Files:** Modify `backend/app/llamada/service.py`, `backend/app/llamada/router.py`. Test: `backend/tests/test_llamada_api.py`.

**Interfaces:**
- Produces:
  - `DecisionIn.actor: Literal["analista", "familia"] = "analista"`.
  - `service.analyst_decision(case_id, decision, actor="analista")` guarda `c["analystDecision"] = {"decision", "actor", "ts"}`.
  - `_publish_case(case: dict) -> None`: hace `events.bus.publish("familia", "caso", <copia del caso>)`. Se llama al **salir** de `store.mutate` cuando un caso pasa a `retenida` o `pendiente` (en `request_transfer` y `reply`) y cuando el analista o el familiar lo resuelven.

- [ ] **Step 1: Tests**
  - `test_family_can_block_case`: caso retenido (con `open_estafa_case`) → `POST decision {"decision": "block", "actor": "familia"}` → `bloqueada` y `analystDecision.actor == "familia"`.
  - `test_default_actor_is_analista`: tras un `release` sin `actor` → `actor == "analista"`.
  - `test_invalid_actor_rejected`: `actor: "otro"` → 422.
  - `test_family_after_analyst_conflicts`: el analista bloquea → el familiar libera → 409; el saldo no cambia.
  - `test_case_event_published_to_family`: `q = bus.subscribe("familia")`; caso retenido → `q.get_nowait()` tiene `{"evento": "caso", "datos": {"status": "retenida", ...}}`. Al final, `bus.unsubscribe`.
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3:** Implementa `actor` y `_publish_case`.
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Commit `feat(llamada): el familiar libera o bloquea casos y recibe avisos en directo`.

---

### Task 4: Estructura de la app, Inicio y Perfil

**Files:**
- Create: `frontend/banco.css`, `frontend/js/banco/core.js`, `app.js`, `inicio.js`, `perfil.js`, `backend/tests/test_frontend_static.py`.
- Rewrite: `frontend/index.html`.
- Modify: `frontend/sw.js`, `frontend/demo.html`.
- Delete: `frontend/banco.html`, `frontend/js/banco.js`.

**Interfaces** (`core.js`):
- `export const store = { state: null, profile: null, bank: null, health: null }`.
  - `state` viene de `/api/llamada/state`, `profile` de `/api/perfil`, `bank` de `/api/banco` (solo para `escudo`) y `health` de `/api/health`.
- `export async function refresh(): Promise<void>`: carga `state`, `profile` y `bank` en paralelo. Si una falla, conserva el valor anterior y lo registra con `console.warn`. Después llama a los listeners.
- `export function onRefresh(fn: (store) => void): void`.
- `export function goTab(name: "inicio" | "transferir" | "proteccion" | "perfil"): void`: muestra `#tab-<name>`, marca el botón `[data-tab=<name>]` con `aria-current="page"` y hace scroll arriba.
- `export function showScreen(tab: string, screenId: string): void`: dentro de `#tab-<tab>`, muestra solo `[data-screen=<screenId>]`.
- `export const BASE = "/api/llamada"`.
- `inicio.js`: `export function initInicio()`. `perfil.js`: `export function initPerfil()`.
- `app.js` (entrada, `<script type="module">`):
  - `unlockAudioOnFirstTouch()`;
  - `health`;
  - `initInicio()`, `initTransferir()`, `initProteccion()`, `initPerfil()` (las dos centrales llegan en las Tasks 5 y 6; hasta entonces, importaciones comentadas);
  - `refresh()` y `setInterval(refresh, 2000)`;
  - `subscribe("usuario", {...})` (los handlers se completan en la Task 6; aquí `reset: () => location.reload()`, y `escudo`/`perfil` → `refresh`);
  - registro de `/sw.js`.

- [ ] **Step 1: Test** `backend/tests/test_frontend_static.py`:
  - `test_sw_shell_files_exist`: lee `frontend/sw.js`, extrae con una regex las rutas de la lista `SHELL`, convierte `"/"` en `index.html` y comprueba que cada archivo existe en `FRONTEND_DIR`. Comprueba también que contiene `centinela-v3`.
  - `test_index_is_bank_app`: `GET /` con `TestClient` contiene `"Banco Demo"` y `js/banco/app.js`, y **no** contiene `js/app.js"`.
  - `test_removed_pages_gone`: `GET /banco.html` → 404.
- [ ] **Step 2:** `pytest tests/test_frontend_static.py -q` → FAIL.
- [ ] **Step 3: Implementa.**
  - **`index.html`:**
    - cabecera con el logo «Banco Demo»;
    - 4 secciones `#tab-*` con sus `[data-screen]`;
    - barra inferior fija con 4 `button[data-tab]` (iconos `bank`, `send`, `shield`, `user`);
    - contenedor `#overlay` para la alerta a pantalla completa (se rellena en la Task 6);
    - `manifest` y `theme-color`.
  - **`inicio.js`:**
    - saludo «Hola, Carmen» (con `state.client.name`) y tarjeta de saldo de la corriente con el ahorro debajo;
    - accesos rápidos: Transferir → `goTab("transferir")`, Traspaso → pantalla de traspaso (lógica de traspaso de `js/llamada/cliente.js`), Bizum y Tarjetas → `toast("Próximamente")`;
    - 8 movimientos;
    - banner según la prioridad de Global Constraints. «Mensaje sospechoso» = `bank.escudo.activo`; «Protección activa» = `profile.proteccion_activa`.
  - **`perfil.js`:**
    - nombre, IBAN de la corriente y filas decorativas con toast;
    - tema (`getTheme`/`setTheme`);
    - fila «Herramientas de demo» → pantalla con los 5 enlaces (`target="_blank"`) y «Reiniciar toda la demo». Este botón, tras los 2 POST, hace `toast` y `location.reload()`.
  - **`banco.css`:** estilos con prefijo `bk-` (no hay que reutilizar `.phone`). Ancho máximo de 430 px centrado en escritorio y ancho completo en móvil. Padding inferior suficiente para la barra de navegación.
  - **`sw.js`:** `CACHE = "centinela-v3"` y la lista SHELL con `"/"`, `"/index.html"`, `"/styles.css"`, `"/banco.css"`, `"/manifest.webmanifest"`, `"/js/common.js"`, `"/js/banco/core.js"`, `"/js/banco/app.js"`, `"/js/banco/inicio.js"`, `"/js/banco/perfil.js"`, `"/icons.svg"` y los dos iconos. `transferir.js` y `proteccion.js` se añaden a SHELL en las Tasks 5 y 6.
  - **`demo.html`:** quita el enlace «Banco».
  - Borra `banco.html` y `js/banco.js`. Con `grep -rn "banco.html" frontend backend README.md`, actualiza o quita cada referencia que quede.
- [ ] **Step 4:** `pytest -q` → PASS. Verificación por HTTP con el servidor en el puerto 8765: `/`, `/banco.css` y `/js/banco/*.js` → 200; `/banco.html` → 404.
- [ ] **Step 5:** Commit `feat(app): estructura de la app de Banco Demo con Inicio y Perfil`.

---

### Task 5: Pestaña Transferir

**Files:**
- Create: `frontend/js/banco/transferir.js`.
- Modify: `frontend/index.html` (marcado de `#tab-transferir`), `frontend/llamada/index.html` (redirección), `frontend/llamada/presentador.html` (enlace), `frontend/sw.js` (si hace falta).
- Delete: `frontend/js/llamada/cliente.js`.

**Interfaces:**
- Consumes: `store`, `refresh`, `showScreen`, `goTab` y `BASE` de `core.js`.
- Produces: `export function initTransferir()`.
- Pantallas de `#tab-transferir`: `form`, `chat`, `result`. Mismos `PRESETS` 1 · 2 · 3 que hoy, sin añadir ninguno.
- En `sw.js`, añade `"/js/banco/transferir.js"` a SHELL.

- [ ] **Step 1: Test** en `test_frontend_static.py`:
  - `test_llamada_redirects_to_app`: `GET /llamada/` contiene `location.replace("/")` y `<meta http-equiv="refresh" content="0; url=/">`.
  - `test_presenter_links_app_root`: `GET /llamada/presentador.html` contiene `href="/"` y **no** `href="/llamada/"`.
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3: Implementa.**
  - Traslada la lógica de transferencia, chat y resultado de `js/llamada/cliente.js` a `transferir.js`, sin cambiar el comportamiento: detección de `paste`, presets 1 · 2 · 3, «Escribiendo…», «Salir», vuelta al formulario ante un error en la respuesta y `callActive` desde `store.state`.
  - «Volver al inicio» llama a `goTab("inicio")`.
  - Activa `initTransferir()` en `app.js`.
  - Reescribe `llamada/index.html` como una redirección mínima.
  - Borra `js/llamada/cliente.js`.
- [ ] **Step 4:** `pytest -q` → PASS. Verificación por HTTP: transferencia del escenario 1 vía API → `executed`.
- [ ] **Step 5:** Commit `feat(app): pestaña Transferir con el escudo de llamada`.

---

### Task 6: Pestaña Protección (Centinela dentro del banco)

**Files:**
- Create: `frontend/js/banco/proteccion.js`.
- Modify: `frontend/index.html` (marcado de `#tab-proteccion` y `#overlay`), `frontend/js/banco/app.js` (handlers SSE), `frontend/banco.css`.
- Delete: `frontend/js/app.js`. Añade `"/js/banco/proteccion.js"` a SHELL en `sw.js`.

**Interfaces:**
- Consumes: `store`, `refresh`, `showScreen` y `goTab` de `core.js`; `api`, `streamAnalysis`, `speak`, `stopSpeaking`, `LEVEL`, `CHANNEL`, `fmtTime`, `fmtShort`, `el`, `icon` y `initials` de `common.js`.
- Produces:
  - `export function initProteccion()`;
  - `export function onIncomingMessage(m: dict)`, que sustituye a `onIncoming` de `js/app.js`;
  - `export async function handleShared()`: el mismo cuerpo que en `js/app.js`, más `goTab("proteccion")` antes de analizar;
  - `export function onShieldEvent()`, que llama a `refresh` y repinta el estado del escudo.
- Pantallas de `#tab-proteccion`: `main`, `check`, `progress`, `result`, `contacts`.

- [ ] **Step 1: Test** en `test_frontend_static.py`:
  - `test_app_has_protection_copy`: `GET /` contiene `"con tecnología Centinela"` y `"requiere permiso de notificaciones (Android)"`.
  - `test_share_target_redirects_to_app`: `POST /share-target` con `data={"text": "hola"}` y `follow_redirects=False` → 303 con `location` que empieza por `/?compartido=`.
- [ ] **Step 2:** Ejecuta los tests → FAIL en el primero. El segundo ya debería pasar; es un test que fija el comportamiento existente.
- [ ] **Step 3: Implementa** trasladando de `js/app.js` las funciones:
  - `resetCheck`, `toggleRecording`, `addStep`, `runAnalysis`, `verdictCard`, `renderResult`, `showOverlay`, `hideOverlay`, `processQueue`, `loadInbox`, `renderStats`, `renderInboxItem`, `openMessage`, `fillSettings`, `renderContacts` y el guardado de ajustes y contactos, y `handleShared`;
  - con su mismo comportamiento y los ids adaptados al nuevo marcado.

  Además:
  - **Pantalla `main`:**
    - estado (interruptor `proteccion_activa`; si `store.bank.escudo.activo`, cuenta atrás hasta `activo_hasta` y `motivo`);
    - botón «Comprobar un mensaje»;
    - bandeja «Mensajes vigilados» con la nota de Android;
    - fila «Contactos de confianza y avisos» → pantalla `contacts`, con el familiar, la lista de contactos y los interruptores `leer_en_voz_alta` y `escudo_bancario` («Frenar pagos a cuentas nuevas tras un mensaje sospechoso»).
  - Se elimina el ajuste de tamaño de letra: `tamano_letra` deja de usarse en esta app.
  - Si `store.health.ia === false`, se muestra el aviso de modo básico.
  - En `app.js`, `subscribe("usuario")` queda así:
    - `mensaje: onIncomingMessage`;
    - `perfil` → `refresh`;
    - `escudo: onShieldEvent`;
    - `transferencia_retenida` se ignora (es del banco antiguo);
    - `reset` → `location.reload()`.

    Y después de `init`, `handleShared()`.
  - Borra `js/app.js`.
- [ ] **Step 4:** `pytest -q` → PASS. Verificación por HTTP con el servidor:
  - `POST /api/demo/entrante` con el SMS del falso hijo → `GET /api/mensajes` lo contiene;
  - `POST /api/analizar` con ese texto → `rojo`, y `GET /api/banco` → `escudo.activo == true`;
  - `POST /share-target` → 303 a `/?compartido=`.
- [ ] **Step 5:** Commit `feat(app): pestaña Protección con Centinela integrado`.

---

### Task 7: Panel del familiar con los casos de Banco Demo

**Files:** Modify `frontend/familia.html`, `frontend/js/familia.js`.

**Interfaces:** Consume `GET /api/llamada/cases` y `POST /api/llamada/cases/{id}/decision` con `{decision, actor: "familia"}`, más el evento SSE `caso` del canal `familia` (Task 3).

- [ ] **Step 1: Test** en `test_frontend_static.py`, `test_family_panel_uses_bank_cases`: `GET /js/familia.js` contiene `/api/llamada/cases` y `actor: "familia"`, y **no** contiene `/api/banco/transferencias`.
- [ ] **Step 2:** Ejecuta el test → FAIL.
- [ ] **Step 3: Implementa.**
  - La sección «Operaciones retenidas» pasa a «Transferencias en revisión»: casos con `status` en `retenida`/`pendiente`.
    - Cada caso muestra importe, beneficiario, la primera señal más relevante (el `detail` de mayor peso) y un `<details>` con la conversación.
    - Botones **Bloquear** (`btn-danger`) y **Liberar** (`btn-outline`).
  - La tarjeta de estadísticas «Retenidas» cuenta esos casos.
  - Handler SSE `caso`: si el caso está retenido o pendiente → `toast` + `notifyBrowser("Banco Demo: transferencia en revisión", ...)`; siempre → recargar los casos.
  - Se eliminan los handlers `transferencia_retenida` y `transferencia`. El *pill* del escudo sigue leyendo `/api/banco`.
- [ ] **Step 4:** `pytest -q` → PASS. Verificación por HTTP: caso retenido vía API → `GET /api/llamada/cases` → decisión con `actor: "familia"` → `bloqueada`.
- [ ] **Step 5:** Commit `feat(familia): el familiar revisa las transferencias de Banco Demo`.

---

### Task 8: README y verificación de punta a punta

**Files:** Modify `README.md`.

- [ ] **Step 1: README**
  - En «Ejecución», `/` pasa a ser la app de Banco Demo con Centinela integrado. Quita `banco.html` y añade la ruta Perfil → Herramientas de demo.
  - En la sección «Escudo de llamada», cambia la URL de la app a `/`.
  - «Guion de la demo» pasa a ser una historia unificada:
    1. Inicio.
    2. Transferencia normal a Javier.
    3. SMS del falso hijo desde `demo.html` → alerta → transferencia al «hijo» con una cuenta nueva → el Escudo pregunta → el familiar la bloquea desde `familia.html`.
    4. Llamada del falso empleado del banco (escenario 3) → analista.
    5. Comprobar un mensaje con una nota de voz o una captura.
    6. Casero (legítima).
  - Actualiza el árbol del repositorio.
- [ ] **Step 2:** `pytest -q` → todo PASS. Apunta el total.
- [ ] **Step 3:** Verificación manual en el navegador (si hay herramienta de navegador; si no, por HTTP y anotado como pendiente para el usuario): cada pestaña, el escenario 1, el SMS rojo desde `demo.html` → banner en Inicio → transferencia frenada → decisión en `familia.html`, las herramientas de demo y el tema oscuro.
- [ ] **Step 4:** Commit `docs: guion de la demo con la app de banco unificada`.
