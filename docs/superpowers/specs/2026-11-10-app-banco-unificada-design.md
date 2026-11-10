# App de banco unificada: Centinela como extensión de Banco Demo

**Fecha:** 2026-11-10
**Rama:** `experimento`
**Estado:** diseño aprobado en conversación; pendiente de revisión escrita. Siguiente paso: plan de implementación (skill `writing-plans`).
**Parte de:** `docs/superpowers/specs/2026-11-09-escudo-antiestafas-design.md` (escudo de llamada, ya implementado).

---

## 1. Objetivo

Que la demo deje de parecer "una app aparte" y se vea como **la app normal de un banco** (Banco Demo) que lleva dentro la extensión antiestafas que proporciona este repositorio. El jurado (parte trabaja en banca) debe ver:

- Una app de banco creíble: saldo, movimientos, transferencias, accesos rápidos.
- Dentro de ella, nuestras funciones:
  - comprobar mensajes sospechosos (texto, enlace, captura, archivo, nota de voz);
  - intervención en transferencias cuando hay una llamada activa o la cuenta de destino es sospechosa;
  - elegir los contactos de confianza que reciben los avisos.
- Una zona discreta, solo para el equipo, con accesos al presentador, al analista, al panel del familiar y al panel de SMS.

No hay que construir todas las funciones de un banco: lo que no es nuestro solo **aparenta** existir.

### Criterios de éxito

- Una sola clienta (Carmen López) y un solo banco con un único saldo en todas las pantallas.
- Un SMS de estafa recibido (alerta roja) hace que la siguiente transferencia a una cuenta nueva pase por el agente del escudo.
- La llamada activa sigue funcionando como hoy (escenarios 1, 2 y 3 del escudo de llamada).
- El familiar de confianza recibe en tiempo real los casos retenidos o pendientes y puede liberarlos o bloquearlos.
- Los tests existentes siguen pasando; los endpoints `/api/banco/*` siguen respondiendo igual.

## 2. Decisiones tomadas (con el usuario)

| Tema | Decisión |
|---|---|
| Bancos | Un solo banco y una sola Carmen: Banco Demo es el banco; Centinela es su sección de protección. |
| Pantallas existentes | La app de banco pasa a ser la entrada principal en `/` y sustituye a `index.html` (app de Centinela) y a `banco.html`. `familia.html` y `demo.html` se quedan, se adaptan y se enlazan desde la zona de demo. |
| Estilo | App de banco moderna y legible: letra algo mayor de lo habitual y buen contraste, sin aspecto "especial para mayores". |
| Zona de demo | Entrada discreta "Herramientas de demo" al final de la pestaña Perfil. |
| SMS simulados | Se mantienen como bandeja "Mensajes vigilados" alimentada por `demo.html`, con la nota "requiere permiso de notificaciones (Android)". Se mantiene también la comprobación manual. |
| Backend | Enfoque A: Banco Demo (`backend/app/llamada/`) es el único banco; el escudo por mensaje de Centinela pasa a ser una señal más del motor de riesgo. |
| Peso de la señal nueva | `alerta_estafa_reciente` = 25. |
| Familiar | Puede liberar o bloquear casos igual que el analista. |

## 3. La app (`/`)

PWA instalable; se mantienen `manifest.webmanifest`, el service worker y "Compartir → Banco Demo" (Web Share Target, `/share-target` → `/?compartido=<id>`). Barra de navegación inferior con 4 pestañas.

### 3.1 Inicio

- Saludo ("Hola, Carmen") y tarjeta de saldo de la cuenta corriente, con la de ahorro debajo.
- Accesos rápidos: **Transferir** y **Traspaso** (funcionales); **Bizum** y **Tarjetas** (decorativos: muestran el toast "Próximamente").
- Últimos movimientos (8).
- Banner de estado, con un solo mensaje y en este orden de prioridad:
  1. "📞 Llamada en curso".
  2. "⚠️ Mensaje sospechoso reciente: los pagos a cuentas nuevas se revisarán".
  3. "🛡️ Protección antiestafas activa".

### 3.2 Transferir

