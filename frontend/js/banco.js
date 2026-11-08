// Banco simulado: muestra cómo el «Escudo bancario» retiene pagos tras una alerta.
import { api, subscribe, el, toast, fmtTime, fmtMoney, icon } from "./common.js";

const $ = (s) => document.querySelector(s);
let timer = null;

const STATE_ICON = { completada: "arrow-up-right", retenida: "clock", cancelada: "x", rechazada: "x" };

function maskIban(iban = "") {
  const c = iban.replace(/\s/g, "");
  return c.length > 8 ? `${c.slice(0, 4)} •••• •••• ${c.slice(-4)}` : iban;
}

async function load() {
  const b = await api("/api/banco");
  $("#entity").textContent = b.entidad;
  $("#holder").textContent = b.titular;
  $("#balance").textContent = fmtMoney(b.saldo);
  $("#iban").textContent = maskIban(b.iban);

  const st = $("#shield-status");
  const ring = $("#shield-ring");
  const pill = $("#shield-pill");
  const cd = $("#countdown");
  clearInterval(timer);
  if (b.escudo.activo) {
    ring.classList.add("on");
    ring.querySelector("use").setAttribute("href", "/icons.svg#lock");
    pill.className = "pill warn";
    pill.textContent = "Activo";
    cd.classList.remove("hidden");
    st.textContent = `${b.escudo.motivo}. Pagos de ${fmtMoney(b.umbral_escudo)} o más a beneficiarios nuevos quedan retenidos hasta que el familiar los revise.`;
    const tick = () => {
      const ms = new Date(b.escudo.activo_hasta) - new Date();
      if (ms <= 0) { load(); return; }
      const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
      cd.textContent = `${m}:${String(s).padStart(2, "0")}`;
    };
    tick();
    timer = setInterval(tick, 1000);
  } else {
    ring.classList.remove("on");
    ring.querySelector("use").setAttribute("href", "/icons.svg#shield");
    pill.className = "pill";
    pill.textContent = "En espera";
    cd.classList.add("hidden");
    st.textContent = "Se activa solo cuando Centinela detecta una estafa grave.";
  }

  const list = b.transferencias;
  $("#movements").replaceChildren(...(list.length ? list.map((t) => el("li", { class: t.estado },
    el("span", { class: "m-ic" }, icon(STATE_ICON[t.estado] || "arrow-up-right")),
    el("div", { style: "min-width:0" },
      el("div", { class: "m-name" }, t.beneficiario),
      el("div", { class: "m-sub" }, `${fmtTime(t.fecha)} · ${t.beneficiario_conocido ? "habitual" : "beneficiario nuevo"}`),
      t.motivo ? el("div", { class: "m-sub" }, t.motivo) : null),
    el("div", {},
      el("div", { class: "m-amt" }, `−${fmtMoney(t.importe)}`),
      t.estado === "completada" ? el("span", { class: "estado completada" }, "Completada")
        : el("div", { style: "text-align:right" }, el("span", { class: `stamp estado ${t.estado}`, style: "background:none" }, t.estado)))))
    : [el("li", { class: "empty", style: "display:block" }, icon("inbox"), "Sin movimientos")]));
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
    toast(tx.estado === "retenida" ? "Operación RETENIDA por el escudo" : `Operación ${tx.estado}`);
    load();
  } catch (e) { toast(e.message); }
});
$("#btn-shield-on").addEventListener("click", async () => { await api("/api/banco/escudo/activar", { method: "POST" }); load(); });
$("#btn-shield-off").addEventListener("click", async () => { await api("/api/banco/escudo/desactivar", { method: "POST" }); load(); });

load();
subscribe("banco", { escudo: load, transferencia: load, transferencia_retenida: load, alerta: load, reset: () => location.reload() });
