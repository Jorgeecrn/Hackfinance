// Panel del presentador: llamada simulada, reinicio y aviso de configuración.
import { api, toast } from "../common.js";

const $ = (s) => document.querySelector(s);
const BASE = "/api/llamada";
let callActive = false;

function render(s) {
  callActive = s.callActive;
  $("#call-box").classList.toggle("on", callActive);
  const btn = $("#call-toggle");
  btn.setAttribute("aria-pressed", String(callActive));
  btn.className = callActive ? "btn btn-danger" : "btn btn-primary";
  btn.querySelector("span").textContent = callActive ? "Colgar" : "Activar";
  $("#no-key").classList.toggle("hidden", s.agentEnabled);
  $("#model").textContent = s.agentEnabled ? `Agente: ${s.model}` : "Agente externo apagado";
}

async function refresh() {
  try { render(await api(`${BASE}/state`)); } catch (e) { console.warn(e); }
}

$("#call-toggle").addEventListener("click", async () => {
  try {
    await api(`${BASE}/demo/call`, { method: "POST", json: { active: !callActive } });
    refresh();
  } catch (e) { toast(e.message); }
});

$("#reset").addEventListener("click", async () => {
  try {
    await api(`${BASE}/demo/reset`, { method: "POST" });
    $("#reset-msg").textContent = "Demo reiniciada";
    setTimeout(() => { $("#reset-msg").textContent = ""; }, 2500);
    refresh();
  } catch (e) { toast(e.message); }
});

refresh();
setInterval(refresh, 2000);
