// Panel del familiar de confianza: avisos en tiempo real y revisión de las transferencias de Banco Demo.
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
}

// ------------------------------------------------------------ transferencias de Banco Demo en revisión
const OPEN = ["retenida", "pendiente"];
const STATUS_LABEL = { retenida: "Retenida", pendiente: "Pendiente" };

async function loadCases() {
  try {
    const cases = await api("/api/llamada/cases");
    held = cases.filter((c) => OPEN.includes(c.status));
  } catch (e) { console.warn(e); }
  renderHeld();
  renderStats();
}

function topSignal(c) {
  const sorted = [...(c.signals || [])].sort((a, b) => b.weight - a.weight);
  return sorted[0]?.detail || "";
}

function renderHeld() {
  const ul = $("#held");
  if (!held.length) {
    ul.replaceChildren(el("li", { class: "empty" }, icon("check-circle"), "No hay transferencias en revisión."));
    return;
  }
  ul.replaceChildren(...held.map((c) => el("li", { style: "border:0;padding:0" },
    el("div", { class: "held" },
      el("div", { class: "row", style: "justify-content:space-between;align-items:flex-start" },
        el("div", {},
          el("div", { class: "amount" }, fmtMoney(c.amount)),
          el("div", { class: "who" }, `a ${c.beneficiaryName}`)),
        el("span", { class: "estado retenida" }, icon("clock"), STATUS_LABEL[c.status] || c.status)),
      el("div", { class: "small muted", style: "margin-top:6px" }, `${c.iban} · ${c.concept || "sin concepto"} · ${fmtTime(c.createdAt)}`),
      topSignal(c) ? el("p", { class: "small", style: "margin:8px 0 0" }, icon("alert"), " ", topSignal(c)) : null,
      (c.transcript || []).length ? el("details", {},
        el("summary", {}, "Ver la conversación con el banco"),
        ...c.transcript.map((t) => el("p", { class: "small" }, el("strong", {}, t.role === "agent" ? "Banco: " : "Ella: "), t.text))) : null,
      el("div", { class: "btns" },
        el("button", { class: "btn btn-danger", onclick: () => resolve(c.id, "block") }, icon("x"), "Bloquear"),
        el("button", { class: "btn btn-outline", onclick: () => resolve(c.id, "release") }, icon("check"), "Liberar"))))));
}

async function resolve(id, decision) {
  try {
    await api(`/api/llamada/cases/${id}/decision`, { method: "POST", json: { decision, actor: "familia" } });
    toast(decision === "block" ? "Transferencia bloqueada: el dinero no ha salido" : "Transferencia liberada");
  } catch (e) { toast(e.message); }
  loadCases();
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
  await Promise.all([loadProfile(), loadAlerts(), loadCases()]);
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
    caso: (c) => {
      if (OPEN.includes(c.status)) {
        toast(`Transferencia de ${fmtMoney(c.amount)} en revisión: decide si liberarla`, 6000);
        notifyBrowser("Banco Demo: transferencia en revisión", `${fmtMoney(c.amount)} a ${c.beneficiaryName}`);
      }
      loadCases();
    },
    escudo: () => loadProfile(),
    perfil: () => loadProfile(),
    reset: () => location.reload(),
  });
  es.onopen = () => { $("#live").className = "pill on"; $("#live").lastElementChild.textContent = "En directo"; };
  es.onerror = () => { $("#live").className = "pill warn"; $("#live").lastElementChild.textContent = "Reconectando…"; };
}

init();
