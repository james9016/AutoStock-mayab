const CACHE_NAME = 'autostock-v1';
const ASSETS = [
  '/mostrador',
  'https://tailwindcss.com'
];

// Instalar el Service Worker y almacenar recursos críticos
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

// Estrategia: Network First (Intenta red, si falla usa caché de bodega)
self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request).catch(() => {
      return caches.match(e.request);
    })
  );
});
