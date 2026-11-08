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

export function toast(text, ms = 3500) {
  const t = el("div", { class: "toast", role: "status" }, text);
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

export const LEVEL = {
  verde: { icon: "✅", label: "Tranquilo/a", color: "var(--verde)" },
  amarillo: { icon: "⚠️", label: "Cuidado", color: "var(--amarillo-accent)" },
  rojo: { icon: "⛔", label: "Peligro", color: "var(--rojo)" },
};

export function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
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
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "es-ES";
    u.rate = 0.92;
    const voice = speechSynthesis.getVoices().find((v) => v.lang && v.lang.startsWith("es"));
    if (voice) u.voice = voice;
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
