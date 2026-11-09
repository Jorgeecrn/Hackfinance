# Escudo de llamada — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir a Centinela un banco simulado ("Banco Demo") que, cuando el cliente pide una transferencia arriesgada durante una llamada, la pausa y abre una conversación corta con un agente de Claude para frenar la estafa del falso empleado del banco.

**Architecture:** Módulo nuevo y aislado `backend/app/llamada/` dentro del FastAPI existente: funciones puras (`risk`, `policy`), un agente (`agent`) con cliente de Claude inyectable, un estado **en memoria** propio (`store`, no toca `state.json`) y un `APIRouter` con prefijo `/api/llamada`. Tres páginas nuevas en `frontend/llamada/` que reutilizan `styles.css` y `js/common.js`. Lo único que se toca del código existente es **una línea** en `main.py` (`include_router`) más documentación.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SDK `anthropic` 2.6.0 (`AsyncAnthropic`), pytest; HTML/JS sin build (módulos ES).

**Spec:** `docs/superpowers/specs/2026-11-09-escudo-antiestafas-design.md`

**Desviaciones de la spec (decididas, por reutilizar Centinela):**
- Stack: FastAPI + HTML/JS de Centinela en lugar de Next.js + Tailwind (§13 y §16 lo marcan como revisable). Vitest → pytest.
- Rutas con prefijo para no chocar con Centinela (`/api/demo/reset` ya existe): API en `/api/llamada/...`; UI en `/llamada/` (cliente), `/llamada/presentador.html`, `/llamada/analista.html`.
- Estado de caso extra `en_conversacion` mientras el agente pregunta (la spec no nombra ese estado intermedio).
- La regla dura (§10.1) se aplica en cuanto se cumple, aunque el agente aún no marque `readyToDecide`.

## Global Constraints

- **No cambiar el comportamiento de Centinela**: no editar `bank.py`, `state.py`, `events.py`, `agent.py`, `analyzer.py`, `rules.py`, `tools.py`, `config.py`, ni los HTML/JS existentes. En `main.py` solo se añaden el import y `app.include_router(...)` **antes** de `app.mount("/", ...)`. Los tests existentes deben seguir pasando sin cambios.
- Clienta: **Carmen López**, banco **Banco Demo** (no usar marcas reales). Corriente **2.300 €**, ahorro **14.000 €**, beneficiario habitual **Javier López**, media histórica de salidas **250 €**.
- Modelo: `claude-haiku-5-5`, configurable con `ESCUDO_MODEL`. Timeout **10 s** (`ESCUDO_TIMEOUT_S`), **1 reintento**. Clave: `ANTHROPIC_API_KEY` existente (`settings.anthropic_api_key`, respeta `settings.force_offline`).
- Umbral de intervención: **40** puntos. Máximo **4 turnos del agente**.
- Pesos: `llamada_activa` 35 · `beneficiario_nuevo` 20 · `importe_inusual` 20 (importe > 3 × media) · `traspaso_previo_ahorro` 20 (≤ 30 min antes) · `cuenta_destino_marcada` 25 · `iban_pegado` 10. Puntuación recortada a 100. Prohibido usar la edad.
- Nunca se escuchan las llamadas: solo existe el booleano `callActive`.
- Mensajes de cierre fijos (no los escribe el LLM):
  - execute: `"Listo. Tu transferencia se ha enviado."`
  - hold: `"Hemos retenido esta transferencia para protegerte. Cuelga y llámanos al número de tu tarjeta."` (literal de la spec)
  - review: `"Un empleado del banco va a revisar esta transferencia. Tu dinero no se ha movido."`
