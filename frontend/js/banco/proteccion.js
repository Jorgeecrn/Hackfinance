// Pestaña Protección: Centinela integrado en Banco Demo (mensajes vigilados, comprobación manual y avisos).
import { api, el, icon, initials, speak, stopSpeaking, streamAnalysis, toast, LEVEL, CHANNEL, fmtShort } from "../common.js";
import { goTab, onRefresh, refresh, showScreen, store } from "./core.js";

const $ = (s) => document.querySelector(s);
let selectedFile = null;
let analyzing = false;
let shieldTimer = null;
const pending = []; // mensajes entrantes esperando análisis

const profile = () => store.profile;

// ------------------------------------------------------------ navegación
function show(screen) {
  showScreen("proteccion", screen);
  const h = $(`#tab-proteccion [data-screen="${screen}"] h2`);
  if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
}

// ------------------------------------------------------------ estado
function renderProfile() {
  const p = profile();
  if (!p) return;
  const on = !!p.proteccion_activa;
  $("#hero").classList.toggle("off", !on);
  $("#hero-icon use").setAttribute("href", `/icons.svg#${on ? "shield-check" : "shield-off"}`);
  $("#hero-title").textContent = on ? "Protección activada" : "Protección desactivada";
  $("#hero-sub").textContent = on
    ? "Reviso tus mensajes nuevos y te aviso si hay peligro."
    : "Ahora mismo no reviso tus mensajes. Actívala con el interruptor.";
  $("#set-proteccion").checked = on;
  $("#inbox-help").textContent = on
    ? "La protección está activada: reviso solos los mensajes nuevos."
    : "La protección está desactivada. Puedes activarla con el interruptor de arriba.";
}

function renderShield() {
  const b = $("#shield-banner");
  const escudo = store.bank?.escudo;
  clearInterval(shieldTimer);
  if (!escudo?.activo || !escudo.activo_hasta) { b.classList.add("hidden"); return; }
  const until = new Date(escudo.activo_hasta).getTime();
  const tick = () => {
    const left = Math.max(0, Math.round((until - Date.now()) / 1000));
    if (!left) { clearInterval(shieldTimer); b.classList.add("hidden"); refresh(); return; }
    const mm = String(Math.floor(left / 60)).padStart(2, "0");
    const ss = String(left % 60).padStart(2, "0");
    b.replaceChildren(icon("lock"), el("span", {},
      `Pagos a cuentas nuevas en revisión durante ${mm}:${ss}.`,
      escudo.motivo ? el("br") : null,
      escudo.motivo ? el("span", { class: "small" }, `Motivo: ${escudo.motivo}`) : null));
  };
  tick();
  b.classList.remove("hidden");
  shieldTimer = setInterval(tick, 1000);
}

export function onShieldEvent() {
  refresh().then(renderShield);
}

// ------------------------------------------------------------ contactos y avisos
function fillSettings() {
  const p = profile() || {};
  $("#set-voz").checked = !!p.leer_en_voz_alta;
  $("#set-escudo").checked = !!p.escudo_bancario;
  const f = p.familiar || {};
  $("#set-fam-nombre").value = f.nombre || "";
  $("#set-fam-relacion").value = f.relacion || "";
  $("#set-fam-tel").value = f.telefono || "";
  $("#set-voz-id").value = p.voz_id || "";
  renderContacts();
  const h = store.health;
  if (h) {
    $("#health").textContent = `IA: ${h.ia ? "activada (" + h.modelo + ")" : "modo básico sin IA"} · Voz ElevenLabs: ${h.voz ? "activada" : "voz del navegador"} · Avisos por Telegram: ${h.telegram ? "sí" : "no"}`;
  }
}

function renderContacts() {
  const p = profile();
  $("#contacts").replaceChildren(...(p?.contactos || []).map((c, i) =>
    el("span", { class: "chip" }, `${c.nombre} · ${c.telefono}`,
      el("button", { "aria-label": `Quitar a ${c.nombre}`, onclick: () => { p.contactos.splice(i, 1); renderContacts(); } }, icon("x")))));
}

