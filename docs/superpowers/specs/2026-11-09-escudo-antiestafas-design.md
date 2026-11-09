# Escudo — agente antiestafas en la puerta de la transferencia

**Fecha:** 2026-11-09
**Contexto:** proyecto para un hackathon de finanzas (tema libre). Parte del jurado trabaja en banca.
**Estado:** diseño pendiente de revisión. Siguiente paso tras aprobarlo: plan de implementación (skill `writing-plans`).

---

## 1. Objetivo

Construir una **demo funcional** de un agente de IA que un banco pondría en su app para frenar las estafas en las que **el propio cliente hace la transferencia** porque alguien le está guiando por teléfono (estafa del "falso empleado del banco").

La demo debe poder presentarse en **3–5 minutos** delante del jurado, con un compañero haciendo de estafador en directo.

### Criterios de éxito

- El jurado entiende en menos de 1 minuto el problema y dónde actúa el agente.
- Las transferencias normales pasan **sin fricción**; la estafa se **retiene**.
- Se ve el lado del banco: un panel con la puntuación de riesgo, las señales, la conversación y la decisión.
- El sistema es explicable: cada decisión muestra sus motivos.

---

## 2. El problema

En el fraude clásico alguien roba tus claves y entra en tu cuenta; los sistemas antifraude del banco están hechos para eso. En esta estafa **todo es legítimo**: el móvil, la huella y el código de verificación son del cliente, y la orden la da él. Lo que falla es la intención: el cliente cree que está "protegiendo" su dinero porque alguien que dice ser del banco se lo pide por teléfono.

Recorrido típico de la víctima:

1. Recibe una llamada que aparenta venir del banco (número falsificado).
2. El estafador conoce datos reales y suena profesional.
3. Crea urgencia ("hay un ataque en su cuenta") y aísla ("no hable con la oficina").
4. Le dicta un IBAN de una "cuenta segura" y le dice qué contestar si el banco pregunta.
5. Si funciona, repite: más traspasos, préstamos preconcedidos, etc.

Hoy los bancos muestran un aviso genérico que todo el mundo cierra sin leer.

---

## 3. La solución en una frase

> Cuando una transferencia parece arriesgada, el banco la pone en pausa y un agente mantiene una conversación corta y dirigida con el cliente, diseñada para romper el guion del estafador, antes de ejecutarla.

### Principios de diseño

- **El agente vive dentro del banco.** Toda transferencia es una petición a los servidores del banco; el agente es un paso más de ese circuito, justo antes de ejecutarla.
- **No escucha llamadas.** Solo usa la señal "hay una llamada activa" (en un móvil real: `CXCallObserver` en iOS, `TelephonyManager` en Android). Nunca el contenido.
- **Embudo para controlar coste y fricción.** Reglas baratas en el 100 % de las transferencias; el LLM solo entra en el pequeño porcentaje marcado como arriesgado.
- **El LLM no decide solo.** Devuelve una evaluación estructurada; una política determinista aplica la acción. Así es explicable y auditable.
- **Ante fallo, seguridad.** Si el LLM falla o no responde, la transferencia arriesgada se retiene y pasa a un analista.

---

## 4. Alcance

### Dentro

- App de banco simulada (web con aspecto de móvil) para un cliente ficticio.
- Pantalla de transferencia con las señales de contexto.
- Panel del presentador para simular la llamada activa y reiniciar la demo.
- Motor de riesgo por reglas.
- Agente conversacional (LLM) con evaluación estructurada.
- Política de decisión determinista: ejecutar, retener o enviar a un analista.
- Panel del analista del banco con los casos.
- Tres escenarios de demo con datos sembrados.

### Fuera (se menciona en el pitch como hoja de ruta)

- Analizador de SMS y correos reenviados por el cliente, y detección de campañas.
- Otras "puertas": alta de dispositivo, tarjeta en monedero móvil, confirmación de pagos con tarjeta, Bizum.
- Otros tipos de estafa en la demo (hijo en apuros, inversión falsa, compraventa). El catálogo del agente los conoce, pero la demo se centra en el falso empleado del banco.
- Autenticación real, varios usuarios, persistencia en base de datos, integración con sistemas bancarios reales.
- Detección real de llamadas (requiere app nativa).

---

## 5. Escenarios de la demo

Cliente ficticio: **Carmen López**, cliente de **Banco Demo** (nombre inventado; no se usa la marca de ningún banco real).

