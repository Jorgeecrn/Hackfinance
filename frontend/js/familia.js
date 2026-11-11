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
  const cases = await api("/api/llamada/cases");
  held = cases.filter((c) => OPEN.includes(c.status));
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
        el("button", { class: "btn btn-danger", onclick: (e) => resolve(c.id, "block", e.currentTarget) }, icon("x"), "Bloquear"),
        el("button", { class: "btn btn-outline", onclick: (e) => resolve(c.id, "release", e.currentTarget) }, icon("check"), "Liberar"))))));
}

async function resolve(id, decision, btn) {
  btn?.parentElement?.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  try {
    await api(`/api/llamada/cases/${id}/decision`, { method: "POST", json: { decision, actor: "familia" } });
    toast(decision === "block" ? "Transferencia bloqueada: el dinero no ha salido" : "Transferencia liberada");
  } catch (e) { toast(e.message); }
  try { await loadCases(); }
  catch (e) {
    toast("No se han podido actualizar las transferencias");
    btn?.parentElement?.querySelectorAll("button").forEach((b) => { b.disabled = false; });
  }
}

function alertItem(a) {
  const lv = LEVEL[a.nivel] || LEVEL.amarillo;
  return el("li", {},
    el("span", { class: `badge ${a.nivel}`, "aria-hidden": "true" }, icon(lv.icon)),
    el("div", { style: "min-width:0" },
      el("div", { class: "t-head" },
        el("strong", {}, a.titulo),
        el("span", { class: `chip-status ${a.nivel}` }, lv.label),
        a.notificada ? el("span", { class: "tag" }, icon("send"), "Aviso publicado en el panel") : null),
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

function setLive(connected, text) {
  $("#live").className = connected ? "pill on" : "pill warn";
  $("#live").lastElementChild.textContent = text;
}

async function refreshPanel() {
  try {
    await Promise.all([loadProfile(), loadAlerts(), loadCases()]);
    return true;
  } catch (e) {
    setLive(false, "No se han podido actualizar los datos");
    return false;
  }
}

function init() {
  if ("Notification" in window && Notification.permission === "default") {
    document.body.addEventListener("click", () => Notification.requestPermission(), { once: true });
  }
  const es = subscribe("familia", {
    alerta: refreshPanel,
    aviso_familiar: () => {
      toast("Hay un nuevo aviso en el panel familiar", 6000);
      notifyBrowser("Centinela", "Hay un posible timo en el panel familiar.");
      refreshPanel();
    },
    caso: ({ status }) => {
      if (OPEN.includes(status)) {
        toast("Hay una transferencia en revisión", 6000);
        notifyBrowser("Banco Demo", "Hay una transferencia en revisión en el panel familiar.");
      }
      refreshPanel();
    },
    escudo: refreshPanel,
    perfil: refreshPanel,
    reset: refreshPanel,
  });
  es.onopen = async () => {
    if (await refreshPanel() && es.readyState === EventSource.OPEN) setLive(true, "En directo");
  };
  es.onerror = () => setLive(false, "Reconectando…");
}

init();
