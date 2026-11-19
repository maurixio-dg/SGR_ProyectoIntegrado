/* Búsqueda dinámica del Tubo, con formulario GET como alternativa accesible. */
(() => {
  const form = document.getElementById('filtros-tubo');
  const field = document.getElementById('buscar-tubo');
  const box = document.getElementById('tubo-tabla');
  if (!form || !field || !box || typeof fetch !== 'function') return;
  let timer;
  let controller;
  field.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(async () => {
      if (controller) controller.abort();
      controller = new AbortController();
      const qs = new URLSearchParams(new FormData(form));
      qs.set('live', '1');
      qs.delete('pagina');
      try {
        const response = await fetch(`${form.action || window.location.pathname}?${qs}`, {
          headers: {'X-Requested-With': 'XMLHttpRequest'}, signal: controller.signal
        });
        if (!response.ok) return;
        const data = await response.json();
        box.innerHTML = data.html;
      } catch (e) {
        if (e.name !== 'AbortError') { /* El formulario GET sigue disponible. */ }
      }
    }, 300);
  });
})();