- Interfaz en español; la app del cliente simula un móvil (ancho ~390 px, centrado). Sondeo cada 2 s en el analista.
- Campos JSON de la API en camelCase, como en la spec (`callActive`, `ibanPasted`, `conversationId`, `readyToDecide`, `redFlags`).
- Commits en español, terminando con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Responder a una conversación ya decidida (doble envío, pestaña vieja) → 409; la transferencia nunca se ejecuta dos veces. *(Task 5: `test_reply_after_decision_conflicts`)*
2. IBAN pegado con espacios o en minúsculas (`es66 2100 …`) → se normaliza antes de compararlo con beneficiarios y cuentas marcadas; Javier no cuenta como beneficiario nuevo. *(Task 2: `test_iban_normalized_for_known_and_flagged`)*
3. El analista libera una transferencia retenida cuando ya no hay saldo → 422 «Saldo insuficiente» y el caso no cambia. *(Task 5: `test_release_without_balance_keeps_case`)*
4. Claude devuelve JSON bien formado pero fuera del esquema (`risk: "very_high"`, falta `message`) → se trata como fallo (reintento → analista), no revienta. *(Task 4: `test_schema_violation_is_failure`)*
5. Reset de la demo con una conversación abierta → el `conversationId` antiguo da 404 y no se ejecuta nada. *(Task 5: `test_reset_invalidates_conversation`)*

---

## File Structure

```
backend/app/llamada/__init__.py     vacío
backend/app/llamada/seed.py         SEED (datos de Carmen), FLAGGED_IBANS, PRESETS de escenarios
backend/app/llamada/store.py        estado en memoria + lock: reset(), snapshot(), mutate(fn)
backend/app/llamada/risk.py         evaluate_risk(...) pura + THRESHOLD
backend/app/llamada/policy.py       decide(...) pura + CLOSING_TEXTS
backend/app/llamada/agent.py        next_turn(...) con Claude, esquema, reintento, AgentUnavailable
backend/app/llamada/service.py      orquestación (transferencias, conversación, analista, demo)
backend/app/llamada/router.py       APIRouter(prefix="/api/llamada")
backend/app/main.py                 +2 líneas (import + include_router)
backend/tests/test_llamada_risk.py · test_llamada_policy.py · test_llamada_agent.py · test_llamada_api.py
frontend/llamada/index.html         app del cliente (marco de móvil)
frontend/llamada/presentador.html   panel del presentador
frontend/llamada/analista.html      panel del analista
frontend/llamada/llamada.css        estilos propios (marco móvil, chat, tabla de casos)
frontend/js/llamada/cliente.js · presentador.js · analista.js
eval/run_llamada_eval.py            guiones contra el modelo real (manual)
README.md, .env.example             sección nueva / variables nuevas
```

---

### Task 0: Preparación

- [ ] **Step 1:** `git checkout -b feature/escudo-llamada`
- [ ] **Step 2:** Copia este plan a `docs/superpowers/plans/2026-11-09-escudo-llamada.md`.
- [ ] **Step 3:** El `.venv` existe pero está vacío: `.venv/Scripts/python.exe -m pip install -r requirements.txt`
- [ ] **Step 4:** Línea base: `cd backend && ../.venv/Scripts/python.exe -m pytest -q` → todos PASS. Apunta el número de tests (debe seguir igual + los nuevos al final).
- [ ] **Step 5:** Commit `docs: plan de implementación del escudo de llamada`.

---

### Task 1: Semilla y estado en memoria

**Files:** Create `backend/app/llamada/__init__.py`, `seed.py`, `store.py`. Test: `backend/tests/test_llamada_api.py` (se crea aquí, crece en Task 5).

**Interfaces:**
- Produces:
  - `seed.SEED: dict` con claves `client {"name": "Carmen López", "bank": "Banco Demo"}`, `accounts {"corriente": {"iban": "ES6000491500051234567892", "balance": 2300.0}, "ahorro": {"balance": 14000.0}}`, `beneficiaries [{"name": "Javier López", "iban": "ES6621000418401234567891"}]`, `movements` (6 salidas `{"type": "transfer_out", "amount", "ts", "name", "iban"}` de 200, 200, 200, 200, 350 y 350 € con fechas fijas pasadas → media 250), `transfers [] `, `cases []`, `callActive False`.
  - `seed.FLAGGED_IBANS = ["ES9814650100941900123456"]`
  - `seed.PRESETS`: `normal` (Javier López, `ES6621000418401234567891`, 200, "Ayuda mensual", `ibanPasted` false), `casero` (Antonio Ruiz, `ES6201822370420201504358`, 600, "Alquiler noviembre", false), `estafa` (Cuenta segura Banco Demo, `ES4920383000001000123456`, 8500, "Protección de fondos", `ibanPasted` true; requiere traspaso previo de 8.000 €).
  - `store.reset() -> None` (deepcopy de SEED), `store.snapshot() -> dict` (deepcopy), `store.mutate(fn: Callable[[dict], T]) -> T` (bajo `threading.RLock`). El estado se crea al importar el módulo.
  - Movimientos que se añaden: `{"type": "internal_in" | "transfer_out", "amount", "ts" (ISO UTC), ...}`.

