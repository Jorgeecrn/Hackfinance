// Banco simulado: muestra cómo el «Escudo bancario» retiene pagos tras una alerta.
import { api, subscribe, el, toast, fmtTime, fmtMoney } from "./common.js";

const $ = (s) => document.querySelector(s);
let timer = null;

async function load() {
  const b = await api("/api/banco");
  $("#entity").textContent = `${b.entidad} · ${b.titular}`;
  $("#balance").textContent = fmtMoney(b.saldo);
  $("#iban").textContent = b.iban;
  const st = $("#shield-status");
  clearInterval(timer);
  if (b.escudo.activo) {
    const tick = () => {
      const ms = new Date(b.escudo.activo_hasta) - new Date();
      if (ms <= 0) { load(); return; }
      const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
      st.textContent = `🛡️ ACTIVO (${m}:${String(s).padStart(2, "0")} restantes). Motivo: ${b.escudo.motivo}. Pagos ≥ ${fmtMoney(b.umbral_escudo)} a beneficiarios nuevos quedan retenidos.`;
    };
    st.className = "banner shield";
    tick();
    timer = setInterval(tick, 1000);
  } else {
    st.className = "banner info";
    st.textContent = "En espera. Se activa solo cuando Centinela detecta una estafa grave.";
  }
  $("#movements").replaceChildren(...(b.transferencias.length ? b.transferencias.map((t) => el("tr", {},
    el("td", {}, fmtTime(t.fecha)),
    el("td", {}, t.beneficiario, el("div", { class: "small muted" }, t.iban + (t.beneficiario_conocido ? " · habitual" : " · NUEVO"))),
    el("td", {}, fmtMoney(t.importe)),
    el("td", {}, el("span", { class: `estado ${t.estado}` }, t.estado)),
    el("td", { class: "small" }, t.motivo || "—"))) : [el("tr", {}, el("td", { colspan: "5", class: "muted" }, "Sin movimientos"))]));
}

function preset(benef, iban, amount, concept) {
  $("#tx-benef").value = benef; $("#tx-iban").value = iban; $("#tx-amount").value = amount; $("#tx-concept").value = concept;
}
$("#preset-scam").addEventListener("click", () => preset("Dani (número nuevo)", "ES7921000813610123456789", 680, "Factura urgente"));
$("#preset-ok").addEventListener("click", () => preset("Lucía López", "ES9121000418450200051332", 25, "Cena cumpleaños"));

$("#btn-send").addEventListener("click", async () => {
  const body = {
    beneficiario: $("#tx-benef").value.trim(), iban: $("#tx-iban").value.trim(),
    importe: parseFloat($("#tx-amount").value), concepto: $("#tx-concept").value.trim(),
  };
  if (!body.beneficiario || !body.iban || !(body.importe > 0)) { toast("Rellena beneficiario, IBAN e importe"); return; }
  try {
    const tx = await api("/api/banco/transferencia", { method: "POST", json: body });
    toast(tx.estado === "retenida" ? "🛡️ Operación RETENIDA por el escudo" : `Operación ${tx.estado}`);
    load();
  } catch (e) { toast(e.message); }
});
$("#btn-shield-on").addEventListener("click", async () => { await api("/api/banco/escudo/activar", { method: "POST" }); load(); });
$("#btn-shield-off").addEventListener("click", async () => { await api("/api/banco/escudo/desactivar", { method: "POST" }); load(); });

load();
subscribe("banco", { escudo: load, transferencia: load, transferencia_retenida: load, alerta: load, reset: () => location.reload() });