async function saveSettings() {
  const p = profile() || {};
  const body = {
    leer_en_voz_alta: $("#set-voz").checked,
    escudo_bancario: $("#set-escudo").checked,
    voz_id: $("#set-voz-id").value.trim(),
    familiar: { nombre: $("#set-fam-nombre").value.trim(), relacion: $("#set-fam-relacion").value.trim(), telefono: $("#set-fam-tel").value.trim() },
    contactos: p.contactos || [],
  };
  try {
    await api("/api/perfil", { method: "PUT", json: body });
    await refresh();
    toast("Ajustes guardados");
    show("main");
  } catch (e) { toast("No se han podido guardar: " + e.message); }
}

// ------------------------------------------------------------ bandeja
async function loadInbox() {
  try {
    const msgs = await api("/api/mensajes");
    renderStats(msgs);
    $("#inbox").replaceChildren(...(msgs.length
      ? msgs.map(renderInboxItem)
      : [el("li", { class: "empty" }, icon("inbox"), "Todavía no hay mensajes.")]));
  } catch (e) { console.warn(e); }
}

function renderStats(msgs) {
  const revisados = msgs.filter((m) => m.analisis?.nivel).length;
  const peligros = msgs.filter((m) => ["rojo", "amarillo"].includes(m.analisis?.nivel)).length;
  $("#hero-stats").replaceChildren(
    el("span", { class: "stat" }, `${revisados} ${revisados === 1 ? "mensaje revisado" : "mensajes revisados"}`),
    el("span", { class: "stat" }, peligros ? `${peligros} ${peligros === 1 ? "peligro frenado" : "peligros frenados"}` : "Ningún peligro"));
}

function renderInboxItem(m) {
  const level = m.analisis?.nivel;
  const on = profile()?.proteccion_activa;
  const ini = initials(m.remitente || "");
  const badge = el("span", { class: `badge ${level || ""}`, "aria-hidden": "true" },
    level ? icon(LEVEL[level].icon) : (ini || icon(m.canal === "email" ? "mail" : "message")));
  const status = level ? m.analisis.titulo : (on ? "Pendiente de revisar" : "Sin revisar");
  return el("li", {},
    el("button", { onclick: () => openMessage(m), "aria-label": `Mensaje de ${m.remitente}. ${status}` },
      badge,
      el("div", { style: "min-width:0" },
        el("div", { class: "meta" }, el("span", { class: "from" }, m.remitente || "Desconocido"), el("span", { class: "time" }, fmtShort(m.fecha))),
        el("div", { class: "preview" }, m.texto),
        el("div", { class: "foot" },
          el("span", { class: `chip-status ${level || ""}` }, level ? LEVEL[level].label : (on ? "Revisando…" : "Sin revisar")),
          el("span", { class: "tag" }, CHANNEL[m.canal] || m.canal)))));
}

function openMessage(m) {
  if (m.resultado) { renderResult(m.resultado); show("result"); return; }
  const form = new FormData();
  form.append("texto", m.texto);
  form.append("remitente", m.remitente || "");
  form.append("canal", m.canal || "sms");
  form.append("mensaje_id", m.id);
  runAnalysis(form, { visible: true });
}

// ------------------------------------------------------------ comprobar a mano
function resetCheck() {
  $("#check-text").value = "";
  $("#check-sender").value = "";
  selectedFile = null;
  $("#file-chosen").textContent = "";
}

// ------------------------------------------------------------ grabar con el micrófono
let recorder = null;
let chunks = [];