- [ ] **Step 1: Test** `test_store_reset_restores_seed`: `store.mutate(lambda s: s["accounts"]["corriente"].update(balance=1))`, `store.reset()`, `assert store.snapshot()["accounts"]["corriente"]["balance"] == 2300.0`, y `snapshot()` devuelve una copia (si se modifica no cambia el store).
- [ ] **Step 2:** Ejecuta `pytest tests/test_llamada_api.py -v` → FAIL (ImportError).
- [ ] **Step 3:** Implementa `seed.py` y `store.py`.
- [ ] **Step 4:** Ejecuta el test → PASS.
- [ ] **Step 5:** Commit `feat(llamada): semilla y estado en memoria del Banco Demo`.

---

### Task 2: Motor de riesgo

**Files:** Create `backend/app/llamada/risk.py`. Test: `backend/tests/test_llamada_risk.py`.

**Interfaces:**
- Consumes: `seed.SEED`, `seed.FLAGGED_IBANS`.
- Produces: `THRESHOLD = 40`; `WEIGHTS: dict[str, int]` (los 6 ids de Global Constraints); `normalize_iban(s: str) -> str` (sin espacios, en mayúsculas);
  `evaluate_risk(amount: float, iban: str, call_active: bool, iban_pasted: bool, beneficiaries: list[dict], movements: list[dict], flagged: list[str], now: datetime) -> dict` → `{"score": int, "signals": [{"id": str, "weight": int, "detail": str}]}`, con las señales en el orden de `WEIGHTS`.
  - Media = promedio de los `amount` con `type == "transfer_out"`; sin salidas, `importe_inusual` no se activa. La condición es estricta (`>`).
  - `traspaso_previo_ahorro`: hay un `internal_in` con `0 <= now - ts <= 30 min`.
  - `detail` es una frase en español para el analista (p. ej. `"8.500 € es más de 3 veces su media (250 €)"`).

- [ ] **Step 1: Tests** (con un helper `ctx(**over)` sobre los datos de la semilla y `now` fijo):
  - `test_scenario_normal_scores_0`: 200 € a Javier, sin llamada → `score == 0`, `signals == []`.
  - `test_scenario_casero_scores_55`: llamada + IBAN del casero, 600 € → `55`, ids `["llamada_activa", "beneficiario_nuevo"]`.
  - `test_scenario_estafa_caps_at_100`: llamada, 8.500 €, IBAN de la estafa, pegado, con un `internal_in` de 8.000 € 5 min antes → `100` y 5 señales (sin `cuenta_destino_marcada`).
  - `test_each_signal_weight`: parametrizado; cada señal sola da exactamente su peso (para `cuenta_destino_marcada` se usa el IBAN de `FLAGGED_IBANS`).
  - `test_unusual_amount_is_strict`: 750 € → sin `importe_inusual`; 750,01 € → con ella.
  - `test_internal_transfer_older_than_30_min_ignored`: `internal_in` hace 31 min → sin `traspaso_previo_ahorro`.
  - `test_iban_normalized_for_known_and_flagged`: `"es66 2100 0418 4012 3456 7891"` → sin `beneficiario_nuevo`; el IBAN marcado en minúsculas y con espacios → `cuenta_destino_marcada`.
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3:** Implementa `risk.py`.
- [ ] **Step 4:** Ejecuta los tests → PASS.
- [ ] **Step 5:** Commit `feat(llamada): motor de riesgo por reglas`.

---

### Task 3: Política de decisión

**Files:** Create `backend/app/llamada/policy.py`. Test: `backend/tests/test_llamada_policy.py`.

