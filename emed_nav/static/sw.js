// EmedNav Service Worker - v10 (Full Offline PWA + Cache-First Assets + Multi-Stop Routing)
const CACHE_NAME = 'emednav-v11-multistop';

const ASSETS_TO_CACHE = [
  '/',
  '/frota',
  '/static/index.html',
  '/static/frota.html',
  '/static/manifest.json',
  '/static/simbolo_emed_clean.svg',
  '/static/simbolo_emed_red.svg',
  '/static/logo_emed_oficial.png',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch(() => {});
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // APIs do GPS e telemetria: tenta rede primeiro; se offline, cai no cache ou segue o app
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(req).catch(() => caches.match(req))
    );
    return;
  }

  // Arquivos estáticos (HTML, CSS, JS, Imagens): Cache-first com revalidação
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) {
        // Busca versão atualizada em background
        fetch(req).then((networkRes) => {
          if (networkRes && networkRes.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(req, networkRes));
          }
        }).catch(() => {});
        return cached;
      }
      return fetch(req).then((networkRes) => {
        if (networkRes && networkRes.status === 200) {
          const resClone = networkRes.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone));
        }
        return networkRes;
      });
    }).catch(() => caches.match('/static/index.html'))
  );
});
