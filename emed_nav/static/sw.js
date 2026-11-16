// EmedNav Service Worker - v28 (Arquitetura 100% Offline: Leaflet Local, Cache de Tiles OSM e Rotas Resilientes)
const CACHE_NAME = 'emednav-v28-offline-ultimate';
const TILE_CACHE_NAME = 'emednav-tiles-offline-v1';

const ASSETS_TO_CACHE = [
  '/',
  '/gps',
  '/emedcar',
  '/frota',
  '/admin',
  '/static/index.html',
  '/static/frota.html',
  '/static/manifest.json',
  '/static/leaflet.css',
  '/static/leaflet.js',
  '/static/logo_emed_arroba.png',
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
          if (k !== CACHE_NAME && k !== TILE_CACHE_NAME) return caches.delete(k);
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1. Cache automático de ladrilhos de mapa (OpenStreetMap e CartoDB) para visualização offline nas viagens
  if (url.hostname.includes('tile.openstreetmap.org') || url.hostname.includes('basemaps.cartocdn.com')) {
    event.respondWith(
      caches.open(TILE_CACHE_NAME).then((tileCache) => {
        return tileCache.match(req).then((cached) => {
          return fetch(req).then((networkRes) => {
            if (networkRes && networkRes.status === 200) {
              tileCache.put(req, networkRes.clone());
            }
            return networkRes;
          }).catch(() => cached);
        });
      })
    );
    return;
  }

  // 2. APIs do GPS e telemetria: tenta rede primeiro; se offline, recorre ao cache local
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(req).catch(() => caches.match(req))
    );
    return;
  }

  // 3. Arquivos estáticos (HTML, CSS, JS, Imagens): Cache-first com revalidação
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
