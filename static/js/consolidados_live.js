// Actualiza en sitio las matrices de Consolidados sin recargar la pagina.
// Consulta la version cada 30 s; cuando cambia, vuelve a pedir la vista y
// copia los valores en las celdas existentes. Solo recarga si cambia la
// estructura de la tabla (nueva semana o nuevo lote).
(function () {
  'use strict';

  var INTERVALO_MS = 30000;

  function iniciar() {
    if (!window.location.pathname.startsWith('/consolidados/')) return;
    if (!window.CONSOLIDADOS_VERSION_URL) return;

    // Las vistas con series multiples o estructura distinta no se actualizan
    // en sitio: se dejan como estan para no romper su comportamiento.
    if (document.querySelector('table.serie-tabla')) return;
    var tablas = document.querySelectorAll('table.tabla-compacta');
    if (tablas.length !== 1) return;
    var tablaActual = tablas[0];
    if (!tablaActual.querySelector('tbody tr[data-semana]')) return;

    var versionActual = null;
    var actualizando = false;
    var pendiente = false;

    function filas(tabla) {
      return Array.prototype.slice.call(tabla.querySelectorAll('tbody tr[data-semana]'));
    }

    function lotes(tabla) {
      return Array.prototype.map.call(
        tabla.querySelectorAll('thead .chk-incluir'),
        function (chk) { return chk.dataset.lote; }
      );
    }

    function mismaEstructura(nueva) {
      var lotesActuales = lotes(tablaActual);
      var lotesNuevos = lotes(nueva);
      if (lotesActuales.length !== lotesNuevos.length) return false;
      for (var i = 0; i < lotesActuales.length; i++) {
        if (lotesActuales[i] !== lotesNuevos[i]) return false;
      }
      var filasActuales = filas(tablaActual);
      var filasNuevas = filas(nueva);
      if (filasActuales.length !== filasNuevas.length) return false;
      for (var j = 0; j < filasActuales.length; j++) {
        if (filasActuales[j].dataset.semana !== filasNuevas[j].dataset.semana) return false;
      }
      return true;
    }

    function seRedujo(nueva) {
      return lotes(nueva).length < lotes(tablaActual).length ||
             filas(nueva).length < filas(tablaActual).length;
    }

    function copiarCabeceras(nueva) {
      var filasActuales = tablaActual.querySelectorAll('thead tr');
      var filasNuevas = nueva.querySelectorAll('thead tr');
      var totalFilas = Math.min(filasActuales.length, filasNuevas.length);
      for (var i = 0; i < totalFilas; i++) {
        var celdasActuales = filasActuales[i].children;
        var celdasNuevas = filasNuevas[i].children;
        var totalCeldas = Math.min(celdasActuales.length, celdasNuevas.length);
        for (var j = 0; j < totalCeldas; j++) {
          // El encabezado del lote contiene el checkbox: no se reemplaza.
          if (celdasNuevas[j].querySelector('.chk-incluir')) continue;
          celdasActuales[j].textContent = celdasNuevas[j].textContent;
        }
      }
    }

    function actualizarCeldas(nueva) {
      if (!mismaEstructura(nueva)) return false;


      copiarCabeceras(nueva);

      var filasActuales = filas(tablaActual);
      var filasNuevas = filas(nueva);

      filasActuales.forEach(function (filaActual, indice) {
        var filaNueva = filasNuevas[indice];
        var celdasNuevas = {};
        filaNueva.querySelectorAll('td[data-lote]').forEach(function (celda) {
          celdasNuevas[celda.dataset.lote] = celda;
        });

        filaActual.querySelectorAll('td[data-lote]').forEach(function (celdaActual) {
          var celdaNueva = celdasNuevas[celdaActual.dataset.lote];
          if (!celdaNueva) return;
          celdaActual.textContent = celdaNueva.textContent;
          if (celdaNueva.dataset.valor !== undefined) {
            celdaActual.dataset.valor = celdaNueva.dataset.valor;
          }
        });

        var tablaActualCelda = filaActual.querySelector('td.col-tabla');
        var tablaNuevaCelda = filaNueva.querySelector('td.col-tabla');
        if (tablaActualCelda && tablaNuevaCelda) {
          tablaActualCelda.textContent = tablaNuevaCelda.textContent;
        }
      });

      // Dispara el recalculo de PROM con la logica propia de cada vista.
      var chk = tablaActual.querySelector('.chk-incluir');
      if (chk) chk.dispatchEvent(new Event('change'));
      return true;
    }

    function actualizarVista() {
      if (actualizando) {
        pendiente = true;
        return;
      }
      actualizando = true;

      fetch(window.location.href, { cache: 'no-store' })
        .then(function (resp) {
          if (!resp.ok) return null;
          return resp.text();
        })
        .then(function (html) {
          if (!html) return;
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var tablaNueva = doc.querySelector('table.tabla-compacta');
          if (!tablaNueva) return;
          if (!actualizarCeldas(tablaNueva)) {
            // Si la nueva tabla trae menos filas o lotes, probablemente la
            // carga esta a medias: se espera al siguiente ciclo sin recargar.
            if (seRedujo(tablaNueva)) return;
            // Cambio de estructura (nueva semana o lote): se reconstruye.
            window.location.reload();
          }
        })
        .catch(function () {
          // Silencio: se reintenta en el siguiente ciclo.
        })
        .then(function () {
          actualizando = false;
          if (pendiente) {
            pendiente = false;
            actualizarVista();
          }
        });
    }

    function consultarVersion() {
      if (document.visibilityState !== 'visible' || actualizando) return;

      fetch(window.CONSOLIDADOS_VERSION_URL, { cache: 'no-store' })
        .then(function (resp) {
          if (!resp.ok) return null;
          return resp.json();
        })
        .then(function (data) {
          if (!data || !data.version || data.version === 'error') return;
          if (versionActual === null) {
            versionActual = data.version;
          } else if (data.version !== versionActual) {
            versionActual = data.version;
            actualizarVista();
          }
        })
        .catch(function () {
          // Silencio: no interrumpir si falla la red.
        });
    }

    consultarVersion();
    setInterval(consultarVersion, INTERVALO_MS);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') consultarVersion();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
