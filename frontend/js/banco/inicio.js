// Pestaña Inicio: saldo, accesos rápidos, movimientos, banner de estado y traspaso.
import { api, el, fmtMoney, fmtShort, toast } from "../common.js";
import { BASE, onRefresh, refresh, showScreen, store } from "./core.js";

const $ = (s) => document.querySelector(s);
let lastKind;

const BANNERS = {
  call: "📞 Llamada en curso",
  alert: "⚠️ Mensaje sospechoso reciente: los pagos a cuentas nuevas se revisarán",
  ok: "🛡️ Protección antiestafas activa",
};

function bannerKind({ state, bank, profile }) {
  if (state?.callActive) return "call";
  if (bank?.escudo?.activo) return "alert";
  if (profile?.proteccion_activa) return "ok";
  return null;
}

function render(s) {
  if (!s.state) return;
  const { client, accounts, movements } = s.state;
  $("#hello").textContent = `Hola, ${client.name.split(" ")[0]}`;
  $("#bal-corriente").textContent = fmtMoney(accounts.corriente.balance);
  $("#iban-corriente").textContent = accounts.corriente.iban.replace(/(.{4})/g, "$1 ").trim();
  $("#bal-ahorro").textContent = fmtMoney(accounts.ahorro.balance);
  $("#int-available").textContent = fmtMoney(accounts.ahorro.balance);

  const kind = bannerKind(s);
  if (kind !== lastKind) { // role="status": solo se anuncia cuando cambia de verdad
    lastKind = kind;
    const banner = $("#status-banner");
    banner.className = kind ? `bk-banner ${kind}` : "bk-banner hidden";
    banner.textContent = kind ? BANNERS[kind] : "";
  }

  $("#movements").replaceChildren(...movements.slice(0, 8).map((m) => {
    const out = m.type === "transfer_out";
    return el("li", {},
      el("span", {}, out ? (m.name || "Transferencia") : "Traspaso desde ahorro", el("br"), el("span", { class: "muted small" }, fmtShort(m.ts))),
      el("span", { class: out ? "neg" : "pos" }, (out ? "−" : "+") + fmtMoney(m.amount)));
  }));
}

export function initInicio() {
  onRefresh(render);
  $("#go-internal").addEventListener("click", () => { $("#form-internal").reset(); showScreen("inicio", "internal"); });
  $("#form-internal").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api(`${BASE}/internal-transfer`, { method: "POST", json: { amount: Number($("#int-amount").value) } });
      toast("Traspaso hecho");
      showScreen("inicio", "home");
      refresh();
    } catch (err) { toast(err.message); }
  });
}

export { bannerKind, store };
