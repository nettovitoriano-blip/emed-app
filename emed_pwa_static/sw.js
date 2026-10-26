const CACHE_NAME = 'emed-pwa-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/?modo=tecnico',
  '/?modo=gestor',
  '/manifest.json',
  '/api/logo'
];

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
  // Para chamadas de API GET (/api/bootstrap), tenta rede primeiro e salva cache para uso offline
  if (url.pathname.startsWith('/api/bootstrap')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Para o App Shell (HTML/JS/CSS), tenta rede primeiro para manter sempre atualizado e cai para o cache se estiver sem sinal
  if (event.request.method === 'GET' && !url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request).then((res) => res || caches.match('/')))
    );
  }
});
