const CACHE_NAME = 'emed-pwa-v1-3-0-konica-fr-se00003';
const ASSETS_TO_CACHE = [
  '/',
  '/?modo=tecnico',
  '/?modo=gestor',
  '/manifest.json',
  '/api/logo',
  '/api/app-icon/192',
  '/api/app-icon/512'
];

function fetchWithTimeout(req, ms) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  return fetch(req, { signal: ctrl.signal }).finally(() => clearTimeout(timer));
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(
        ASSETS_TO_CACHE.map((u) =>
          fetch(u, { credentials: 'include' })
            .then((res) => (res && res.ok ? cache.put(u, res.clone()) : null))
            .catch(() => null)
        )
      )
    )
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

async function atualizarCacheNavegacao(req, cache) {
  try {
    const res = await fetchWithTimeout(req, 15000);
    if (res && res.ok && !res.redirected) {
      const clone = res.clone();
      const txt = await res.clone().text().catch(() => '');
      // Nunca sobrescrever o App Shell logado (index.html) com a tela pequena de login
      const existing = await cache.match('/?modo=tecnico') || await cache.match('/');
      const existingLen = existing ? (await existing.clone().text().catch(() => '')).length : 0;
      if (txt.length >= existingLen || txt.includes('abrirModalOS') || existingLen < 100000) {
        await cache.put(req, clone.clone());
        await cache.put('/?modo=tecnico', clone.clone());
        await cache.put('/', clone);
      }
    }
  } catch (e) {}
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // 1. /api/bootstrap: rede com timeout 3.5s -> fallback instantaneo no cache
  if (url.pathname.startsWith('/api/bootstrap')) {
    event.respondWith(
      fetchWithTimeout(req, 3500)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(req, { ignoreSearch: false }) || await caches.match('/api/bootstrap?slim=1');
          if (cached) return cached;
          return new Response(JSON.stringify({ ok: false, error: 'offline' }), {
            headers: { 'Content-Type': 'application/json' }
          });
        })
    );
    return;
  }

  // 2. Navegacao / App Shell (somente raiz / e /index.html; nunca interceptar /api/imprimir, /proposta/, /nav etc.)
  if (url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached =
          (await cache.match(req)) ||
          (await cache.match('/?modo=tecnico')) ||
          (await cache.match('/')) ||
          (await cache.match(req, { ignoreSearch: true }));
        if (cached) {
          event.waitUntil(atualizarCacheNavegacao(req, cache));
          return cached;
        }
        try {
          const netRes = await fetchWithTimeout(req, 4000);
          if (netRes && netRes.ok) {
            await cache.put(req, netRes.clone());
            await cache.put('/?modo=tecnico', netRes.clone());
            await cache.put('/', netRes.clone());
          }
          return netRes;
        } catch (e) {
          return new Response(
            '<!DOCTYPE html><html><meta charset="utf-8"><body style="font-family:sans-serif;padding:24px;text-align:center;"><h3>EMED App — Modo Offline</h3><p>Abra uma vez conectado para concluir o cache inicial.</p></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        }
      })
    );
    return;
  }

  // 3. Estaticos, manifest e icones: Cache-First com atualizacao silenciosa
  if (!url.pathname.startsWith('/api/') || url.pathname.startsWith('/api/logo') || url.pathname.startsWith('/api/icone-autosave') || url.pathname.startsWith('/api/app-icon/')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(req);
        const netPromise = fetchWithTimeout(req, 3000)
          .then((res) => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => null);
        return cached || (await netPromise) || Response.error();
      })
    );
  }
});