**Interfaces:**
- Produces: `CLOSING_TEXTS: dict[str, str]` (textos de Global Constraints, claves `execute`/`hold`/`review`); `HARD_FLAGS = {"suplantacion_banco", "cuenta_segura"}`;
  `hard_rule_applies(signal_ids: list[str], assessment: dict | None) -> bool`;
  `decide(signal_ids: list[str], assessment: dict | None, ready: bool) -> dict` → `{"action": "execute" | "hold" | "review", "rule": str, "reasons": list[str]}`.
  Orden (la primera que se cumple):
  1. `R1_suplantacion`: `hard_rule_applies` → hold.
  2. `R2_riesgo_alto`: `risk == "high"` → hold.
  3. `R3_riesgo_medio`: `risk == "medium"` → review.
  4. `R4_riesgo_bajo`: `risk == "low"` y `ready` → execute.
  5. `R5_sin_decision` → review. Si `assessment is None`, `reasons` incluye `"agente no disponible"`; si no, `"límite de turnos sin decisión"`.

  `reasons` siempre lista las señales y, si hay evaluación, `risk`, `typology` y `redFlags`.

- [ ] **Step 1: Tests:**
  - `test_hard_rule_beats_low_risk`: `["llamada_activa"]` + `{"risk": "low", "redFlags": ["cuenta_segura"]}` → `hold`, `R1_suplantacion`.
  - `test_hard_rule_needs_call`: los mismos flags sin `llamada_activa` y `risk` low, `ready` → `execute`.
  - `test_high_holds_even_if_not_ready`: `R2`, `hold`.
  - `test_medium_reviews`: `R3`, `review`.
  - `test_low_ready_executes`: `R4`, `execute`.
  - `test_low_not_ready_reviews`: `R5`, `review`, con «límite de turnos sin decisión» en `reasons`.
  - `test_agent_failure_reviews`: `assessment=None` → `R5`, `review`, con «agente no disponible» en `reasons`.
  - `test_closing_hold_text_is_literal`: `CLOSING_TEXTS["hold"]` es igual al texto de la spec.
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3:** Implementa `policy.py`.
- [ ] **Step 4:** Ejecuta los tests → PASS.
- [ ] **Step 5:** Commit `feat(llamada): política de decisión determinista`.

---

### Task 4: Agente conversacional

**Files:** Create `backend/app/llamada/agent.py`. Test: `backend/tests/test_llamada_agent.py`.

**Interfaces:**
- Consumes: `app.config.settings` (`anthropic_api_key`, `claude_enabled`).
- Produces:
  - `MODEL = os.getenv("ESCUDO_MODEL", "claude-haiku-5-5")`, `TIMEOUT_S = float(os.getenv("ESCUDO_TIMEOUT_S", "10"))`, `MAX_AGENT_TURNS = 4`.
  - `class AgentUnavailable(RuntimeError)`.
  - `class Assessment(pydantic.BaseModel)`: `message: str` (min 1), `typology: Literal["falso_empleado_banco","hijo_en_apuros","inversion_falsa","compraventa","ninguna"]`, `risk: Literal["low","medium","high"]`, `redFlags: list[Literal["suplantacion_banco","cuenta_segura","urgencia","aislamiento","guion_aprendido","contradiccion_datos"]]`, `readyToDecide: bool`; `model_config = ConfigDict(extra="forbid")`.
  - `ASSESSMENT_SCHEMA`: el JSON schema equivalente, escrito a mano (`additionalProperties: false`, todos los campos `required`, enums).
  - `get_client() -> anthropic.AsyncAnthropic` (singleton, `timeout=TIMEOUT_S`, `max_retries=0`).
  - `async next_turn(transfer: dict, signals: list[dict], transcript: list[dict], client=None) -> dict` (el `Assessment` como dict). `transcript` es una lista de `{"role": "agent" | "client", "text": str}`.

