// Panel del familiar de confianza: avisos en tiempo real y aprobación de operaciones retenidas.
import { api, subscribe, el, toast, LEVEL, fmtTime, fmtMoney, CHANNEL, icon, initials } from "./common.js";

const $ = (s) => document.querySelector(s);
let alerts = [];
let held = [];

function renderStats() {
  const timos = alerts.filter((a) => a.nivel === "rojo").length;
  $("#stats").replaceChildren(
    el("div", { class: "stat-tile" }, el("span", { class: "n" }, alerts.length), el("span", { class: "l" }, alerts.length === 1 ? "Aviso" : "Avisos")),
    el("div", { class: "stat-tile rojo" }, el("span", { class: "n" }, timos), el("span", { class: "l" }, "Timos graves")),
    el("div", { class: "stat-tile amarillo" }, el("span", { class: "n" }, held.length), el("span", { class: "l" }, "Retenidas")),
  );
}

async function loadProfile() {
  const p = await api("/api/perfil");
  $("#person").textContent = p.nombre || "—";
  $("#avatar").textContent = initials(p.nombre || "") || "—";
  const bank = await api("/api/banco");
  $("#status-pills").replaceChildren(
    el("span", { class: "pill " + (p.proteccion_activa ? "on" : "off") }, el("span", { class: "dot" }), p.proteccion_activa ? "Protección activada" : "Protección desactivada"),
    el("span", { class: "pill " + (bank.escudo.activo ? "warn" : "") }, icon(bank.escudo.activo ? "lock" : "shield"), bank.escudo.activo ? "Escudo bancario activo" : "Escudo en espera"),
  );
  held = bank.transferencias.filter((t) => t.estado === "retenida");
  renderHeld();
  renderStats();
}

function renderHeld() {
  const ul = $("#held");
  if (!held.length) {
    ul.replaceChildren(el("li", { class: "empty" }, icon("check-circle"), "No hay operaciones retenidas."));
    return;
  }
  ul.replaceChildren(...held.map((tx) => el("li", { style: "border:0;padding:0" },
    el("div", { class: "held" },
      el("div", { class: "row", style: "justify-content:space-between;align-items:flex-start" },
        el("div", {},
          el("div", { class: "amount" }, fmtMoney(tx.importe)),
          el("div", { class: "who" }, `a ${tx.beneficiario}`)),
        el("span", { class: "estado retenida" }, icon("clock"), "Retenida")),
      el("div", { class: "small muted", style: "margin-top:6px" }, `${tx.iban} · ${tx.concepto || "sin concepto"} · ${fmtTime(tx.fecha)}`),
      el("div", { class: "btns" },
        el("button", { class: "btn btn-danger", onclick: () => resolve(tx.id, "cancelar") }, icon("x"), "Cancelar"),
        el("button", { class: "btn btn-outline", onclick: () => resolve(tx.id, "aprobar") }, icon("check"), "Aprobar"))))));
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
    el("span", { class: `badge ${a.nivel}`, "aria-hidden": "true" }, icon(lv.icon)),
    el("div", { style: "min-width:0" },
      el("div", { class: "t-head" },
        el("strong", {}, a.titulo),
        el("span", { class: `chip-status ${a.nivel}` }, lv.label),
        a.notificada ? el("span", { class: "tag" }, icon("send"), "Aviso enviado") : null),
      el("div", { class: "t-meta" }, `${fmtTime(a.fecha)} · ${CHANNEL[a.canal] || a.canal || ""} · remitente: ${a.remitente || "desconocido"}`),
      el("p", { class: "t-body" }, a.resumen),
      a.texto ? el("details", {}, el("summary", {}, "Ver el mensaje"), el("p", { class: "quote" }, a.texto)) : null));
}

function renderAlerts() {
  $("#alerts").replaceChildren(...(alerts.length ? alerts.map((a) => alertItem(a))
    : [el("li", { class: "empty", style: "display:block" }, icon("shield-check"), "Sin avisos. Todo tranquilo.")]));
  renderStats();
}

async function loadAlerts() {
  alerts = await api("/api/alertas");
  renderAlerts();
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
      alerts = [a, ...alerts.filter((x) => x.id !== a.id)];
      const ul = $("#alerts");
      if (ul.firstElementChild?.classList.contains("empty")) ul.replaceChildren();
      ul.prepend(alertItem(a, true));
      renderStats();
    },
    aviso_familiar: (a) => {
      toast(`${a.persona || "Tu familiar"} ha recibido un posible timo`, 6000);
      notifyBrowser("Centinela: posible estafa", a.titulo);
      loadAlerts();
    },
    transferencia_retenida: (tx) => {
      toast(`Operación de ${fmtMoney(tx.importe)} retenida: revísala`, 6000);
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
