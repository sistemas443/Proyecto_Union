/* ============================================================
   GESTION AMBIENTAL - Transicion entre paginas

   Salida breve al hacer clic en una tarjeta o en "volver", y entrada
   suave con fade + desplazamiento corto. Sin clones ni morphs: la
   cabecera nunca se oculta ni se mueve de su sitio.
   ============================================================ */
(function () {
  'use strict';

  var DURACION_SALIDA = 140;
  var saliendo = false;

  function paginaActual() {
    return document.querySelector('.ga-page');
  }

  document.addEventListener('click', function (evento) {
    if (evento.defaultPrevented || evento.button !== 0 ||
        evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) {
      return;
    }

    var enlace = evento.target.closest('a[data-vt], a.ga-back, a.ga-crumb');
    if (!enlace) return;
    if (enlace.target && enlace.target !== '_self') return;

    var url;
    try {
      url = new URL(enlace.href, window.location.href);
    } catch (error) {
      return;
    }
    if (url.origin !== window.location.origin) return;

    var contenedor = paginaActual();
    if (!contenedor || saliendo) return;

    evento.preventDefault();
    saliendo = true;
    contenedor.classList.add('is-leaving');

    var destino = url.href;
    window.setTimeout(function () {
      window.location.href = destino;
    }, DURACION_SALIDA);
  }, true);

  // Al volver desde el historial (bfcache) se limpia el estado de salida.
  window.addEventListener('pageshow', function () {
    saliendo = false;
    var contenedor = paginaActual();
    if (contenedor) contenedor.classList.remove('is-leaving');
  });
})();
