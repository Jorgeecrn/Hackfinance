// Estado compartido y navegación de la app de Banco Demo.
import { api, toast } from "../common.js";

export const BASE = "/api/llamada";
export const store = { state: null, profile: null, bank: null, health: null };

const listeners = [];
const TABS = ["inicio", "transferir", "proteccion", "perfil"];

export function onRefresh(fn) { listeners.push(fn); }

async function load(key, path) {
  try { store[key] = await api(path); } catch (e) { console.warn(`No se pudo cargar ${path}`, e); }
}

/** Recarga el estado del banco, el perfil y el escudo, y avisa a cada pestaña. */
export async function refresh() {
  await Promise.all([load("state", `${BASE}/state`), load("profile", "/api/perfil"), load("bank", "/api/banco")]);
  for (const fn of listeners) {
    try { fn(store); } catch (e) { console.warn(e); }
  }
}

export function goTab(name) {
  for (const t of TABS) document.getElementById(`tab-${t}`).classList.toggle("hidden", t !== name);
  document.querySelectorAll("[data-tab]").forEach((b) => {
    if (b.dataset.tab === name) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  window.scrollTo({ top: 0 });
}

export function showScreen(tab, screenId) {
  document.querySelectorAll(`#tab-${tab} [data-screen]`).forEach((s) => s.classList.toggle("hidden", s.dataset.screen !== screenId));
  window.scrollTo({ top: 0 });
}

/** Enlaces genéricos: pestañas, pantallas, «volver» y botones decorativos. */
export function wireNavigation(root = document) {
  root.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => goTab(b.dataset.tab)));
  root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => goTab(b.dataset.goto)));
  root.querySelectorAll("[data-soon]").forEach((b) => b.addEventListener("click", () => toast("Próximamente")));
  root.querySelectorAll("[data-screen-go], [data-screen-back]").forEach((b) => b.addEventListener("click", () => {
    const tab = b.closest(".bk-tab").id.replace("tab-", "");
    showScreen(tab, b.dataset.screenGo || b.dataset.screenBack);
  }));
}
