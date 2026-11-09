/* ==========================================================================
   Comparador de lotes — piloto en Primera semana
   ========================================================================== */
(function () {
  'use strict';

  var cont = document.getElementById('comparadorLotes');
  if (!cont) return;

  var CLAVES = ['lote_b', 'lote_c', 'lote_d'];

  function urlActual() { return new URL(window.location.href); }
  function ir(url) { window.location.href = url.toString(); }

  function conComparacion(url) {
    url.searchParams.set('comparar', '1');
    return url;
  }

  /* Cantidad de lotes (2, 3, 4) */
  var selCantidad = document.getElementById('cmpCantidad');
  if (selCantidad) {
    selCantidad.addEventListener('change', function () {
      var url = conComparacion(urlActual());
      url.searchParams.set('cantidad', this.value);
      ir(url);
    });
  }

  /* Selectores de lote B, C y D */
  document.querySelectorAll('.comparador-select').forEach(function (sel) {
    sel.addEventListener('change', function () {
      var pos = Number(this.dataset.pos);
      var clave = CLAVES[pos - 1];
      if (!clave) return;
      var url = conComparacion(urlActual());
      if (this.value) url.searchParams.set(clave, this.value);
      else url.searchParams.delete(clave);
      ir(url);
    });
  });

  /* Quitar un lote y reacomodar los siguientes */
  document.querySelectorAll('.comparador-quitar').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var pos = Number(this.dataset.pos);
      if (!pos) return;
      var url = conComparacion(urlActual());
      var valores = CLAVES.map(function (clave) {
        return url.searchParams.get(clave) || '';
      });
      valores.splice(pos - 1, 1);
      valores.push('');
      CLAVES.forEach(function (clave, i) {
        if (valores[i]) url.searchParams.set(clave, valores[i]);
        else url.searchParams.delete(clave);
      });
      var cantidad = Math.max(2, Math.min(4, Number(url.searchParams.get('cantidad') || 2) - 1));
      url.searchParams.set('cantidad', cantidad);
      ir(url);
    });
  });

  /* Más columnas / Menos columnas */
  var btnMas = document.getElementById('cmpMasColumnas');
  if (btnMas) {
    btnMas.addEventListener('click', function () {
      var activo = cont.classList.toggle('mas-columnas');
      this.textContent = activo ? 'Menos columnas' : 'Más columnas';
    });
  }

  /* Pantalla completa del comparador */
  var btnFs = document.getElementById('cmpPantalla');

  function estaCompleta() {
    return document.fullscreenElement === cont
      || document.webkitFullscreenElement === cont
      || cont.classList.contains('cmp-fs-fallback');
  }

  function salirCompleta() {
    if (document.fullscreenElement === cont || document.webkitFullscreenElement === cont) {
      var api = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
      if (api) api.call(document);
      return;
    }
    cont.classList.remove('cmp-fs-fallback');
  }

  function pintarBotonFs() {
    if (btnFs) btnFs.textContent = estaCompleta() ? 'Salir' : 'Pantalla completa';
  }

  if (btnFs) {
    btnFs.addEventListener('click', function () {
      if (estaCompleta()) {
        salirCompleta();
        pintarBotonFs();
        return;
      }
      var pedir = cont.requestFullscreen || cont.webkitRequestFullscreen || cont.msRequestFullscreen;
      if (!pedir) {
        cont.classList.add('cmp-fs-fallback');
        pintarBotonFs();
        return;
      }
      try {
        var promesa = pedir.call(cont);
        if (promesa && promesa.catch) {
          promesa.catch(function () {
            cont.classList.add('cmp-fs-fallback');
            pintarBotonFs();
          });
        }
      } catch (e) {
        cont.classList.add('cmp-fs-fallback');
        pintarBotonFs();
        return;
      }
      window.setTimeout(function () {
        if (!document.fullscreenElement && !document.webkitFullscreenElement) {
          cont.classList.add('cmp-fs-fallback');
        }
        pintarBotonFs();
      }, 900);
    });
  }

  document.addEventListener('fullscreenchange', pintarBotonFs);
  document.addEventListener('webkitfullscreenchange', pintarBotonFs);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && cont.classList.contains('cmp-fs-fallback')) {
      cont.classList.remove('cmp-fs-fallback');
      pintarBotonFs();
    }
  });

  /* Scroll vertical compartido entre paneles */
  var tablas = Array.prototype.slice.call(cont.querySelectorAll('.tabla-scroll'));
  var sincronizando = false;
  tablas.forEach(function (tabla) {
    tabla.addEventListener('scroll', function () {
      if (sincronizando) return;
      sincronizando = true;
      tablas.forEach(function (otra) {
        if (otra !== tabla) otra.scrollTop = tabla.scrollTop;
      });
      window.requestAnimationFrame(function () { sincronizando = false; });
    });
  });

  /* Resaltar la misma fila en todos los paneles */
  function indiceFila(fila) {
    return Array.prototype.indexOf.call(fila.parentNode.children, fila);
  }

  cont.addEventListener('mouseover', function (e) {
    var fila = e.target.closest ? e.target.closest('tbody tr') : null;
    if (!fila || !cont.contains(fila)) return;
    var indice = indiceFila(fila);
    cont.querySelectorAll('.comparador-panel tbody tr').forEach(function (tr) {
      tr.classList.toggle('cmp-fila-hover', indiceFila(tr) === indice);
    });
  });

  cont.addEventListener('mouseout', function (e) {
    if (e.target.closest && e.target.closest('tbody tr')) {
      cont.querySelectorAll('tr.cmp-fila-hover').forEach(function (tr) {
        tr.classList.remove('cmp-fila-hover');
      });
    }
  });

  pintarBotonFs();
})();