- Cuenta corriente: 2.300 €
- Cuenta de ahorro: 14.000 €
- Beneficiario habitual: su hijo, **Javier López**, al que transfiere unos 200 € al mes.
- Media histórica de transferencias salientes: unos 250 €.

| # | Escenario | Lo que pasa | Resultado esperado |
|---|---|---|---|
| 1 | **Transferencia normal** | 200 € a Javier, sin llamada | Se ejecuta al instante. El agente no aparece. |
| 2 | **Legítima con llamada** | Llamada activa (habla con su casero), 600 € a un beneficiario nuevo: el casero (por debajo del umbral de importe inusual, 750 €) | El agente hace 1–2 preguntas, las respuestas cuadran y la transferencia se ejecuta. Demuestra poca fricción. |
| 3 | **Estafa del falso empleado** | Llamada activa; minutos antes ha traspasado 8.000 € del ahorro a la corriente; envía 8.500 € a un IBAN nuevo pegado desde el portapapeles | El agente pregunta, detecta la suplantación del banco y **retiene** la transferencia. El caso aparece en el panel del analista. |

### Guion de la demo (unos 4 minutos)

1. **Contexto (30 s):** el problema y la frase de la solución.
2. **Escenario 1 (20 s):** "Así funciona el 99 % de las veces: no notas nada."
3. **Escenario 3 (2 min):** el compañero llama a la "víctima" y la guía. El presentador activa "llamada activa". La víctima hace el traspaso y la transferencia, y el agente la retiene.
4. **Panel del analista (40 s):** puntuación, señales, tipo de estafa, conversación y decisión.
5. **Escenario 2 (20 s):** "Y si es legítimo, una pregunta y listo."
6. **Cierre (30 s):** coste (céntimos por intervención, solo en <1 % de transferencias), privacidad (no escuchamos llamadas) y hoja de ruta.

---

## 6. Arquitectura

Aplicación web única (frontend y backend en el mismo proyecto).

```
┌─────────────────────────────┐      ┌──────────────────────────────────┐
│  App del cliente (móvil)    │      │  Backend (API)                   │
│  - Inicio / movimientos     │      │                                  │
│  - Traspaso ahorro→corriente│ ───► │  transfers  ──► riskEngine       │
│  - Nueva transferencia      │      │                    │             │
│  - Chat del Escudo          │ ◄──► │  conversations ──► shieldAgent   │
│  - Resultado                │      │                    │   (LLM)     │
└─────────────────────────────┘      │                    ▼             │
┌─────────────────────────────┐      │               decisionPolicy     │
│  Panel del presentador      │ ───► │  demo (llamada, reset)           │
└─────────────────────────────┘      │                                  │
┌─────────────────────────────┐      │  cases ◄──── store (memoria)     │
│  Panel del analista (banco) │ ◄──► │              seed (JSON)         │
└─────────────────────────────┘      └──────────────────────────────────┘
```

### Unidades y responsabilidades

| Unidad | Qué hace | Depende de |
|---|---|---|
| `riskEngine` | Función pura: recibe la transferencia, el contexto y el historial; devuelve la puntuación y la lista de señales activadas con su peso. | Nada (testeable sin red) |
| `shieldAgent` | Dado el contexto y la conversación, llama al LLM y devuelve el siguiente mensaje y una evaluación estructurada. | Cliente del LLM (inyectable para tests) |
| `decisionPolicy` | Función pura: combina la puntuación y la evaluación del agente en una acción final con sus motivos. | Nada |
| `store` | Estado en memoria: cuentas, movimientos, beneficiarios, transferencias, conversaciones y casos. Se reinicia desde la semilla. | `seed` |
| `seed` | Datos ficticios de Carmen y lista de cuentas "marcadas" como sospechosas. | — |
| API | Expone las operaciones de abajo y orquesta las unidades. | Todas las anteriores |
| UI del cliente, del presentador y del analista | Pantallas. | API |

### API

