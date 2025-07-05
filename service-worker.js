self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('seele-cache').then((cache) => {
      return cache.addAll([
        '/', 
        '/templates/index.html',
        '/static/icon.png', 
      ]).catch((error) => {
        console.error('Cache addAll error:', error);
      });
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});