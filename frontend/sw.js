// Service worker de Banco Demo (con Centinela): hace la app instalable y que la interfaz cargue sin red.
// El análisis siempre necesita conexión (no se cachea ninguna llamada a /api).
const CACHE = "centinela-v4";
const SHELL = [
  "/", "/index.html", "/styles.css", "/banco.css", "/manifest.webmanifest",
  "/js/common.js", "/js/banco/core.js", "/js/banco/app.js", "/js/banco/inicio.js", "/js/banco/perfil.js", "/js/banco/transferir.js", "/js/banco/proteccion.js",
  "/icons.svg", "/icons/icon-192.png", "/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith("centinela-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.origin !== location.origin) return;
  // Red primero (siempre la versión más reciente), caché si no hay conexión.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/")))
  );
});
