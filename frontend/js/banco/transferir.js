// Pestaña Transferir: formulario, conversación con el escudo de llamada y resultado.
import { api, el, toast } from "../common.js";
import { BASE, goTab, refresh, showScreen, store } from "./core.js";

const $ = (s) => document.querySelector(s);

// Copia de backend/app/llamada/seed.py (PRESETS) para rellenar la demo.
const PRESETS = {
  normal: { beneficiaryName: "Javier López", iban: "ES66 2100 0418 4012 3456 7891", amount: 200, concept: "Ayuda mensual", ibanPasted: false },
  casero: { beneficiaryName: "Antonio Ruiz", iban: "ES62 0182 2370 4202 0150 4358", amount: 600, concept: "Alquiler noviembre", ibanPasted: false },
  estafa: { beneficiaryName: "Cuenta segura Banco Demo", iban: "ES49 2038 3000 0010 0012 3456", amount: 8500, concept: "Protección de fondos", ibanPasted: true },
};
const RESULT_ICON = { execute: "check-circle", hold: "octagon", review: "clock" };

let ibanPasted = false;
let conversationId = null;

/** Formulario vacío: se usa al entrar en la pestaña y tras salir de una conversación. */
export function resetTransferForm() {
  $("#form-transfer").reset();
  ibanPasted = false;
  showScreen("transferir", "form");
}

function bubble(role, text) {
  $("#chat").append(el("div", { class: `bk-msg ${role}` }, text));
}

function showResult(outcome) {
  $("#result").className = `bk-result ${outcome.action}`;
  $("#result-icon").setAttribute("href", `/icons.svg#${RESULT_ICON[outcome.action] || "check-circle"}`);
  $("#result-text").textContent = outcome.text;
  showScreen("transferir", "result");
  refresh();
}

function handleView(view) {
  if (view.done) { showResult(view.outcome); return; }
  bubble("agent", view.message);
  $("#reply-text").focus();
}

function leave() {
  resetTransferForm();
  goTab("inicio");
  refresh();
}

export function initTransferir() {
  document.querySelector('[data-tab="transferir"]').addEventListener("click", resetTransferForm);
  document.querySelectorAll('[data-goto="transferir"]').forEach((b) => b.addEventListener("click", resetTransferForm));

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
          context: { callActive: Boolean(store.state && store.state.callActive), ibanPasted },
        },
      });
      if (res.status === "executed") {
        showResult({ action: "execute", text: "Listo. Tu transferencia se ha enviado." });
      } else {
        conversationId = res.conversationId;
        $("#chat").replaceChildren();
        showScreen("transferir", "chat");
        handleView(res);
      }
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
    }
  });

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
    const typing = el("div", { class: "bk-typing" }, "Escribiendo…");
    $("#chat").append(typing);
    try {
      handleView(await api(`${BASE}/conversations/${conversationId}/messages`, { method: "POST", json: { text } }));
    } catch (err) {
      // La conversación ya no existe o ya se decidió (p. ej., la demo se reinició): volver al inicio.
      toast(err.message);
      leave();
    } finally {
      typing.remove();
      btn.disabled = false;
      input.disabled = false;
    }
  });

  $("#chat-exit").addEventListener("click", leave);
  $("#result-home").addEventListener("click", leave);
}