async function toggleRecording(btn) {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia) { toast("Este navegador no permite grabar"); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    chunks = [];
    const label = btn.querySelector(".btn-label");
    const original = label.textContent;
    const useEl = btn.querySelector(".ac-icon use, .i use");
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      label.textContent = original;
      useEl?.setAttribute("href", "/icons.svg#mic");
      btn.classList.remove("recording");
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      const form = new FormData();
      form.append("canal", "manual");
      form.append("remitente", $("#check-sender").value.trim());
      form.append("archivo", blob, "grabacion.webm");
      runAnalysis(form, { visible: true });
    };
    recorder.start();
    label.textContent = "Parar y comprobar";
    useEl?.setAttribute("href", "/icons.svg#stop");
    btn.classList.add("recording");
    toast("Grabando… lee el mensaje en voz alta");
  } catch (e) {
    toast("No tengo permiso para usar el micrófono");
  }
}

// ------------------------------------------------------------ análisis
function addStep(ev) {
  const list = $("#steps");
  const prev = list.lastElementChild;
  if (prev && prev.dataset.state === "en_curso") {
    prev.dataset.state = "hecho";
    prev.querySelector(".st").replaceChildren(icon("check"));
  }
  const mark = ev.estado === "en_curso" ? el("span", { class: "spinner", "aria-hidden": "true" }) : icon(ev.estado === "aviso" ? "alert" : "check");
  list.append(el("li", { "data-state": ev.estado || "hecho" }, el("span", { class: "st" }, mark), el("span", { class: "txt" }, ev.texto)));
}

async function runAnalysis(form, { visible }) {
  if (analyzing) { toast("Espera, estoy terminando otra comprobación"); return null; }
  analyzing = true;
  if (visible) { $("#steps").replaceChildren(); show("progress"); }
  let result = null;
  let error = null;
  try {
    await streamAnalysis(form, (ev) => {
      if (ev.tipo === "paso" && visible) addStep(ev);
      else if (ev.tipo === "resultado") result = ev.datos;
      else if (ev.tipo === "error") error = ev.texto;
    });
  } catch (e) {
    error = "No he podido conectar. Revisa la conexión a internet.";
  } finally {
    analyzing = false;
  }
  if (error) {
    if (visible) { toast(error, 5000); show("main"); }
    return null;
  }
  await loadInbox();
  if (result?.escudo_activado) onShieldEvent();
  if (visible && result) {
    renderResult(result);
    show("result");
    if (profile()?.leer_en_voz_alta) speak(result.veredicto.mensaje_voz, { voiceId: profile().voz_id });
  }
  processQueue();
  return result;
}

