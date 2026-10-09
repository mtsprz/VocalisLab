/* VocalisLab SW v1 — shell offline + GETs mínimos cacheados.
   Sin precache de assets con hash: runtime cache-first para mismo origen.
   Soloito: no intercepta POST/PUT/DELETE ni orígenes externos. */
const CACHE = 'vocalis-shell-v1';
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

self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/')) {
    const key = u.pathname + (u.search ? '?' : '');
    if (!API_ALLOW.some((rx) => rx.test(key)) && !API_ALLOW.some((rx) => rx.test(u.pathname))) return;
    e.respondWith(
      fetch(e.request).then((r) => {
        const c = r.clone();
        caches.open(CACHE).then((cc) => cc.put(e.request, c));
        return r;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
      const c = r.clone();
      caches.open(CACHE).then((cc) => cc.put(e.request, c));
      return r;
    }).catch(() => caches.match('/index.html')))
  );
});
