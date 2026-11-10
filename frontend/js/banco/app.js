// Entrada de la app de Banco Demo.
import { api, subscribe, toast, unlockAudioOnFirstTouch } from "../common.js";
import { refresh, store, wireNavigation } from "./core.js";
import { initInicio } from "./inicio.js";
import { initPerfil } from "./perfil.js";

async function init() {
  unlockAudioOnFirstTouch();
  try { store.health = await api("/api/health"); } catch (_) { /* sin servidor */ }
  wireNavigation();
  initInicio();
  initPerfil();
  await refresh();
  setInterval(refresh, 2000);
  subscribe("usuario", {
    perfil: () => refresh(),
    escudo: () => refresh(),
    reset: () => location.reload(),
  });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

init().catch((e) => { console.error(e); toast("No se ha podido cargar la aplicación"); });