El flujo actual de `/llamada/` integrado en la app, sin cambios de comportamiento:

- formulario (con detección de IBAN pegado);
- chat del Escudo;
- pantalla de resultado;
- accesos "Demo: rellenar escenario 1 · 2 · 3".

El traspaso desde el ahorro se abre desde Inicio.

### 3.3 Protección (con la etiqueta "con tecnología Centinela")

- **Estado:**
  - interruptor de protección;
  - si el escudo por mensaje está activo, cuenta atrás y motivo.
- **Comprobar un mensaje:**
  - pegar texto o un enlace;
  - subir una captura o un archivo;
  - grabar o subir una nota de voz.
  - Muestra los pasos de la investigación en directo (SSE) y el veredicto 🟢🟡🔴 con pruebas, consejo y lectura en voz alta. Reutiliza la lógica de la app actual de Centinela.
- **Mensajes vigilados:**
  - bandeja alimentada por `/api/demo/entrante`, con la nota "requiere permiso de notificaciones (Android)";
  - cuando la protección está activa, cada mensaje se analiza solo;
  - con veredicto rojo salta la alerta a pantalla completa, como hoy.
- **Contactos de confianza y avisos:**
  - elegir el familiar que recibe los avisos y gestionar los contactos (`/api/perfil`);
  - interruptores "Leer los avisos en voz alta" y "Frenar pagos a cuentas nuevas tras un mensaje sospechoso" (`escudo_bancario`).
- Sin clave de IA, aviso de "modo básico", como hoy.

### 3.4 Perfil

- Datos de Carmen (nombre e IBAN de la cuenta corriente) y ajustes decorativos (notificaciones, seguridad: toast "Próximamente").
- Tema claro u oscuro.
- Al final, **Herramientas de demo**, una pantalla con:
  - enlaces (en pestaña nueva) a Presentador, Analista, Panel del familiar, Panel de SMS de demo y documentación de la API;
  - **Reiniciar toda la demo**, que llama a `POST /api/demo/reset` y `POST /api/llamada/demo/reset`.

## 4. Backend

### 4.1 Una sola Carmen

- Banco Demo es la única fuente de cuentas, movimientos y transferencias de la UI.
- Se añade **Lucía López** (`ES9121000418450200051332`) a `beneficiaries` de la semilla de Banco Demo.
- Los contactos de confianza y el familiar siguen en el perfil de Centinela (`state.json`), sin cambios.

### 4.2 Señal `alerta_estafa_reciente` (peso 25)

- `risk.evaluate_risk` recibe un parámetro nuevo `recent_alert: str | None = None`. Si no es `None`, se activa la señal; su texto describe la alerta, por ejemplo "Hace 12 min recibió un mensaje con señales de estafa: falso hijo". El valor por defecto mantiene los resultados actuales.
- El servicio calcula el valor a partir del estado de Centinela: si `bank.shield_active(state["banco"])`, usa `escudo.motivo` y la antigüedad de la alerta. Centinela solo activa el escudo cuando el perfil tiene `escudo_bancario` activado, así que el interruptor de la app lo controla.
- Si falla la lectura del estado de Centinela, la señal no se activa: se registra el error y no se interrumpe la transferencia.
- La política (R1–R5) no cambia. El agente recibe el detalle de la señal y puede preguntar por el mensaje.

Comprobación de puntuaciones:

| Caso | Puntos | Resultado |
|---|---|---|
| Alerta + beneficiario nuevo | 45 | agente |
| Alerta + Lucía o Javier (habituales) | 25 | se ejecuta |
| Llamada + alerta + beneficiario nuevo | 80 | agente |
| Escenarios 1 / 2 / 3 sin alerta | 0 / 55 / 100 | sin cambios |

### 4.3 El familiar decide también

- `POST /api/llamada/cases/{id}/decision` acepta un campo opcional `actor: "analista" | "familia"` (por defecto `"analista"`), que se guarda en `analystDecision.actor`.
- Cuando un caso pasa a `retenida` o `pendiente`, se publica el evento `caso` en el canal `familia` del bus existente (`events.bus`), con el caso. También al resolverse.
- `familia.html` muestra los casos abiertos de Banco Demo con importe, beneficiario, motivo y conversación, y botones **Liberar** y **Bloquear** (con `actor: "familia"`). Deja de usar `/api/banco` y `/api/banco/transferencias/*`. Las alertas por mensaje siguen como hoy.

