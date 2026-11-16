const CACHE_NAME = 'emed-pwa-v95-offline-resiliente-dedup';
const ASSETS_TO_CACHE = [
  '/',
  '/?modo=tecnico',
  '/?modo=gestor',
  '/manifest.json',
  '/api/logo',
  '/api/icone-autosave'
];

function fetchWithTimeout(req, ms) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  return fetch(req, { signal: ctrl.signal }).finally(() => clearTimeout(timer));
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // /api/bootstrap: tenta rede com timeout de 4s; se travar (4G morto) ou estiver offline, entrega cache na hora
  if (url.pathname.startsWith('/api/bootstrap')) {
    event.respondWith(
      fetchWithTimeout(event.request, 4000)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(event.request);
          if (cached) return cached;
          return new Response(JSON.stringify({ ok: false, error: 'offline' }), {
            headers: { 'Content-Type': 'application/json' }
          });
        })
    );
    return;
  }

  // App Shell (HTML/JS/CSS): timeout curto de 2.2s para nunca travar tela branca sem rede
  if (event.request.method === 'GET' && !url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetchWithTimeout(event.request, 2200)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((res) => res || caches.match('/')))
    );
  }
});