| Método y ruta | Uso |
|---|---|
| `GET /api/state` | Saldos, movimientos y beneficiarios de la clienta. |
| `POST /api/internal-transfer` | Traspaso ahorro → corriente (queda registrado: es una señal). |
| `POST /api/transfers` | Pide una transferencia. Body: importe, IBAN, nombre del beneficiario, concepto y contexto (`callActive`, `ibanPasted`). Respuesta: `executed` o `on_hold` con `conversationId`. |
| `POST /api/conversations/:id/messages` | El cliente responde; devuelve el siguiente mensaje del agente o la decisión final. |
| `GET /api/cases` | Casos para el panel del analista. |
| `POST /api/cases/:id/decision` | El analista libera o bloquea una transferencia retenida. |
| `POST /api/demo/call` | Activa o desactiva la llamada simulada. |
| `POST /api/demo/reset` | Restaura la semilla. |

---

## 7. Flujo de una transferencia

1. El cliente rellena la transferencia y pulsa "Enviar". La app adjunta el contexto: `callActive` (del panel del presentador) e `ibanPasted` (detectado con el evento `paste` del campo IBAN).
2. El backend llama a `riskEngine`.
3. **Puntuación < 40** → se ejecuta, se actualizan los saldos y se registra. El agente no aparece.
4. **Puntuación ≥ 40** → la transferencia queda `on_hold`, se crea una conversación y un caso, y el agente envía su primer mensaje.
5. Cada respuesta del cliente pasa por `shieldAgent`, hasta que el agente marca `readyToDecide` o se llega a **4 turnos del agente**.
6. `decisionPolicy` decide la acción final. La app muestra el resultado y el caso se actualiza en el panel del analista.

---

## 8. Motor de riesgo

Puntuación de 0 a 100 (se recorta a 100). Señales y pesos iniciales:

| Señal | Condición | Peso |
|---|---|---|
| `llamada_activa` | `callActive = true` | 35 |
| `beneficiario_nuevo` | El IBAN no está entre los beneficiarios conocidos | 20 |
| `importe_inusual` | Importe > 3 × la media histórica de transferencias salientes | 20 |
| `traspaso_previo_ahorro` | Traspaso ahorro → corriente en los 30 minutos anteriores | 20 |
| `cuenta_destino_marcada` | El IBAN está en la lista de cuentas sospechosas de la semilla | 25 |
| `iban_pegado` | El IBAN se pegó en lugar de escribirse | 10 |

Comprobación con los escenarios:

- Escenario 1: 0 → se ejecuta.
- Escenario 2: 35 + 20 = 55 → agente.
- Escenario 3: 35 + 20 + 20 + 20 + 10 = 105 → 100 → agente.

No se usa la edad del cliente como señal, para evitar sesgos discriminatorios.

---

## 9. Agente conversacional (`shieldAgent`)

**Modelo:** `claude-haiku-5-5` (rápido y barato; basta para conversaciones cortas). El identificador del modelo va en configuración. Antes de implementar, consultar la documentación actual de la API de Claude (skill `claude-api`).

**Entrada en cada turno:**

- La transferencia (importe, beneficiario, concepto).
- Las señales activadas por `riskEngine`.
- Un catálogo breve de tipos de estafa: falso empleado del banco, hijo en apuros, inversión falsa, compraventa.
- El historial de la conversación.

**Salida estructurada** (validada con un esquema; si no es válida, se trata como fallo):

```json
{
  "message": "texto para el cliente",
  "typology": "falso_empleado_banco | hijo_en_apuros | inversion_falsa | compraventa | ninguna",
  "risk": "low | medium | high",
  "redFlags": ["suplantacion_banco", "cuenta_segura", "urgencia", "aislamiento", "guion_aprendido", "contradiccion_datos"],
  "readyToDecide": true
}
```

**Instrucciones clave del agente:**

- Mensajes muy cortos, en español claro y con tono tranquilo y empático. Nunca acusar al cliente.
- No preguntar solo "¿para qué es?": el estafador ya lo ha preparado. Preguntar lo que el guion no cubre: "¿Estás hablando por teléfono con alguien ahora mismo?", "¿Te ha dicho alguien que no lo cuentes en la oficina?".
- Afirmar las políticas del banco que contradicen al estafador: "Tu banco nunca te pedirá mover tu dinero a otra cuenta para protegerlo".
- Detectar contradicciones entre las respuestas y los datos de la operación.
- No revelar la puntuación ni los pesos internos.
- No ejecutar nada: el agente solo conversa y evalúa.

**Mensaje de cierre:** lo genera la app a partir de la acción final, con textos fijos. No lo escribe el LLM, para que sea predecible.

---

## 10. Política de decisión (`decisionPolicy`)

Reglas aplicadas en este orden:

