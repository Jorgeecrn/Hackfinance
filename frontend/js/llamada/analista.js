// Panel del analista: casos del escudo de llamada, detalle y decisión.
import { api, el, fmtMoney, fmtTime, toast } from "../common.js";

const $ = (s) => document.querySelector(s);
const BASE = "/api/llamada";

const STATUS_LABEL = {
  en_conversacion: "En conversación", retenida: "Retenida", pendiente: "Pendiente",
  ejecutada: "Ejecutada", liberada: "Liberada", bloqueada: "Bloqueada",
};
const TYPOLOGY_LABEL = {
  falso_empleado_banco: "Falso empleado del banco", hijo_en_apuros: "Hijo en apuros",
  inversion_falsa: "Inversión falsa", compraventa: "Compraventa", ninguna: "—",
};
const RISK_LABEL = { low: "bajo", medium: "medio", high: "alto" };
const RULE_LABEL = {
  R1_suplantacion: "R1 · Regla dura: llamada activa + suplantación del banco / cuenta segura",
  R2_riesgo_alto: "R2 · Riesgo alto según el agente",
  R3_riesgo_medio: "R3 · Riesgo medio: revisión por un analista",
  R4_riesgo_bajo: "R4 · Riesgo bajo: se ejecuta",
  R5_sin_decision: "R5 · Sin decisión del agente: revisión por un analista",
};
const OPEN = new Set(["retenida", "pendiente"]);

let selected = null;
let lastJson = "";

function status(s) {
  return el("span", { class: `ll-status ${s}` }, STATUS_LABEL[s] || s);
}

function renderList(cases) {
  $("#empty").classList.toggle("hidden", cases.length > 0);
  $("#cases").replaceChildren(...cases.map((c) => el("tr", {
    class: c.id === selected ? "sel" : null,
    onclick: () => { selected = c.id; render(cases); },
  },
    el("td", {}, status(c.status)),
    el("td", {}, fmtMoney(c.amount)),
    el("td", {}, c.beneficiaryName),
    el("td", {}, el("span", { class: "ll-score" }, c.score)),
    el("td", {}, TYPOLOGY_LABEL[c.assessment?.typology] || "—"),
  )));
}

async function decide(id, decision) {
  try {
    await api(`${BASE}/cases/${id}/decision`, { method: "POST", json: { decision } });
    toast(decision === "release" ? "Transferencia liberada" : "Transferencia bloqueada");
    poll(true);
  } catch (e) { toast(e.message); }
}

function renderDetail(c) {
  const box = $("#detail");
  if (!c) { box.replaceChildren(el("p", { class: "muted" }, "Selecciona un caso para ver su detalle.")); return; }
  const a = c.assessment;
  const parts = [
    el("div", { class: "card-title" }, el("h2", {}, `${fmtMoney(c.amount)} → ${c.beneficiaryName}`), status(c.status)),
    el("div", { class: "ll-kv muted" },
      el("span", {}, fmtTime(c.createdAt)), el("span", {}, c.iban), c.concept ? el("span", {}, `«${c.concept}»`) : null),
    el("h3", {}, `Señales · puntuación ${c.score}/100`),
    el("ul", { class: "ll-signals" }, c.signals.map((s) => el("li", {}, el("span", { class: "w" }, `+${s.weight}`), el("span", {}, s.detail)))),
    el("h3", {}, "Evaluación del agente"),
    a
      ? el("div", { class: "ll-kv" },
        el("span", {}, el("strong", {}, "Riesgo: "), RISK_LABEL[a.risk] || a.risk),
        el("span", {}, el("strong", {}, "Tipo: "), TYPOLOGY_LABEL[a.typology] || a.typology),
        el("span", {}, el("strong", {}, "Alertas: "), a.redFlags.length ? a.redFlags.join(", ") : "ninguna"))
      : el("p", { class: "muted" }, "Sin evaluación (el agente no respondió)."),
    el("h3", {}, "Conversación"),
    c.transcript.length
      ? el("div", { class: "ll-chat" }, c.transcript.map((t) => el("div", { class: `ll-msg ${t.role}` }, t.text)))
      : el("p", { class: "muted" }, "Sin mensajes."),
  ];
  if (c.decision) {
    parts.push(el("h3", {}, "Decisión"),
      el("p", {}, el("strong", {}, RULE_LABEL[c.decision.rule] || c.decision.rule)),
      el("ul", { class: "muted small" }, c.decision.reasons.map((r) => el("li", {}, r))));
  }
  if (c.analystDecision) {
    parts.push(el("p", { class: "small" }, `Analista: ${c.analystDecision.decision === "release" ? "liberada" : "bloqueada"} · ${fmtTime(c.analystDecision.ts)}`));
  }
  if (OPEN.has(c.status)) {
    parts.push(el("div", { class: "actions row" },
      el("button", { class: "btn btn-ok", onclick: () => decide(c.id, "release") }, "Liberar"),
      el("button", { class: "btn btn-danger", onclick: () => decide(c.id, "block") }, "Bloquear")));
  }
  box.replaceChildren(...parts);
}

function render(cases) {
  if (selected && !cases.some((c) => c.id === selected)) selected = null;
  if (!selected && cases.length) selected = cases[0].id;
  renderList(cases);
  renderDetail(cases.find((c) => c.id === selected));
}

async function poll(force = false) {
  try {
    const cases = await api(`${BASE}/cases`);
    const json = JSON.stringify(cases);
    if (!force && json === lastJson) return; // no repintar: no se pierde el scroll
    lastJson = json;
    render(cases);
  } catch (e) { console.warn(e); }
}

poll(true);
setInterval(poll, 2000);