**Llamada a Claude** (comprobada con la skill `claude-api`: Haiku 5.5 admite `output_config.format` json_schema y `effort`; no tiene fallback del lado del servidor ante rechazos):
```python
await asyncio.wait_for(client.messages.create(
    model=MODEL, max_tokens=2000, system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": render_turn(transfer, signals, transcript)}],
    output_config={"effort": "low", "format": {"type": "json_schema", "schema": ASSESSMENT_SCHEMA}},
), timeout=TIMEOUT_S)
```
- Es una petición sin estado por turno: toda la conversación va en un único mensaje `user`, así no se reenvían bloques de razonamiento (*thinking*) ni hay que editar el historial. El JSON se lee del primer bloque `type == "text"`.
- Fallo: excepción de `anthropic`, `TimeoutError`, `stop_reason` igual a `"refusal"` o `"max_tokens"`, JSON no válido o `ValidationError` de Pydantic. Con un fallo se reintenta una vez; con el segundo se lanza `AgentUnavailable`.
- Si `client is None` y `not settings.claude_enabled`, lanza `AgentUnavailable("falta ANTHROPIC_API_KEY")` sin llamar a nada.
- `SYSTEM_PROMPT` recoge en español las instrucciones de §9:
  - mensajes muy cortos, tono tranquilo y sin acusar;
  - preguntas que el guion del estafador no cubre («¿Estás hablando por teléfono con alguien ahora mismo?», «¿Te ha dicho alguien que no lo cuentes en la oficina?»);
  - afirmar «Tu banco nunca te pedirá mover tu dinero a otra cuenta para protegerlo»;
  - detectar contradicciones; no revelar puntuación ni pesos; no ejecutar nada;
  - el catálogo de las 4 tipologías;
  - en el primer turno siempre una pregunta;
  - `readyToDecide = true` solo cuando las respuestas basten para decidir.
  - `render_turn` incluye importe, beneficiario, concepto, los `detail` de las señales (sin pesos ni puntuación) y la transcripción.

- [ ] **Step 1: Tests** (cliente falso como en `test_agent.py`: `NS(messages=FakeMessages([...]))`; respuesta `NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(VALID))])`):
  - `test_valid_turn_parsed_and_request_shape`: devuelve `VALID`; `calls[0]["model"] == "claude-haiku-5-5"`, `output_config["format"]["type"] == "json_schema"`, `output_config["effort"] == "low"`; el texto del usuario contiene el importe y el detalle de las señales, pero no `"35"` ni la palabra «puntuación».
  - `test_invalid_json_retries_once_then_unavailable`: dos respuestas con texto `"no json"` → `AgentUnavailable`; `len(calls) == 2`.
  - `test_retry_recovers`: primero JSON no válido y luego válido → éxito, 2 llamadas.
  - `test_schema_violation_is_failure`: `{"risk": "very_high", ...}` dos veces → `AgentUnavailable`.
  - `test_timeout_is_failure`: con `monkeypatch` de `agent.TIMEOUT_S = 0.05` y un `create` que hace `asyncio.sleep(1)` → `AgentUnavailable`.
  - `test_refusal_is_failure`: `stop_reason="refusal"` dos veces → `AgentUnavailable`.
  - `test_offline_without_client_raises_without_calling`: con `client=None` (los tests van con `FORCE_OFFLINE=1`) → `AgentUnavailable`.
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3:** Implementa `agent.py`.
- [ ] **Step 4:** Ejecuta los tests → PASS.
- [ ] **Step 5:** Commit `feat(llamada): agente conversacional con salida estructurada`.

---

### Task 5: Servicio, API y conexión con `main.py`

**Files:** Create `backend/app/llamada/service.py`, `router.py`. Modify `backend/app/main.py` (añadir `from .llamada.router import router as llamada_router` y `app.include_router(llamada_router)` justo antes de `app.mount("/", ...)`). Test: `backend/tests/test_llamada_api.py`.

**Interfaces:**
- Consumes: `store`, `seed`, `risk.evaluate_risk/THRESHOLD/normalize_iban`, `policy.decide/hard_rule_applies/CLOSING_TEXTS`, `agent.next_turn/AgentUnavailable/MAX_AGENT_TURNS`. **El servicio llama siempre a `agent.next_turn` a través del módulo** (`from . import agent`) para poder sustituirlo con `monkeypatch` en los tests.
- Forma del caso: `{"id", "conversationId", "createdAt", "amount", "beneficiaryName", "iban", "concept", "score", "signals", "status", "agentTurns", "transcript", "assessment", "decision"}`. Valores de `status`: `en_conversacion | retenida | pendiente | ejecutada | liberada | bloqueada`. Las acciones se traducen así: `hold` → `retenida`, `review` → `pendiente`, `execute` → `ejecutada`.
- Vista de conversación (`ConversationView`): `{"conversationId", "done": bool, "message": str | None, "outcome": {"action", "text"} | None}`.

