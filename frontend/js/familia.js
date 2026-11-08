// Panel del familiar de confianza: avisos en tiempo real y aprobación de operaciones retenidas.
import { api, subscribe, el, toast, LEVEL, fmtTime, fmtMoney, CHANNEL } from "./common.js";

const $ = (s) => document.querySelector(s);

async function loadProfile() {
  const p = await api("/api/perfil");
  $("#person").textContent = p.nombre || "—";
  const bank = await api("/api/banco");
  $("#status-pills").replaceChildren(
    el("span", { class: "pill " + (p.proteccion_activa ? "on" : "off") }, el("span", { class: "dot" }), p.proteccion_activa ? "Protección activada" : "Protección desactivada"),
    el("span", { class: "pill " + (bank.escudo.activo ? "warn" : "") }, el("span", { class: "dot" }), bank.escudo.activo ? "Escudo bancario ACTIVO" : "Escudo bancario en espera"),
  );
  renderHeld(bank.transferencias.filter((t) => t.estado === "retenida"));
}

function renderHeld(list) {
  const ul = $("#held");
  if (!list.length) { ul.replaceChildren(el("li", { class: "muted" }, "No hay operaciones retenidas.")); return; }
  ul.replaceChildren(...list.map((tx) => el("li", {},
    el("strong", {}, `${fmtMoney(tx.importe)} → ${tx.beneficiario}`),
    el("div", { class: "small muted" }, `${tx.iban} · ${tx.concepto || "sin concepto"} · ${fmtTime(tx.fecha)}`),
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "btn btn-danger btn-small", onclick: () => resolve(tx.id, "cancelar") }, "Cancelar (es un timo)"),
      el("button", { class: "btn btn-outline btn-small", onclick: () => resolve(tx.id, "aprobar") }, "Aprobar")),
  )));
}

async function resolve(id, action) {
  try {
    await api(`/api/banco/transferencias/${id}/${action}`, { method: "POST" });
    toast(action === "cancelar" ? "Operación cancelada: el dinero no ha salido" : "Operación aprobada");
    loadProfile();
  } catch (e) { toast(e.message); }
}

function alertItem(a, flash = false) {
  const lv = LEVEL[a.nivel] || LEVEL.amarillo;
  return el("li", { class: flash ? "new-flash" : "" },
    el("div", { class: "row" },
      el("span", { class: `badge ${a.nivel}`, "aria-hidden": "true" }, lv.icon),
      el("div", { style: "flex:1;min-width:220px" },
        el("strong", {}, a.titulo),
        el("div", { class: "small muted" }, `${fmtTime(a.fecha)} · ${CHANNEL[a.canal] || a.canal || ""} · remitente: ${a.remitente || "desconocido"}`)),
      a.notificada ? el("span", { class: "tag" }, "Aviso enviado") : null),
    el("p", { style: "margin-top:8px" }, a.resumen),
    a.texto ? el("details", {}, el("summary", {}, "Ver el mensaje"), el("p", { class: "small" }, a.texto)) : null);
}

async function loadAlerts() {
  const alerts = await api("/api/alertas");
  const ul = $("#alerts");
  ul.replaceChildren(...(alerts.length ? alerts.map((a) => alertItem(a)) : [el("li", { class: "muted" }, "Sin avisos. ¡Todo tranquilo!")]));
}

function notifyBrowser(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") new Notification(title, { body, icon: "/icons/icon-192.png" });
}

async function init() {
  if ("Notification" in window && Notification.permission === "default") {
    document.body.addEventListener("click", () => Notification.requestPermission(), { once: true });
  }
  await Promise.all([loadProfile(), loadAlerts()]);
  const es = subscribe("familia", {
    alerta: (a) => {
      const ul = $("#alerts");
      if (ul.firstElementChild?.classList.contains("muted")) ul.replaceChildren();
      ul.prepend(alertItem(a, true));
    },
    aviso_familiar: (a) => {
      toast(`⚠️ ${a.persona || "Tu familiar"} ha recibido un posible timo`, 6000);
      notifyBrowser("Centinela: posible estafa", a.titulo);
      loadAlerts();
    },
    transferencia_retenida: (tx) => {
      toast(`🛡️ Operación de ${fmtMoney(tx.importe)} retenida: revísala`, 6000);
      notifyBrowser("Centinela: operación retenida", `${fmtMoney(tx.importe)} a ${tx.beneficiario}`);
      loadProfile();
    },
    transferencia: () => loadProfile(),
    escudo: () => loadProfile(),
    perfil: () => loadProfile(),
    reset: () => location.reload(),
  });
  es.onopen = () => { $("#live").className = "pill on"; $("#live").lastElementChild.textContent = "En directo"; };
  es.onerror = () => { $("#live").className = "pill warn"; $("#live").lastElementChild.textContent = "Reconectando…"; };
}

init();
