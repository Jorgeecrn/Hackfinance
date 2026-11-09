// App del cliente de Banco Demo con el escudo de llamada.
import { api, el, fmtMoney, fmtShort, toast } from "../common.js";

const $ = (s) => document.querySelector(s);
const BASE = "/api/llamada";

// Copia de backend/app/llamada/seed.py (PRESETS) para rellenar la demo.
const PRESETS = {
  normal: { beneficiaryName: "Javier López", iban: "ES66 2100 0418 4012 3456 7891", amount: 200, concept: "Ayuda mensual", ibanPasted: false },
  casero: { beneficiaryName: "Antonio Ruiz", iban: "ES62 0182 2370 4202 0150 4358", amount: 600, concept: "Alquiler noviembre", ibanPasted: false },
  estafa: { beneficiaryName: "Cuenta segura Banco Demo", iban: "ES49 2038 3000 0010 0012 3456", amount: 8500, concept: "Protección de fondos", ibanPasted: true },
};
const RESULT_ICON = { execute: "check-circle", hold: "octagon", review: "clock" };

let state = null;
let ibanPasted = false;
let conversationId = null;

function show(id) {
  document.querySelectorAll(".ll-screen").forEach((s) => s.classList.toggle("hidden", s.id !== id));
}

function renderState(s) {
  state = s;
  $("#client-name").textContent = s.client.name;
  $("#bal-corriente").textContent = fmtMoney(s.accounts.corriente.balance);
  $("#bal-ahorro").textContent = fmtMoney(s.accounts.ahorro.balance);
  $("#call-banner").classList.toggle("hidden", !s.callActive);
  const list = $("#movements");
  list.replaceChildren(...s.movements.slice(0, 8).map((m) => {
    const out = m.type === "transfer_out";
    return el("li", {},
      el("span", {}, out ? (m.name || "Transferencia") : "Traspaso desde ahorro", el("br"), el("span", { class: "muted small" }, fmtShort(m.ts))),
      el("span", { class: out ? "neg" : "pos" }, (out ? "−" : "+") + fmtMoney(m.amount)));
  }));
}

async function refresh() {
  try { renderState(await api(`${BASE}/state`)); } catch (e) { console.warn(e); }
}

// ---------------- navegación
document.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => { show("scr-home"); refresh(); }));
$("#go-internal").addEventListener("click", () => { $("#form-internal").reset(); show("scr-internal"); });
$("#go-transfer").addEventListener("click", () => {
  $("#form-transfer").reset();
  ibanPasted = false;
  show("scr-transfer");
});

// ---------------- traspaso
$("#form-internal").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api(`${BASE}/internal-transfer`, { method: "POST", json: { amount: Number($("#int-amount").value) } });
    toast("Traspaso hecho");
    show("scr-home");
    refresh();
  } catch (err) { toast(err.message); }
});

// ---------------- transferencia
$("#tx-iban").addEventListener("paste", () => { ibanPasted = true; });
document.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
  const p = PRESETS[b.dataset.preset];
  $("#tx-name").value = p.beneficiaryName;
  $("#tx-iban").value = p.iban;
  $("#tx-amount").value = p.amount;
  $("#tx-concept").value = p.concept;
  ibanPasted = p.ibanPasted;
}));

$("#form-transfer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#tx-send");
  btn.disabled = true;
  try {
    await refresh(); // llamada activa según el panel del presentador
    const res = await api(`${BASE}/transfers`, {
      method: "POST",
      json: {
        amount: Number($("#tx-amount").value),
        iban: $("#tx-iban").value,
        beneficiaryName: $("#tx-name").value,
        concept: $("#tx-concept").value,
        context: { callActive: Boolean(state && state.callActive), ibanPasted },
      },
    });
    if (res.status === "executed") {
      showResult({ action: "execute", text: "Listo. Tu transferencia se ha enviado." });
    } else {
      conversationId = res.conversationId;
      $("#chat").replaceChildren();
      show("scr-chat");
      handleView(res);
    }
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
});

// ---------------- chat del Escudo
function bubble(role, text) {
  $("#chat").append(el("div", { class: `ll-msg ${role}` }, text));
}

function handleView(view) {
  if (view.done) { showResult(view.outcome); return; }
  bubble("agent", view.message);
  $("#reply-text").focus();
}

$("#form-reply").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#reply-text");
  const text = input.value.trim();
  if (!text) return;
  const btn = $("#reply-send");
  btn.disabled = true;
  input.disabled = true;
  bubble("client", text);
  input.value = "";
  const typing = el("div", { class: "ll-typing" }, "Escribiendo…");
  $("#chat").append(typing);
  try {
    handleView(await api(`${BASE}/conversations/${conversationId}/messages`, { method: "POST", json: { text } }));
  } catch (err) {
    // La conversación ya no existe o ya se decidió (p. ej., la demo se reinició): volver al inicio.
    toast(err.message);
    show("scr-home");
    refresh();
  } finally {
    typing.remove();
    btn.disabled = false;
    input.disabled = false;
  }
});

// ---------------- resultado
function showResult(outcome) {
  const box = $("#result");
  box.className = `ll-result ${outcome.action}`;
  $("#result-icon").setAttribute("href", `/icons.svg#${RESULT_ICON[outcome.action] || "check-circle"}`);
  $("#result-text").textContent = outcome.text;
  show("scr-result");
  refresh();
}

refresh();
setInterval(refresh, 2000);
