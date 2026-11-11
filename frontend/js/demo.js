// Panel del presentador: envía mensajes simulados al móvil durante la demo.
import { api, el, toast, icon, CHANNEL } from "./common.js";

const $ = (s) => document.querySelector(s);

async function send(m, card) {
  await api("/api/demo/entrante", { method: "POST", json: { canal: m.canal, remitente: m.remitente, texto: m.texto } });
  toast(`Enviado: «${(m.titulo || m.texto).slice(0, 40)}…»`);
  if (card) { card.classList.remove("sent"); void card.offsetWidth; card.classList.add("sent"); }
}

function statusPill(ok, label, okText, koText) {
  return el("span", { class: "pill " + (ok ? "on" : "warn") }, el("span", { class: "dot" }), `${label}: ${ok ? okText : koText}`);
}

// ------------------------------------------------------------ móvil en pantalla
function readPhonePref() {
  try { return localStorage.getItem("centinela-demo-movil") !== "no"; } catch (_) { return true; }
}
function setPhone(on) {
  try { localStorage.setItem("centinela-demo-movil", on ? "si" : "no"); } catch (_) { /* sin almacenamiento */ }
  $("#toggle-phone").checked = on;
  $("#phone").classList.toggle("hidden", !on);
  $("#phone-off").classList.toggle("hidden", on);
  const frame = $("#phone-frame");
  if (on && !frame.getAttribute("src")) frame.setAttribute("src", "/");
  if (!on) frame.removeAttribute("src");
}
$("#toggle-phone").addEventListener("change", (e) => setPhone(e.target.checked));

async function init() {
  // En pantallas estrechas la vista previa no se muestra.
  setPhone(readPhonePref() && window.matchMedia("(min-width: 1001px)").matches);

  const h = await api("/api/health");
  $("#health").replaceChildren(
    statusPill(h.ia, "IA", h.modelo, "modo local de demostración"),
    statusPill(h.voz, "Voz ElevenLabs", "activada", "voz local si está disponible"),
    statusPill(h.telegram, "Telegram", "activado", "no configurado"),
  );
  const samples = await api("/api/demo/ejemplos");
  $("#samples").replaceChildren(...samples.map((m) => {
    const card = el("article", { class: `scenario ${m.tipo}` });
    card.append(
      el("div", { class: "s-head" },
        el("h3", {}, m.titulo),
        el("span", { class: `chip-status ${m.tipo === "estafa" ? "rojo" : "verde"}` }, m.tipo === "estafa" ? "Estafa" : "Legítimo")),
      el("p", { class: "s-text" }, m.texto),
      el("div", { class: "s-from" }, icon(m.canal === "whatsapp" ? "message" : m.canal === "email" ? "mail" : "smartphone"), `${CHANNEL[m.canal] || m.canal} · ${m.remitente}`),
      el("div", { class: "s-btns" },
        el("button", { class: "btn btn-small btn-primary", onclick: () => send(m, card) }, icon("send"), "Enviar"),
        el("button", { class: "btn btn-small btn-outline", "aria-label": `Editar «${m.titulo}»`, onclick: () => {
          $("#c-sender").value = m.remitente; $("#c-channel").value = m.canal; $("#c-text").value = m.texto;
          $("#custom-title").scrollIntoView({ behavior: "smooth", block: "center" });
        } }, icon("pencil"))));
    return card;
  }));
}

$("#btn-send").addEventListener("click", () => {
  const texto = $("#c-text").value.trim();
  if (!texto) { toast("Escribe el texto del mensaje"); return; }
  send({ canal: $("#c-channel").value, remitente: $("#c-sender").value.trim(), texto });
});
$("#btn-reset").addEventListener("click", async () => {
  if (!confirm("¿Reiniciar la demo? Se borran mensajes, alertas y movimientos del banco.")) return;
  await api("/api/demo/reset", { method: "POST" });
  toast("Demo reiniciada");
});

init();
