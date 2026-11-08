// App de la persona protegida (PWA).
import {
  api, streamAnalysis, subscribe, el, toast, LEVEL, fmtTime, CHANNEL, speak, stopSpeaking, unlockAudioOnFirstTouch,
} from "./common.js";

const $ = (s) => document.querySelector(s);
const views = ["home", "check", "progress", "result", "settings"];
let profile = null;
let health = null;
let selectedFile = null;
let analyzing = false;
const pending = []; // mensajes entrantes esperando análisis

// ------------------------------------------------------------ navegación
function show(view) {
  for (const v of views) $(`#view-${v}`).classList.toggle("hidden", v !== view);
  window.scrollTo({ top: 0 });
  const h = $(`#view-${view} h1, #view-${view} h2`);
  if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
}
document.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => { stopSpeaking(); show("home"); }));

// ------------------------------------------------------------ perfil
async function loadProfile() {
  profile = await api("/api/perfil");
  document.documentElement.dataset.letra = profile.tamano_letra || "grande";
  $("#greeting").textContent = `Hola, ${profile.nombre || ""}`.trim();
  const pill = $("#protection-pill");
  pill.className = "pill " + (profile.proteccion_activa ? "on" : "off");
  pill.querySelector("span:last-child").textContent = profile.proteccion_activa ? "Protegido/a" : "Sin protección";
  pill.setAttribute("aria-label", profile.proteccion_activa ? "Protección contra estafas activada" : "Protección contra estafas desactivada");
  $("#inbox-help").textContent = profile.proteccion_activa
    ? "La protección está activada: reviso solos los mensajes nuevos."
    : "La protección está desactivada. Puedes activarla en Ajustes ⚙️.";
}

function fillSettings() {
  $("#set-proteccion").checked = !!profile.proteccion_activa;
  $("#set-voz").checked = !!profile.leer_en_voz_alta;
  $("#set-escudo").checked = !!profile.escudo_bancario;
  $("#set-nombre").value = profile.nombre || "";
  $("#set-letra").value = profile.tamano_letra || "grande";
  const f = profile.familiar || {};
  $("#set-fam-nombre").value = f.nombre || "";
  $("#set-fam-relacion").value = f.relacion || "";
  $("#set-fam-tel").value = f.telefono || "";
  $("#set-voz-id").value = profile.voz_id || "";
  renderContacts();
  if (health) {
    $("#health").textContent = `IA: ${health.ia ? "activada (" + health.modelo + ")" : "modo básico sin IA"} · Voz ElevenLabs: ${health.voz ? "activada" : "voz del navegador"} · Avisos por Telegram: ${health.telegram ? "sí" : "no"}`;
  }
}

function renderContacts() {
  const box = $("#contacts");
  box.replaceChildren(...(profile.contactos || []).map((c, i) =>
    el("span", { class: "chip" }, `${c.nombre} · ${c.telefono}`,
      el("button", { "aria-label": `Quitar a ${c.nombre}`, onclick: () => { profile.contactos.splice(i, 1); renderContacts(); } }, "✕"))));
}

$("#btn-add-contact").addEventListener("click", () => {
  const nombre = $("#new-contact-name").value.trim();
  const telefono = $("#new-contact-tel").value.trim();
  if (!nombre || !telefono) { toast("Escribe el nombre y el teléfono"); return; }
  profile.contactos = [...(profile.contactos || []), { nombre, telefono, relacion: $("#new-contact-rel").value.trim() }];
  ["#new-contact-name", "#new-contact-tel", "#new-contact-rel"].forEach((s) => ($(s).value = ""));
  renderContacts();
});

$("#btn-settings").addEventListener("click", () => { fillSettings(); show("settings"); });
$("#set-letra").addEventListener("change", (e) => (document.documentElement.dataset.letra = e.target.value));

$("#btn-save-settings").addEventListener("click", async () => {
  const body = {
    nombre: $("#set-nombre").value.trim(),
    proteccion_activa: $("#set-proteccion").checked,
    leer_en_voz_alta: $("#set-voz").checked,
    escudo_bancario: $("#set-escudo").checked,
    tamano_letra: $("#set-letra").value,
    voz_id: $("#set-voz-id").value.trim(),
    familiar: { nombre: $("#set-fam-nombre").value.trim(), relacion: $("#set-fam-relacion").value.trim(), telefono: $("#set-fam-tel").value.trim() },
    contactos: profile.contactos || [],
  };
  try {
    await api("/api/perfil", { method: "PUT", json: body });
    await loadProfile();
    toast("Ajustes guardados");
    show("home");
  } catch (e) { toast("No se han podido guardar: " + e.message); }
});

// ------------------------------------------------------------ bandeja
async function loadInbox() {
  const msgs = await api("/api/mensajes");
  const list = $("#inbox");
  if (!msgs.length) {
    list.replaceChildren(el("li", {}, el("p", { class: "muted", style: "padding:12px 0" }, "Todavía no hay mensajes.")));
    return;
  }
  list.replaceChildren(...msgs.map(renderInboxItem));
}