1. **Regla dura de suplantación:** `llamada_activa` + `redFlags` incluye `suplantacion_banco` o `cuenta_segura` → **RETENER**.
2. `risk = high` → **RETENER**.
3. `risk = medium` → **ENVIAR A ANALISTA**: la transferencia queda pendiente y se avisa al cliente de que un empleado la revisará.
4. `risk = low` → **EJECUTAR**.
5. Se llega al límite de turnos sin `readyToDecide`, o el LLM falla → **ENVIAR A ANALISTA**.

**RETENER** significa: la transferencia no se ejecuta; el cliente ve un mensaje fijo ("Hemos retenido esta transferencia para protegerte. Cuelga y llámanos al número de tu tarjeta"), y el caso queda en el panel del analista, que puede liberarla o bloquearla.

Cada decisión guarda sus motivos: las señales, la evaluación del agente y la regla aplicada.

---

## 11. Panel del analista

- Lista de casos con estado (`retenida`, `pendiente`, `ejecutada`, `liberada`, `bloqueada`), importe, puntuación y tipo de estafa.
- Detalle del caso: señales con sus pesos, evaluación del agente (riesgo y alertas), conversación completa y regla aplicada.
- Botones **Liberar** y **Bloquear** para los casos retenidos o pendientes.
- Se actualiza solo (sondeo cada 2 s es suficiente para la demo).

---

## 12. Manejo de errores

| Situación | Comportamiento |
|---|---|
| El LLM falla, tarda más de 10 s o devuelve JSON no válido | Se reintenta una vez; si vuelve a fallar → ENVIAR A ANALISTA con el motivo "agente no disponible". |
| Falta la clave de la API | El servidor arranca, pero la UI muestra un aviso claro en el panel del presentador. |
| Saldo insuficiente | Se rechaza antes de evaluar el riesgo, con un mensaje normal de banco. |
| Datos inválidos (IBAN con formato incorrecto, importe ≤ 0) | Validación en el formulario y en la API. |

---

## 13. Tecnología

- **Next.js (App Router) + TypeScript**, con frontend y API en el mismo proyecto.
- **Tailwind CSS** para la interfaz. La app del cliente imita un móvil (ancho ~390 px, centrado).
- **SDK oficial de Anthropic para TypeScript**, con la clave en `ANTHROPIC_API_KEY` (`.env.local`, sin subir al repositorio).
- **Estado en memoria** en el servidor; se reinicia desde `seed.json`.
- **Vitest** para las pruebas.

### Rutas de la interfaz

- `/` — app del cliente.
- `/presentador` — panel del presentador (llamada activa, reset y aviso de configuración).
- `/analista` — panel del analista.

Para la demo se abren en dos pantallas o pestañas: la app del cliente a un lado y el analista al otro.

---

## 14. Pruebas

- **`riskEngine`:** pruebas unitarias por señal y para los tres escenarios (puntuaciones 0, 55 y 100).
- **`decisionPolicy`:** pruebas unitarias para cada regla y su orden de prioridad.
- **`shieldAgent`:** pruebas con el cliente del LLM simulado (respuesta válida, JSON no válido, tiempo agotado).
- **Evaluación con el modelo real (manual, antes de la demo):** guiones de conversación para cada escenario, comprobando que el 3 termina en `high` o con la regla dura, y el 2 en `low`. Ejecutar cada guion varias veces para ver si el resultado es estable.
- **Ensayo completo de la demo** al menos dos veces.

---

## 15. Definición de terminado

- Los tres escenarios funcionan de principio a fin con el modelo real.
- El panel del analista muestra los casos y permite liberar o bloquear.
- Las pruebas de `riskEngine`, `decisionPolicy` y `shieldAgent` pasan.
- Hay un `README` con cómo arrancar el proyecto y el guion de la demo.

---

## 16. Decisiones tomadas por defecto (revisar)

Se tomaron sin confirmarlas explícitamente; se pueden cambiar:

- Stack: Next.js + TypeScript + Tailwind.
- Modelo: `claude-haiku-5-5`.
- Un solo tipo de estafa en la demo (falso empleado del banco).
- Sin analizador de SMS/correos (queda en la hoja de ruta).
- La llamada activa se simula con un interruptor en el panel del presentador.
- Banco y clienta ficticios; interfaz en español.
- Umbral de intervención: 40 puntos; máximo de 4 turnos del agente.
