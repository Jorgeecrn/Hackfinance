// Panel del presentador: envía mensajes simulados al móvil durante la demo.
import { api, el, toast } from "./common.js";

const $ = (s) => document.querySelector(s);

async function send(m) {
  await api("/api/demo/entrante", { method: "POST", json: { canal: m.canal, remitente: m.remitente, texto: m.texto } });
  toast(`Enviado: «${(m.titulo || m.texto).slice(0, 40)}…»`);
}

async function init() {
  const h = await api("/api/health");
  $("#health").textContent = `IA: ${h.ia ? "✅ " + h.modelo : "⚠️ modo básico (sin ANTHROPIC_API_KEY)"} · Voz ElevenLabs: ${h.voz ? "✅" : "⚠️ voz del navegador"} · Telegram: ${h.telegram ? "✅" : "—"}`;
  const samples = await api("/api/demo/ejemplos");
  $("#samples").replaceChildren(...samples.map((m) => el("tr", {},
    el("td", {}, el("strong", {}, m.titulo), el("div", { class: "small muted" }, m.texto.slice(0, 110) + "…")),
    el("td", {}, el("span", { class: "tag" }, m.tipo)),
    el("td", { class: "small" }, m.remitente),
    el("td", {}, el("div", { class: "row" },
      el("button", { class: "btn btn-small btn-primary", onclick: () => send(m) }, "Enviar"),
      el("button", { class: "btn btn-small btn-outline", onclick: () => { $("#c-sender").value = m.remitente; $("#c-channel").value = m.canal; $("#c-text").value = m.texto; window.scrollTo({ top: 0, behavior: "smooth" }); } }, "Editar"))))));
}

$("#btn-send").addEventListener("click", () => {
  const texto = $("#c-text").value.trim();
  if (!texto) { toast("Escribe el texto del mensaje"); return; }
  send({ canal: $("#c-channel").value, remitente: $("#c-sender").value.trim(), texto });
});
$("#btn-reset").addEventListener("click", async () => {
  if (!confirm("¿Reiniciar la demo?")) return;
  await api("/api/demo/reset", { method: "POST" });
  toast("Demo reiniciada");
});

init();
