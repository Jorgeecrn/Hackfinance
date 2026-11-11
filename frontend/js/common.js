// Utilidades compartidas por todas las pantallas.

export async function api(path, { method = "GET", json, form } = {}) {
  const opts = { method, headers: {} };
  if (json !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(json);
  } else if (form) {
    opts.body = form;
  }
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const msg = (data && (data.detail || data.error)) || `Error ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

/** POST multipart que devuelve eventos SSE (pasos de la investigación). */
export async function streamAnalysis(form, onEvent) {
  const res = await fetch("/api/analizar/stream", { method: "POST", body: form });
  if (!res.ok || !res.body) throw new Error(`Error ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (line) {
        try { onEvent(JSON.parse(line.slice(5).trim())); } catch (e) { console.warn(e); }
      }
    }
  }
}

/** Suscripción a eventos en tiempo real con reconexión automática. */
export function subscribe(channel, handlers) {
  const es = new EventSource(`/api/eventos/${channel}`);
  for (const [name, fn] of Object.entries(handlers)) {
    es.addEventListener(name, (ev) => {
      try { fn(JSON.parse(ev.data)); } catch (e) { console.warn(e); }
    });
  }
  return es;
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";

/** Icono de línea del sprite /icons.svg. */
export function icon(name, cls = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", ("i " + cls).trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `/icons.svg#${name}`);
  svg.append(use);
  return svg;
}

/** Iniciales para avatares («Lucía López» → «LL»; números → icono). */
export function initials(name = "") {
  const clean = name.replace(/\(.*?\)/g, "").trim();
  if (!clean || /^[+\d\s]+$/.test(clean)) return null;
  return clean.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

/** Tema claro/oscuro (preferencia local del dispositivo). */
export function getTheme() {
  try { return localStorage.getItem("centinela-tema") || "light"; } catch (_) { return "light"; }
}
export function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("centinela-tema", theme); } catch (_) { /* sin almacenamiento */ }
}
document.documentElement.dataset.theme = getTheme();

export function toast(text, ms = 3500) {
  const t = el("div", { class: "toast", role: "status" }, text);
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

export const LEVEL = {
  verde: { icon: "check-circle", label: "Sin señales en lo revisado", color: "var(--verde)" },
  amarillo: { icon: "alert", label: "Cuidado", color: "var(--amarillo-accent)" },
  rojo: { icon: "octagon", label: "Timo", color: "var(--rojo)" },
};

export function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Hora si es de hoy; si no, día y mes. */
export function fmtShort(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  return today ? d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
}

export function fmtMoney(n) {
  return Number(n).toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export const CHANNEL = { sms: "SMS", whatsapp: "WhatsApp", email: "Correo", manual: "Comprobado a mano", compartido: "Compartido" };

// ------------------------------------------------------------ voz
let currentAudio = null;

export function stopSpeaking() {
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

/** Lee un texto en voz alta: ElevenLabs si está configurado; si no, la voz del navegador. */
export async function speak(text, { voiceId } = {}) {
  stopSpeaking();
  if (!text) return;
  try {
    const res = await fetch("/api/voz", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto: text, voz_id: voiceId || null }),
    });
    if (res.status === 200) {
      const blob = await res.blob();
      currentAudio = new Audio(URL.createObjectURL(blob));
      await currentAudio.play();
      return;
    }
  } catch (e) {
    console.warn("Voz ElevenLabs no disponible", e);
  }
  if ("speechSynthesis" in window) {
    const voice = speechSynthesis.getVoices().find((v) => v.localService && v.lang?.startsWith("es"));
    if (!voice) return; // El resultado escrito sigue disponible.
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "es-ES";
    u.rate = 0.92;
    u.voice = voice;
    speechSynthesis.speak(u);
  }
}

/** Los navegadores bloquean el audio hasta el primer toque: lo desbloqueamos. */
export function unlockAudioOnFirstTouch() {
  const unlock = () => {
    try {
      const a = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=");
      a.play().catch(() => {});
      if ("speechSynthesis" in window) speechSynthesis.getVoices();
    } catch (_) { /* nada */ }
    window.removeEventListener("pointerdown", unlock);
  };
  window.addEventListener("pointerdown", unlock);
}
