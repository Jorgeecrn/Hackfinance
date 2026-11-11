// Pestaña Perfil: datos de la clienta, tema y herramientas de demo (solo para el equipo).
import { api, getTheme, initials, setTheme, toast } from "../common.js";
import { onRefresh } from "./core.js";

const $ = (s) => document.querySelector(s);

function renderTheme() {
  $("#theme-label").textContent = getTheme() === "dark" ? "Tema claro" : "Tema oscuro";
}

export function initPerfil() {
  onRefresh(({ state }) => {
    if (!state) return;
    $("#profile-name").textContent = state.client.name;
    $("#profile-avatar").textContent = initials(state.client.name) || "—";
    $("#profile-iban").textContent = state.accounts.corriente.iban.replace(/(.{4})/g, "$1 ").trim();
  });
  renderTheme();
  $("#theme-toggle").addEventListener("click", () => {
    setTheme(getTheme() === "dark" ? "light" : "dark");
    renderTheme();
  });
  $("#reset-all").addEventListener("click", async () => {
    try {
      await api("/api/demo/reset", { method: "POST" });
      toast("Demo reiniciada");
      setTimeout(() => location.reload(), 600);
    } catch (e) { toast(e.message); }
  });
}
