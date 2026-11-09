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

  /* Aviso sin diálogo nativo (no interrumpe la pantalla completa) */
  function avisar(mensaje) {
    var aviso = cont.querySelector('.comparador-aviso');
    if (!aviso) {
      aviso = document.createElement('span');
      aviso.className = 'comparador-aviso';
      aviso.setAttribute('role', 'alert');
      var barra = cont.querySelector('.comparador-barra');
      if (barra) barra.appendChild(aviso);
    }
    aviso.textContent = mensaje;
    aviso.hidden = false;
    clearTimeout(aviso._temporizador);
    aviso._temporizador = setTimeout(function () { aviso.hidden = true; }, 4000);
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
    sel.dataset.previo = sel.value;
    sel.addEventListener('change', function () {
      var pos = Number(this.dataset.pos);
      var clave = this.dataset.clave;
      if (!clave) return;

      var valor = this.value;
      if (valor) {
        var usados = Array.prototype.map.call(
          document.querySelectorAll('.comparador-select'),
          function (otro) { return otro.value; }
        );
        var repetido = usados.filter(function (v) { return v === valor; }).length > 1;
        if (repetido) {
          avisar('Ese lote ya está en la comparación.');
          this.value = this.dataset.previo || '';
          return;
        }
      }

      var url = conComparacion(urlActual());
      if (valor) url.searchParams.set(clave, valor);
      else url.searchParams.delete(clave);

      // En pantalla completa se carga el panel sin recargar la página
      if (estaCompleta()) {
        cargarPanel(pos, url, this);
      } else {
        ir(url);
      }
    });
  });

  /* Carga un panel por AJAX para no salir de pantalla completa */
  function cargarPanel(pos, url, select) {
    var panel = cont.querySelector('.comparador-panel[data-panel="' + pos + '"]');
    var anterior = select.dataset.previo || '';
    select.disabled = true;
    if (panel) panel.classList.add('cmp-cargando');

    fetch(url.toString(), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (respuesta) {
        if (!respuesta.ok) throw new Error('HTTP ' + respuesta.status);
        return respuesta.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var nuevo = doc.querySelector('.comparador-panel[data-panel="' + pos + '"]');
        if (!nuevo || !panel) throw new Error('Panel no encontrado');

        panel.replaceWith(nuevo);
        conectarScroll();

        // Conserva la altura ya calculada por el comparador
        var otra = cont.querySelector('.comparador-panel .tabla-scroll');
        var nueva = nuevo.querySelector('.tabla-scroll');
        if (otra && nueva && otra !== nueva && otra.style.height) {
          nueva.style.height = otra.style.height;
          nueva.style.maxHeight = otra.style.maxHeight;
        }

        // El botón de quitar aparece cuando el panel ya tiene lote
        var quitar = document.querySelector('.comparador-quitar[data-pos="' + pos + '"]');
        if (quitar) quitar.hidden = !nuevo.querySelector('.tabla-cmp');

        select.dataset.previo = select.value;
        history.replaceState(null, '', url.toString());
        window.dispatchEvent(new Event('resize'));
      })
      .catch(function () {
        select.value = anterior;
        avisar('No se pudo cargar el lote. Intente de nuevo.');
      })
      .finally(function () {
        select.disabled = false;
        var actual = cont.querySelector('.comparador-panel[data-panel="' + pos + '"]');
        if (actual) actual.classList.remove('cmp-cargando');
      });
  }

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
    if (!btnFs) return;
    if (estaCompleta()) {
      btnFs.innerHTML = '<i class="fas fa-compress me-1"></i> <span>Salir de pantalla completa</span>';
      btnFs.title = 'Salir de pantalla completa';
    } else {
      btnFs.innerHTML = '<i class="fas fa-expand me-1"></i> <span>Pantalla completa</span>';
      btnFs.title = 'Ver la comparación en pantalla completa';
    }
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
  var sincronizando = false;

  function tablasActuales() {
    return Array.prototype.slice.call(cont.querySelectorAll('.tabla-scroll'));
  }

  function conectarScroll() {
    tablasActuales().forEach(function (tabla) {
      if (tabla.dataset.cmpScroll === '1') return;
      tabla.dataset.cmpScroll = '1';
      tabla.addEventListener('scroll', function () {
        if (sincronizando) return;
        sincronizando = true;
        tablasActuales().forEach(function (otra) {
          if (otra !== tabla) otra.scrollTop = tabla.scrollTop;
        });
        window.requestAnimationFrame(function () { sincronizando = false; });
      });
    });
  }

  conectarScroll();

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
