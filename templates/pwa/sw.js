{% autoescape off %}// Service worker de Finanzas (RNF-01). Lo genera apps/core/pwa.py.
// Las páginas van siempre a la red: los datos financieros nunca se muestran desde caché.
const CACHE = "{{ cache }}";
const SIN_CONEXION = "{{ sin_conexion }}";
const ESTATICOS = "{{ prefijo_estaticos }}";
const PRECARGA = {{ precarga }};

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll([SIN_CONEXION, ...PRECARGA]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(
        nombres.filter((nombre) => nombre !== CACHE).map((nombre) => caches.delete(nombre))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const solicitud = evento.request;
  const url = new URL(solicitud.url);
  if (solicitud.method !== "GET" || url.origin !== self.location.origin) return;

  if (solicitud.mode === "navigate") {
    // Páginas: de la red; sin conexión, solo el aviso (nunca una página guardada).
    evento.respondWith(fetch(solicitud).catch(() => caches.match(SIN_CONEXION)));
    return;
  }
  if (url.pathname.startsWith(ESTATICOS)) {
    // Estilos, scripts e íconos: de la red y, sin conexión, la última copia guardada.
    evento.respondWith(
      fetch(solicitud)
        .then((respuesta) => {
          if (respuesta.ok) {
            const copia = respuesta.clone();
            caches.open(CACHE).then((cache) => cache.put(solicitud, copia));
          }
          return respuesta;
        })
        .catch(() => caches.match(solicitud))
    );
  }
});
{% endautoescape %}