| Ruta | Body | Respuesta / errores |
|---|---|---|
| `GET /api/llamada/state` | — | `{client, accounts, beneficiaries, movements, callActive, agentEnabled, model}` |
| `POST /api/llamada/internal-transfer` | `{amount>0}` | Mueve dinero de ahorro a corriente y añade un `internal_in`; si no hay saldo en el ahorro, 422 |
| `POST /api/llamada/transfers` | `{amount>0, iban, beneficiaryName, concept="", context{callActive, ibanPasted}}` | IBAN no válido (`tools.analyze_iban(iban)["valido"]`) → 422. Saldo de la corriente insuficiente → 422 `"Saldo insuficiente"`, **antes** de calcular el riesgo y sin crear caso. Si `score < 40` → `{"status":"executed","transfer":{...}}`. Si no, se crea el caso y se llama a `next_turn`: si responde → `{"status":"on_hold", ...ConversationView(message)}`; si lanza `AgentUnavailable` → se decide con `assessment=None` y se devuelve `{"status":"on_hold", ...ConversationView(done, outcome review)}` |
| `POST /api/llamada/conversations/{id}/messages` | `{text}` (sin espacios sobrantes, 1–500 caracteres) | Id desconocido → 404. Caso fuera de `en_conversacion` → 409. Se añade la respuesta del cliente y se llama a `next_turn`. Se decide si: falla el agente (`assessment=None`), `readyToDecide`, `hard_rule_applies`, o `agentTurns == 4`. Si se decide → `outcome` con el texto de `CLOSING_TEXTS`; si no → el siguiente `message` |
| `GET /api/llamada/cases` | — | Lista, de más reciente a más antiguo |
| `POST /api/llamada/cases/{id}/decision` | `{decision: "release" \| "block"}` | Caso desconocido → 404. Caso fuera de `retenida`/`pendiente` → 409. `release` sin saldo → 422 y el caso no cambia. `release` → ejecuta → `liberada`. `block` → `bloqueada` |
| `POST /api/llamada/demo/call` | `{active: bool}` | `{callActive}` |
| `POST /api/llamada/demo/reset` | — | `store.reset()`; responde `{"ok": true}` |

- `readyToDecide` del **primer** turno (antes de que el cliente responda) se ignora.
- Ejecutar una transferencia descuenta el importe de la corriente, añade un `transfer_out` a `movements` y registra la transferencia en `transfers`.
- La llamada al agente se hace **fuera** del lock del store.

- [ ] **Step 1: Tests** (fixture autouse que llama a `store.reset()`; `fake_agent(script)` sustituye `app.llamada.agent.next_turn` por una función async que devuelve evaluaciones en orden o lanza `AgentUnavailable`):
  - `test_scenario_normal_executes_without_agent`: preset `normal` → `executed`, corriente 2.100 y el agente falso no se llama.
  - `test_scenario_casero_low_risk_executes`: llamada activa y preset `casero`; el agente devuelve `[low, not ready]` y luego `[low, ready]` → `on_hold` + mensaje; tras una respuesta, `done`, `outcome.action == "execute"`, corriente 1.700 y caso `ejecutada`.
  - `test_scenario_estafa_held_and_analyst_blocks`: traspaso de 8.000 €, llamada y preset `estafa`. El agente devuelve primero una pregunta y después `{"risk": "medium", "redFlags": ["suplantacion_banco"], "readyToDecide": false}`. Resultado: retenida por `R1` y `outcome.text == CLOSING_TEXTS["hold"]`; en `/cases`, el caso `retenida` con `score 100`. Tras `block` → `bloqueada` y la corriente sigue en 10.300.
  - `test_analyst_release_executes`: caso retenido → `release` → `liberada` y se descuenta el saldo.
  - `test_turn_limit_goes_to_review`: el agente nunca está listo y `risk` es low; tras 3 respuestas del cliente → `pendiente`, `R5`.
  - `test_agent_unavailable_goes_to_review`: `next_turn` lanza → `on_hold` con `done` y `outcome.action == "review"`; caso `pendiente` con «agente no disponible» en `decision.reasons`.
  - `test_insufficient_balance_rejected_before_risk`: 5.000 € → 422; `/cases` vacío.
  - `test_invalid_input`: IBAN `ES00 1234` → 422; `amount 0` → 422; respuesta del cliente `"   "` → 422.
  - `test_reply_after_decision_conflicts`: tras el `outcome`, otra respuesta → 409; el saldo no cambia.
  - `test_release_without_balance_keeps_case`: caso `retenida`; con `store.mutate` se deja la corriente sin saldo; `release` → 422 y el caso sigue `retenida`.
  - `test_reset_invalidates_conversation`: caso abierto → `demo/reset` → responder → 404.
  - `test_centinela_untouched`: tras usar `/api/llamada/*`, `GET /api/banco` devuelve `saldo == 12450.3` y `entidad` contiene «MyInvestor».
