// Entrada de la app de Banco Demo.
import { api, subscribe, toast, unlockAudioOnFirstTouch } from "../common.js";
import { refresh, store, wireNavigation } from "./core.js";
import { initInicio } from "./inicio.js";
import { initPerfil } from "./perfil.js";
import { initTransferir } from "./transferir.js";
import { handleShared, initProteccion, loadInbox, onAnalyzedMessage, onShieldEvent } from "./proteccion.js";

async function init() {
  unlockAudioOnFirstTouch();
  try { store.health = await api("/api/health"); } catch (_) { /* sin servidor */ }
  wireNavigation();
  initInicio();
  initPerfil();
  initTransferir();
  initProteccion();
  await refresh();
  setInterval(refresh, 2000);
  const events = subscribe("usuario", {
    mensaje: loadInbox,
    analisis_mensaje: onAnalyzedMessage,
    perfil: () => refresh(),
    escudo: onShieldEvent,
    // «transferencia_retenida» es del banco antiguo de Centinela: esta app no lo usa.
    reset: () => location.reload(),
  });
  events.onopen = () => { loadInbox(); refresh(); };
  handleShared();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

init().catch((e) => { console.error(e); toast("No se ha podido cargar la aplicación"); });