function renderInboxItem(m) {
  const level = m.analisis?.nivel;
  const badge = el("span", { class: `badge ${level || ""}`, "aria-hidden": "true" }, level ? LEVEL[level].icon : "✉️");
  const status = level ? m.analisis.titulo : (profile?.proteccion_activa ? "Pendiente de revisar" : "Sin revisar");
  return el("li", {},
    el("button", { onclick: () => openMessage(m), "aria-label": `Mensaje de ${m.remitente}. ${status}` },
      badge,
      el("div", {},
        el("div", { class: "row" }, el("span", { class: "from" }, m.remitente || "Desconocido"), el("span", { class: "tag" }, CHANNEL[m.canal] || m.canal), el("span", { class: "muted small" }, fmtTime(m.fecha))),
        el("div", { class: "preview" }, m.texto),
        el("div", { class: "small", style: `font-weight:700;color:${level ? LEVEL[level].color : "var(--text-soft)"}` }, status))));
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

// ------------------------------------------------------------ comprobar manualmente
$("#btn-check").addEventListener("click", () => { resetCheck(); show("check"); $("#check-text").focus(); });

function resetCheck() {
  $("#check-text").value = "";
  $("#check-sender").value = "";
  selectedFile = null;
  $("#file-chosen").textContent = "";
}

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
    const original = btn.textContent;
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      btn.textContent = original;
      btn.classList.remove("btn-danger");
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      const form = new FormData();
      form.append("canal", "manual");
      form.append("remitente", $("#check-sender").value.trim());
      form.append("archivo", blob, "grabacion.webm");
      runAnalysis(form, { visible: true });
    };
    recorder.start();
    btn.textContent = "⏹️ Parar y comprobar";
    btn.classList.add("btn-danger");
    toast("Grabando… lee el mensaje en voz alta");
  } catch (e) {
    toast("No tengo permiso para usar el micrófono");
  }
}
$("#btn-record").addEventListener("click", (e) => toggleRecording(e.currentTarget));
$("#btn-record-home").addEventListener("click", (e) => toggleRecording(e.currentTarget));

// ------------------------------------------------------------ análisis
function addStep(ev) {
  const list = $("#steps");
  const prev = list.lastElementChild;
  if (prev && prev.dataset.state === "en_curso") {
    prev.dataset.state = "hecho";
    prev.querySelector(".st").textContent = "✔️";
  }
  const icon = ev.estado === "en_curso" ? el("span", { class: "spinner", "aria-hidden": "true" }) : (ev.estado === "aviso" ? "⚠️" : "✔️");
  list.append(el("li", { "data-state": ev.estado || "hecho" }, el("span", { class: "st" }, icon), el("span", {}, ev.texto)));
}

async function runAnalysis(form, { visible }) {
  if (analyzing) { toast("Espera, estoy terminando otra comprobación"); return; }
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
    if (visible) { toast(error, 5000); show("home"); }
    return null;
  }
  await loadInbox();
  if (visible && result) {
    renderResult(result);
    show("result");
    if (profile?.leer_en_voz_alta) speak(result.veredicto.mensaje_voz, { voiceId: profile.voz_id });
  }
  processQueue();
  return result;
}