- [ ] **Step 2:** Ejecuta los tests → FAIL.
- [ ] **Step 3:** Implementa `service.py` y `router.py` (modelos Pydantic de entrada con `Field(gt=0)`, `max_length`) y añade las 2 líneas en `main.py`.
- [ ] **Step 4:** Ejecuta `pytest -q` (la suite **completa**) → todo PASS; total = línea base + nuevos.
- [ ] **Step 5:** Commit `feat(llamada): API del Banco Demo con escudo de llamada`.

---

### Task 6: App del cliente (`/llamada/`)

**Files:** Create `frontend/llamada/index.html`, `frontend/llamada/llamada.css`, `frontend/js/llamada/cliente.js`.

**Interfaces:** Consume la API de la Task 5 con `api`, `el`, `icon`, `fmtMoney`, `fmtShort` y `toast` de `/js/common.js`. Carga `/styles.css` y después `/llamada/llamada.css`.

- [ ] **Step 1:** Marco de móvil (`.phone`, `max-width: 390px`, centrado; en pantallas de menos de 420 px ocupa todo el ancho). Cabecera «Banco Demo». Pantallas que se alternan con `hidden`:
  - **Inicio:** saldos de corriente y ahorro, movimientos, botones «Traspasar desde ahorro» y «Nueva transferencia».
  - **Traspaso:** campo de importe → `POST internal-transfer`.
  - **Transferencia:** beneficiario, IBAN, importe y concepto. El evento `paste` del IBAN pone `ibanPasted = true`, que vuelve a `false` al abrir el formulario de nuevo. Fila pequeña «Demo: rellenar escenario 1 · 2 · 3» con los `PRESETS`, copiados en JS: el 3 marca `ibanPasted`.
  - **Chat del Escudo:** burbujas del agente y del cliente, campo de texto y botón «Responder». El botón se desactiva mientras se espera la respuesta y aparece el indicador «Escribiendo…».
  - **Resultado:** icono y color según la acción (`execute` verde, `hold` rojo, `review` ámbar), texto de `outcome.text` y botón «Volver al inicio».
- [ ] **Step 2:** Sondeo de `GET state` cada 2 s: si `callActive`, se ve el aviso fijo «📞 Llamada en curso». `callActive` se envía en `context` al pedir la transferencia. Los errores 422 se muestran con `toast`.
- [ ] **Step 3: Verificación manual:** `cd backend && ../.venv/Scripts/uvicorn.exe app.main:app --port 8000`. Abre `http://localhost:8000/llamada/` en el modo móvil de DevTools (390 px). Con el escenario 1 la transferencia se ejecuta y el saldo baja a 2.100. Con 5.000 € aparece el toast «Saldo insuficiente». No hay errores en la consola. `http://localhost:8000/` (Centinela) sigue igual.
- [ ] **Step 4:** Commit `feat(llamada): app móvil del cliente del Banco Demo`.

---

### Task 7: Paneles del presentador y del analista

**Files:** Create `frontend/llamada/presentador.html`, `frontend/llamada/analista.html`, `frontend/js/llamada/presentador.js`, `frontend/js/llamada/analista.js`.

- [ ] **Step 1: Presentador.**
  - Interruptor grande «Llamada activa» → `POST demo/call`, refleja `state.callActive`.
  - Botón «Reiniciar demo» → `POST demo/reset`.
  - Si `agentEnabled` es falso, aviso visible: «Falta ANTHROPIC_API_KEY: las transferencias arriesgadas irán al analista sin conversación».
  - Muestra el modelo, el guion de los 3 escenarios en 3 líneas y enlaces a la app y al analista.