function verdictCard(result, { compact = false } = {}) {
  const v = result.veredicto;
  const lv = LEVEL[v.nivel];
  const p = profile();
  const fam = p?.familiar || {};
  const famName = fam.nombre || "tu familiar";
  const actions = el("div", { class: "actions" + (compact ? "" : " two") });
  actions.append(el("button", { class: "btn btn-primary", onclick: () => speak(v.mensaje_voz, { voiceId: p?.voz_id }) }, icon("volume"), "Escuchar"));
  if ((v.acciones || []).includes("llamar_familiar") && fam.telefono) {
    actions.append(el("a", { class: "btn btn-ok", href: `tel:${fam.telefono.replace(/\s/g, "")}` }, icon("phone"), `Llamar a ${famName}`));
  }
  if ((v.acciones || []).includes("avisar_familiar") && result.alerta_id) {
    actions.append(el("button", { class: "btn btn-outline", onclick: async (e) => {
      const b = e.currentTarget;
      b.disabled = true;
      try { await api(`/api/alertas/${result.alerta_id}/avisar`, { method: "POST" }); toast(`Hemos avisado a ${famName}`); }
      catch (err) { toast("No se ha podido avisar"); b.disabled = false; }
    } }, icon("message"), `Avisar a ${famName}`));
  }
  if ((v.acciones || []).includes("reportar")) {
    actions.append(el("button", { class: "btn btn-outline", onclick: async (e) => {
      const ent = result.detalle_reglas?.entidades || {};
      const telefonos = [...(ent.telefonos || [])];
      if (result.remitente && /\d{6,}/.test(result.remitente.replace(/\s/g, ""))) telefonos.push(result.remitente);
      e.currentTarget.disabled = true;
      await api("/api/reportar", { method: "POST", json: { telefonos, enlaces: ent.enlaces || [] } });
      toast("Gracias. Así protegemos a más personas");
    } }, icon("flag"), "Reportar como timo"));
  }

  const tools = v.herramientas_usadas || [];
  const evIcon = v.nivel === "verde" ? "check" : v.nivel === "rojo" ? "x" : "alert";
  const body = el("div", { class: "verdict-body" },
    el("p", {}, v.explicacion),
    v.pruebas?.length ? el("div", {}, el("h3", {}, "Lo que he comprobado"), el("ul", { class: "evidence" }, v.pruebas.map((x) => el("li", {}, icon(evIcon), el("span", {}, x))))) : null,
    el("p", { class: "advice" }, icon("sparkles"), el("span", {}, v.consejo)),
    result.escudo_activado ? el("div", { class: "banner shield" }, icon("lock"), el("span", {}, "Durante un rato, Banco Demo revisará los pagos a cuentas nuevas para protegerte.")) : null,
    actions,
    compact ? null : el("details", {},
      el("summary", {}, "Ver cómo lo he investigado"),
      el("p", { class: "small muted" }, `Análisis con ${result.fuente === "ia" ? "IA (" + (v.modelo || "Claude") + ")" : "reglas automáticas"} en ${(result.latencia_ms / 1000).toFixed(1)} s.`),
      tools.length ? el("ul", { class: "small" }, tools.map((t) => el("li", {}, `${t.herramienta}: ${t.resumen}`))) : null,
      result.texto ? el("p", { class: "small muted" }, "Mensaje analizado: «" + result.texto.slice(0, 400) + "»") : null));
  return el("article", { class: `card verdict ${v.nivel}`, "aria-live": "assertive" },
    el("header", { class: "verdict-head" },
      el("div", { class: "verdict-icon", "aria-hidden": "true" }, icon(lv.icon)),
      el("h2", { id: compact ? "overlay-title" : "result-title" }, v.titulo),
      v.tipo_estafa ? el("p", { class: "tag" }, v.tipo_estafa) : null,
      el("div", { class: "meter", role: "img", "aria-label": `Riesgo ${v.puntuacion} de 100` }, el("span", { style: `width:${v.puntuacion}%` })),
      el("p", { class: "risk" }, `Riesgo: ${v.puntuacion} de 100`)),
    body);
}

function renderResult(result) {
  $("#verdict").replaceChildren(verdictCard(result));
}

// ------------------------------------------------------------ alerta para mensajes entrantes
function showOverlay(result) {
  const card = verdictCard(result, { compact: true });
  card.classList.add("sheet");
  const close = el("button", { class: "btn btn-outline btn-big", onclick: hideOverlay }, icon("check"), "Entendido");
  card.querySelector(".verdict-body").append(close);
  $("#overlay").replaceChildren(card);
  $("#overlay").classList.remove("hidden");
  const title = card.querySelector("h2");
  title.setAttribute("tabindex", "-1");
  title.focus({ preventScroll: true });
  card.scrollTop = 0;
  if (navigator.vibrate) navigator.vibrate([300, 150, 300, 150, 300]);
  if (profile()?.leer_en_voz_alta) speak(result.veredicto.mensaje_voz, { voiceId: profile().voz_id });
}
function hideOverlay() { stopSpeaking(); $("#overlay").classList.add("hidden"); }

async function processQueue() {
  if (analyzing || !pending.length) return;
  const m = pending.shift();
  const form = new FormData();
  form.append("texto", m.texto);
  form.append("remitente", m.remitente || "");
  form.append("canal", m.canal || "sms");
  form.append("mensaje_id", m.id);
  const res = await runAnalysis(form, { visible: false });
  if (res && res.veredicto.nivel !== "verde") showOverlay(res);
}