### 4.4 Lo que no cambia

- `bank.py`, `/api/banco/*`, `analyzer.py`, `agent.py`, `rules.py`, `tools.py`, `state.py` y `events.py` de Centinela no se modifican. El escudo por mensaje sigue activándose igual; simplemente deja de usarse desde las pantallas.
- Las pantallas solo leen el escudo con `GET /api/banco` (cuenta atrás en Protección).

## 5. Frontend

| Archivo | Cambio |
|---|---|
| `frontend/index.html` | Se reescribe como la estructura de la app de banco (4 pestañas y pantallas). |
| `frontend/js/banco/app.js` | Navegación entre pestañas, estado compartido (`/api/llamada/state`, `/api/perfil`, `/api/banco` para el escudo), sondeo cada 2 s y SSE del canal `usuario`. |
| `frontend/js/banco/inicio.js` | Inicio y traspaso. |
| `frontend/js/banco/transferir.js` | Se traslada desde `js/llamada/cliente.js`. |
| `frontend/js/banco/proteccion.js` | Se traslada desde `js/app.js`: comprobar, bandeja, alerta, contactos y ajustes. |
| `frontend/js/banco/perfil.js` | Perfil y herramientas de demo. |
| `frontend/banco.css` | Estilos de la app de banco sobre los tokens de `styles.css`, con letra de tamaño normal. |
| `frontend/llamada/index.html` | Redirige a `/`. Se borra `js/llamada/cliente.js`. |
| `frontend/llamada/presentador.html` | El enlace "App de la clienta" pasa a ser `/`. |
| `frontend/familia.html`, `js/familia.js` | Casos de Banco Demo en lugar de las transferencias del banco antiguo (§4.3). |
| `frontend/demo.html` | El enlace "Banco" se quita; el enlace "App" sigue en `/`. |
| `frontend/banco.html`, `js/banco.js`, `js/app.js` | Se borran. |
| `frontend/sw.js` | Lista de archivos de la app actualizada; versión de caché `centinela-v3`. |

Todo el texto dinámico se pinta con `el()` o `textContent` (sin `innerHTML` con datos).

## 6. Manejo de errores

| Situación | Comportamiento |
|---|---|
| Sin clave de IA | Aviso "modo básico" en Protección; las transferencias arriesgadas van al analista (como hoy). |
| Falla la lectura del estado de Centinela al evaluar el riesgo | La señal de alerta no se activa; se registra el error. |
| Falla un endpoint al cargar una pestaña | Toast con el error; el resto de la app sigue funcionando. |
| Llega un SSE con la app en segundo plano | Se procesa al volver (como hoy en Centinela). |

## 7. Pruebas

- **Backend (TDD):**
  - `alerta_estafa_reciente`: peso, detalle, sin alerta = resultados actuales.
  - Integración: SMS rojo por `/api/analizar` → transferencia a un beneficiario nuevo → `on_hold` con la señal.
  - Transferencia a Lucía tras la alerta → se ejecuta.
  - Con `escudo_bancario` desactivado → no hay señal.
  - Decisión con `actor: "familia"` guardada.
  - Evento `caso` publicado en el canal `familia`.
  - Lucía como beneficiaria conocida.
- **Frontend:** comprobación por HTTP de cada página y una pasada en el navegador por cada flujo: Inicio, transferencia normal, escenario 3, comprobar un mensaje con texto, alerta por SMS desde `demo.html` → transferencia frenada, decisión desde `familia.html` y herramientas de demo.
- **README:** guion de demo actualizado con la historia unificada.

## 8. Fuera de alcance

- Funciones bancarias reales más allá de transferencia y traspaso (Bizum, tarjetas, inversiones: solo decorativas).
- Lectura real de SMS o notificaciones (app Android), autenticación y varios usuarios.
- Modo "letra grande" opcional.
