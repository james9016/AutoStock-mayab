if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then((reg) => console.log('PWA AutoStock: Service Worker registrado con éxito.', reg.scope))
      .catch((err) => console.error('PWA AutoStock: Error al registrar Service Worker.', err));
  });
}