export function onIncomingMessage(m) {
  loadInbox();
  if (!profile()?.proteccion_activa) return;
  toast(`Nuevo mensaje de ${m.remitente || "desconocido"}: lo estoy revisando…`);
  pending.push(m);
  processQueue();
}

// ------------------------------------------------------------ contenido compartido (Web Share Target)
export async function handleShared() {
  const params = new URLSearchParams(location.search);
  const id = params.get("compartido");
  if (!id) return;
  history.replaceState({}, "", "/");
  goTab("proteccion");
  try {
    const data = await api(`/api/compartido/${id}`);
    const form = new FormData();
    form.append("texto", data.texto || "");
    form.append("canal", "compartido");
    if (data.archivo) {
      const bytes = Uint8Array.from(atob(data.archivo.datos), (c) => c.charCodeAt(0));
      form.append("archivo", new Blob([bytes], { type: data.archivo.tipo }), data.archivo.nombre);
    }
    runAnalysis(form, { visible: true });
  } catch (e) { toast("No he podido recibir lo que has compartido"); }
}

// ------------------------------------------------------------ arranque
export function initProteccion() {
  let lastShield = null;
  onRefresh(() => {
    renderProfile();
    const key = JSON.stringify(store.bank?.escudo || null);
    if (key !== lastShield) { lastShield = key; renderShield(); }
  });
  $("#basic-mode").classList.toggle("hidden", store.health?.ia !== false);

  document.querySelectorAll("[data-prot-back]").forEach((b) => b.addEventListener("click", () => { stopSpeaking(); show("main"); }));
  $("#set-proteccion").addEventListener("change", async (e) => {
    try {
      await api("/api/perfil", { method: "PUT", json: { proteccion_activa: e.target.checked } });
      await refresh();
      loadInbox();
    } catch (err) { toast("No se ha podido cambiar: " + err.message); e.target.checked = !e.target.checked; }
  });
  $("#btn-contacts").addEventListener("click", fillSettings);
  $("#btn-add-contact").addEventListener("click", () => {
    const p = profile();
    const nombre = $("#new-contact-name").value.trim();
    const telefono = $("#new-contact-tel").value.trim();
    if (!p) return;
    if (!nombre || !telefono) { toast("Escribe el nombre y el teléfono"); return; }
    p.contactos = [...(p.contactos || []), { nombre, telefono, relacion: $("#new-contact-rel").value.trim() }];
    ["#new-contact-name", "#new-contact-tel", "#new-contact-rel"].forEach((s) => ($(s).value = ""));
    renderContacts();
  });
  $("#btn-save-settings").addEventListener("click", saveSettings);

  $("#btn-check").addEventListener("click", () => { resetCheck(); show("check"); $("#check-text").focus(); });
  for (const id of ["#file-image", "#file-audio"]) {
    $(id).addEventListener("change", (e) => {
      selectedFile = e.target.files[0] || null;
      $("#file-chosen").textContent = selectedFile ? `Archivo añadido: ${selectedFile.name}` : "";
    });
  }
  $("#btn-analyze").addEventListener("click", () => {
    const texto = $("#check-text").value.trim();
    if (!texto && !selectedFile) { toast("Pega el mensaje o añade una captura o nota de voz"); return; }
    const form = new FormData();
    form.append("texto", texto);
    form.append("remitente", $("#check-sender").value.trim());
    form.append("canal", "manual");
    if (selectedFile) form.append("archivo", selectedFile, selectedFile.name);
    runAnalysis(form, { visible: true });
  });
  $("#btn-record").addEventListener("click", (e) => toggleRecording(e.currentTarget));
  $("#btn-record-home").addEventListener("click", (e) => toggleRecording(e.currentTarget));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideOverlay(); });

  loadInbox();
}
