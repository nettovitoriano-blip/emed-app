// EmedNav Service Worker - v36 (Logo Oficial @eMED Consolidada nos Alfinetes)
const CACHE_NAME = 'emednav-v36-pure-arroba';

const ASSETS_TO_CACHE = [
  '/',
  '/nav',
  '/gps',
  '/emedcar',
  '/frota',
  '/admin',
  '/manifest.json',
  '/static/index.html',
  '/static/frota.html',
  '/static/manifest.json',
  '/static/leaflet.css',
  '/static/leaflet.js',
  '/static/logo_emed_arroba.png',
  '/static/clientes_offline.json',
  '/static/radares_corredor_offline.json',
  '/static/simbolo_emed_clean.svg',
  '/static/simbolo_emed_red.svg',
  '/static/logo_emed_oficial.png',
  '/static/apple-touch-icon.png',
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

  // REGRA DE OURO PWA:
  // NUNCA interceptar requisições cross-origin (fora do domínio do app)
  // Isso garante que Google Maps Tiles (mt0..mt3.google.com), OpenStreetMap e YouTube
  // sejam carregados diretamente pela rede nativa sem bloqueios de CORS, headers ou Service Worker!
  if (url.origin !== self.location.origin) {
    return;
  }

  // 1. APIs do GPS e telemetria: tenta rede primeiro; se offline, recorre ao cache local
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(req).catch(() => caches.match(req))
    );
    return;
  }

  // 2. Arquivos estáticos locais (HTML, CSS, JS, Imagens da mesma origem)
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) {
        // Revalidação assíncrona em background
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
    }).catch(() => {
      // APENAS redireciona para index.html se for NAVEGAÇÃO de página completa
      if (req.mode === 'navigate') {
        return caches.match('/static/index.html');
      }
    })
  );
});