function verdictCard(result, { compact = false } = {}) {
  const v = result.veredicto;
  const lv = LEVEL[v.nivel];
  const fam = profile?.familiar || {};
  const famName = fam.nombre || "tu familiar";
  const actions = el("div", { class: "actions" + (compact ? "" : " two") });
  actions.append(el("button", { class: "btn btn-primary", onclick: () => speak(v.mensaje_voz, { voiceId: profile?.voz_id }) }, "🔊 Escuchar"));
  if ((v.acciones || []).includes("llamar_familiar") && fam.telefono) {
    actions.append(el("a", { class: "btn btn-ok", href: `tel:${fam.telefono.replace(/\s/g, "")}` }, `📞 Llamar a ${famName}`));
  }
  if ((v.acciones || []).includes("avisar_familiar") && result.alerta_id) {
    actions.append(el("button", { class: "btn btn-outline", onclick: async (e) => {
      e.currentTarget.disabled = true;
      try { await api(`/api/alertas/${result.alerta_id}/avisar`, { method: "POST" }); toast(`Hemos avisado a ${famName}`); }
      catch (err) { toast("No se ha podido avisar"); e.currentTarget.disabled = false; }
    } }, `💬 Avisar a ${famName}`));
  }
  if ((v.acciones || []).includes("reportar")) {
    actions.append(el("button", { class: "btn btn-outline", onclick: async (e) => {
      const ent = result.detalle_reglas?.entidades || {};
      const telefonos = [...(ent.telefonos || [])];
      if (result.remitente && /\d{6,}/.test(result.remitente.replace(/\s/g, ""))) telefonos.push(result.remitente);
      e.currentTarget.disabled = true;
      await api("/api/reportar", { method: "POST", json: { telefonos, enlaces: ent.enlaces || [] } });
      toast("Gracias. Así protegemos a más personas");
    } }, "🚩 Reportar como timo"));
  }

  const steps = (result.pasos || []);
  const tools = v.herramientas_usadas || [];
  return el("article", { class: `card verdict ${v.nivel}`, "aria-live": "assertive" },
    el("div", { class: "icon", "aria-hidden": "true" }, lv.icon),
    el("h2", { id: compact ? "overlay-title" : "result-title" }, v.titulo),
    v.tipo_estafa ? el("p", { class: "tag" }, v.tipo_estafa) : null,
    el("div", { class: "meter", role: "img", "aria-label": `Riesgo ${v.puntuacion} de 100` }, el("span", { style: `width:${v.puntuacion}%;background:${lv.color}` })),
    el("p", { class: "small muted" }, `Riesgo: ${v.puntuacion}/100`),
    el("p", {}, v.explicacion),
    v.pruebas?.length ? el("div", {}, el("h3", {}, "Lo que he comprobado"), el("ul", { class: "evidence" }, v.pruebas.map((p) => el("li", {}, p)))) : null,
    el("p", { class: "advice" }, "👉 " + v.consejo),
    result.escudo_activado ? el("div", { class: "banner shield" }, "🛡️ He activado el escudo bancario: tu banco pausará un rato las transferencias a cuentas nuevas.") : null,
    actions,
    compact ? null : el("details", {},
      el("summary", {}, "Ver cómo lo he investigado"),
      el("p", { class: "small muted" }, `Análisis con ${result.fuente === "ia" ? "IA (" + (v.modelo || "Claude") + ")" : "reglas automáticas"} en ${(result.latencia_ms / 1000).toFixed(1)} s.`),
      tools.length ? el("ul", { class: "small" }, tools.map((t) => el("li", {}, `${t.herramienta}: ${t.resumen}`))) : null,
      result.texto ? el("p", { class: "small muted" }, "Mensaje analizado: «" + result.texto.slice(0, 400) + "»") : null),
  );
}

function renderResult(result) {
  $("#result").replaceChildren(verdictCard(result));
}

// ------------------------------------------------------------ alerta para mensajes entrantes
function showOverlay(result) {
  const card = verdictCard(result, { compact: true });
  card.classList.add("sheet");
  const close = el("button", { class: "btn btn-outline btn-big", onclick: hideOverlay }, "Entendido");
  card.append(close);
  $("#overlay").replaceChildren(card);
  $("#overlay").classList.remove("hidden");
  const title = card.querySelector("h2");
  title.setAttribute("tabindex", "-1");
  title.focus({ preventScroll: true });
  card.scrollTop = 0;
  if (navigator.vibrate) navigator.vibrate([300, 150, 300, 150, 300]);
  if (profile?.leer_en_voz_alta) speak(result.veredicto.mensaje_voz, { voiceId: profile.voz_id });
}
function hideOverlay() { stopSpeaking(); $("#overlay").classList.add("hidden"); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideOverlay(); });

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

function onIncoming(m) {
  loadInbox();
  if (!profile?.proteccion_activa) return;
  toast(`Nuevo mensaje de ${m.remitente || "desconocido"}: lo estoy revisando…`);
  pending.push(m);
  processQueue();
}

// ------------------------------------------------------------ escudo bancario
async function refreshShield() {
  try {
    const bank = await api("/api/banco");
    const b = $("#shield-banner");
    if (bank.escudo.activo) {
      const until = new Date(bank.escudo.activo_hasta).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
      b.textContent = `🛡️ Escudo bancario activo hasta las ${until}: las transferencias a cuentas nuevas necesitan el visto bueno de ${profile?.familiar?.nombre || "tu familiar"}.`;
      b.classList.remove("hidden");
    } else b.classList.add("hidden");
  } catch (_) { /* sin banco */ }
}

// ------------------------------------------------------------ contenido compartido (Web Share Target)
async function handleShared() {
  const params = new URLSearchParams(location.search);
  const id = params.get("compartido");
  if (!id) return;
  history.replaceState({}, "", "/");
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
async function init() {
  unlockAudioOnFirstTouch();
  try { health = await api("/api/health"); } catch (_) { /* sin servidor */ }
  await loadProfile();
  await loadInbox();
  refreshShield();
  subscribe("usuario", {
    mensaje: onIncoming,
    perfil: () => loadProfile(),
    escudo: () => refreshShield(),
    transferencia_retenida: (tx) => toast(`🛡️ Hemos retenido una transferencia de ${tx.importe} € a una cuenta nueva`, 6000),
    reset: () => location.reload(),
  });
  handleShared();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

init().catch((e) => { console.error(e); toast("No se ha podido cargar la aplicación"); });