- [ ] **Step 2: Analista.**
  - Sondeo de `GET cases` cada 2 s.
  - Tabla con estado (píldora de color), importe, beneficiario, puntuación y tipología.
  - Detalle del caso seleccionado: señales con peso y `detail`, evaluación (`risk`, `redFlags`), conversación completa, regla aplicada y motivos.
  - Botones «Liberar» y «Bloquear» solo en los casos `retenida`/`pendiente`.
  - La selección se mantiene entre sondeos.
- [ ] **Step 3: Verificación manual** con el servidor en marcha y una clave real en `.env`:
  1. Escenario 3 de principio a fin (traspaso de 8.000 €, llamada activa, transferencia de 8.500 € y respuestas como víctima guiada): termina retenida y aparece en el analista con puntuación 100 y la conversación.
  2. Bloquear el caso → `bloqueada`.
  3. Escenario 2 con respuestas coherentes («hablo con mi casero, es el alquiler») → se ejecuta.
  4. Sin clave → aviso en el presentador, y el escenario 3 termina en `pendiente`.
- [ ] **Step 4:** Commit `feat(llamada): paneles del presentador y del analista`.

---

### Task 8: Evaluación manual, documentación y configuración

**Files:** Create `eval/run_llamada_eval.py`. Modify `README.md` (sección nueva), `.env.example` (variables nuevas).

- [ ] **Step 1: `eval/run_llamada_eval.py --veces N` (por defecto 3).**
  - Añade `backend` a `sys.path`.
  - Para cada guion (escenario 3 «víctima guiada», con respuestas como «Sí, es del banco, me dicen que hay un ataque» o «Me han dicho que no lo cuente»; escenario 2 «casero», con respuestas coherentes) usa `risk.evaluate_risk` y llama a `agent.next_turn` turno a turno con las respuestas guionizadas, aplicando las mismas reglas de parada que el servicio y después `policy.decide`.
  - Imprime una tabla `guion · ejecución · acción · regla · risk · redFlags`.
  - Éxito: el escenario 3 acaba siempre en `hold` y el 2 en `execute`.
  - Sin clave, avisa y termina con código 1.
- [ ] **Step 2: README.** Sección «🛡️ Escudo de llamada (Banco Demo)»:
  - qué hace;
  - URLs `/llamada/`, `/llamada/presentador.html` y `/llamada/analista.html`;
  - guion de 4 minutos de §5;
  - cómo ejecutar la evaluación;
  - privacidad: no se escuchan llamadas.

  Añade una fila al árbol del repositorio. **Sin** cambiar las secciones existentes.
- [ ] **Step 3:** En `.env.example`, bloque `# --- Escudo de llamada ---` con `ESCUDO_MODEL=claude-haiku-5-5` y `ESCUDO_TIMEOUT_S=10`.
- [ ] **Step 4:** `.venv/Scripts/python.exe eval/run_llamada_eval.py --veces 3` con una clave real → se cumple el criterio de éxito. Si no, ajusta `SYSTEM_PROMPT` en `agent.py` y repite (los tests de la Task 4 deben seguir pasando).
- [ ] **Step 5:** Commit `docs(llamada): guion, README y evaluación con el modelo real`.

---

### Task 9: Verificación final

- [ ] `cd backend && ../.venv/Scripts/python.exe -m pytest -q` → todo PASS; total = línea base + nuevos.
- [ ] `git diff main --stat -- backend/app/ frontend/` → de lo existente, solo cambia `backend/app/main.py` (+2 líneas).
- [ ] Guion de Centinela del README (pasos 2–5) → funciona igual que antes.
- [ ] Ensayo completo de la demo del Escudo **dos veces** (§14), con la app y el analista en pestañas lado a lado.
- [ ] Usa superpowers:finishing-a-development-branch.

---

## Verificación de punta a punta (resumen)

1. Tests: `pytest -q` (sin red, `FORCE_OFFLINE=1` por `conftest.py`).
2. Modelo real: `python eval/run_llamada_eval.py --veces 3`.
3. Manual: arrancar con `iniciar.bat` y abrir `/llamada/presentador.html`, `/llamada/` y `/llamada/analista.html`; recorrer los escenarios 1 → 3 → analista → 2.
