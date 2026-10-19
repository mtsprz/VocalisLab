/* VocalisLab SW v2 — shell offline + GETs mínimos cacheados.
   - Página (HTML / navegación): RED PRIMERO, caché solo sin conexión. La v1
     servía index.html desde caché para siempre: el navegador nunca veía las
     versiones nuevas publicadas en Vercel.
   - /assets/ (con hash en el nombre, inmutables): caché primero.
   - No intercepta POST/PUT/DELETE ni orígenes externos. */
const CACHE = 'vocalis-shell-v2';
const API_ALLOW = [/^\/api\/pacientes(\?|$)/];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(['/', '/index.html', '/manifest.webmanifest']).catch(() => {}))
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => clients.claim())
  );
});

const guardar = (req, r) => {
  if (r && r.ok) {
    const c = r.clone();
    caches.open(CACHE).then((cc) => cc.put(req, c));
  }
  return r;
};

self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/')) {
    if (!API_ALLOW.some((rx) => rx.test(u.pathname))) return;
    e.respondWith(fetch(e.request).then((r) => guardar(e.request, r)).catch(() => caches.match(e.request)));
    return;
  }
  const esPagina = e.request.mode === 'navigate' || u.pathname === '/' || u.pathname.endsWith('.html')
    || u.pathname === '/sw.js' || u.pathname.endsWith('.webmanifest');
  if (esPagina) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' }).then((r) => guardar(e.request, r))
        .catch(() => caches.match(e.request).then((hit) => hit || caches.match('/index.html')))
    );
    return;
  }
  // Assets con hash: inmutables → caché primero.
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => guardar(e.request, r))
      .catch(() => caches.match('/index.html')))
  );
});
