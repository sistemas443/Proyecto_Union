/* ==========================================================================
   Comparador de lotes con paneles embebidos (iframe) — Producción
   ========================================================================== */
(function () {
  'use strict';

  var cont = document.getElementById('comparadorLotes');
  if (!cont) return;

  var CLAVES = ['lote_a', 'lote_b', 'lote_c', 'lote_d'];
  var sincronizando = false;
  var datosLotes = {};
  try {
    var nodoDatos = document.getElementById('comparadorDatosLotes');
    if (nodoDatos) datosLotes = JSON.parse(nodoDatos.textContent || '{}');
  } catch (e) {}

  function urlActual() { return new URL(window.location.href); }
  function ir(url) { window.location.href = url.toString(); }

  function urlIframe(lote) {
    var url = urlActual();
    ['comparar', 'cantidad', 'lote_a', 'lote_b', 'lote_c', 'lote_d'].forEach(function (clave) {
      url.searchParams.delete(clave);
    });
    url.searchParams.set('embed', '1');
    if (lote) url.searchParams.set('lote', lote);
    else url.searchParams.delete('lote');
    return url;
  }

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

  function formatearAves(valor) {
    var numero = Number(valor);
    if (valor === null || valor === undefined || valor === '' || !isFinite(numero)) return '—';
    return numero.toLocaleString('es-CO');
  }

  function iframesActuales() {
    return Array.prototype.slice.call(cont.querySelectorAll('.comparador-iframe'));
  }

  function panelDe(pos) {
    return cont.querySelector('.comparador-panel[data-panel="' + pos + '"]');
  }

  /* Cabecera del panel: lote, aves y variedad */
  function actualizarCabecera(panel, lote) {
    if (!panel) return;
    var nombre = panel.querySelector('.comparador-lote-nombre');
    if (nombre) nombre.textContent = 'Lote ' + (lote || '—');

    var meta = panel.querySelector('.comparador-panel-meta');
    if (!meta) {
      meta = document.createElement('div');
      meta.className = 'comparador-panel-meta';
      meta.innerHTML = '<span class="comparador-aves">Aves: <b>—</b></span>' +
        '<span class="comparador-variedad">—</span>';
      var cabecera = panel.querySelector('.comparador-panel-head');
      if (cabecera) cabecera.appendChild(meta);
    }
    var datos = datosLotes[lote] || {};
    var aves = meta.querySelector('.comparador-aves b');
    var variedad = meta.querySelector('.comparador-variedad');
    if (aves) aves.textContent = formatearAves(datos.aves);
    if (variedad) variedad.textContent = datos.variedad || '—';
    meta.title = 'Aves encasetadas: ' + formatearAves(datos.aves) +
      ' · Variedad: ' + (datos.variedad || '—');
  }

  function crearPlaceholder(panel) {
    var existente = panel.querySelector('.comparador-vacio');
    if (existente) return existente;
    var div = document.createElement('div');
    div.className = 'comparador-vacio';
    div.innerHTML = '<i class="fas fa-hand-pointer"></i><p>Seleccione un lote para comparar</p>';
    panel.appendChild(div);
    return div;
  }

  function crearIframe(pos) {
    var iframe = document.createElement('iframe');
    iframe.className = 'comparador-iframe';
    iframe.dataset.pos = pos;
    iframe.setAttribute('allowfullscreen', '');
    iframe.addEventListener('load', function () { conectarIframe(iframe); });
    return iframe;
  }

  /* Aplica el lote al panel sin recargar la página (mantiene pantalla completa) */
  function aplicarPanel(pos, lote) {
    var panel = panelDe(pos);
    if (!panel) return;
    var iframe = panel.querySelector('.comparador-iframe');
    var vacio = panel.querySelector('.comparador-vacio');

    if (lote) {
      if (vacio) vacio.remove();
      if (!iframe) {
        iframe = crearIframe(pos);
        panel.appendChild(iframe);
      }
      iframe.src = urlIframe(lote).toString();
    } else {
      if (iframe) iframe.remove();
      crearPlaceholder(panel);
    }

    actualizarCabecera(panel, lote);
    var quitar = document.querySelector('.comparador-quitar[data-pos="' + pos + '"]');
    if (quitar) quitar.hidden = !lote;
    ajustarAlturas();
  }

  /* Selectores A, B, C y D */
  document.querySelectorAll('.comparador-select').forEach(function (sel) {
    sel.dataset.previo = sel.value;
    sel.addEventListener('change', function () {
      var pos = Number(this.dataset.pos);
      var clave = this.dataset.clave;
      var valor = this.value;
      if (!clave || isNaN(pos)) return;

      if (valor) {
        var usados = Array.prototype.map.call(
          document.querySelectorAll('.comparador-select'),
          function (otro) { return otro.value; }
        );
        if (usados.filter(function (v) { return v === valor; }).length > 1) {
          avisar('Ese lote ya está en la comparación.');
          this.value = this.dataset.previo || '';
          return;
        }
      }

      var url = urlActual();
      url.searchParams.set('comparar', '1');
      if (valor) url.searchParams.set(clave, valor);
      else url.searchParams.delete(clave);

      aplicarPanel(pos, valor);
      history.replaceState(null, '', url.toString());
      this.dataset.previo = valor;
    });
  });

  /* Cantidad de lotes: se recarga el comparador */
  var selCantidad = document.getElementById('cmpCantidad');
  if (selCantidad) {
    selCantidad.addEventListener('change', function () {
      var url = urlActual();
      url.searchParams.set('comparar', '1');
      url.searchParams.set('cantidad', this.value);
      ir(url);
    });
  }

  /* Quitar un lote y reacomodar los siguientes */
  document.querySelectorAll('.comparador-quitar').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var pos = Number(this.dataset.pos);
      if (!pos) return;
      var url = urlActual();
      url.searchParams.set('comparar', '1');
      var valores = ['lote_b', 'lote_c', 'lote_d'].map(function (clave) {
        return url.searchParams.get(clave) || '';
      });
      valores.splice(pos - 1, 1);
      valores.push('');
      ['lote_b', 'lote_c', 'lote_d'].forEach(function (clave, i) {
        if (valores[i]) url.searchParams.set(clave, valores[i]);
        else url.searchParams.delete(clave);
      });
      var cantidad = Math.max(2, Math.min(4, Number(url.searchParams.get('cantidad') || 2) - 1));
      url.searchParams.set('cantidad', cantidad);
      ir(url);
    });
  });

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
      if (estaCompleta()) { salirCompleta(); pintarBotonFs(); ajustarAlturas(); return; }
      var pedir = cont.requestFullscreen || cont.webkitRequestFullscreen || cont.msRequestFullscreen;
      if (!pedir) {
        cont.classList.add('cmp-fs-fallback');
        pintarBotonFs();
        ajustarAlturas();
        return;
      }
      try {
        var promesa = pedir.call(cont);
        if (promesa && promesa.catch) {
          promesa.catch(function () {
            cont.classList.add('cmp-fs-fallback');
            pintarBotonFs();
            ajustarAlturas();
          });
        }
      } catch (e) {
        cont.classList.add('cmp-fs-fallback');
        pintarBotonFs();
        ajustarAlturas();
        return;
      }
      window.setTimeout(function () {
        if (!document.fullscreenElement && !document.webkitFullscreenElement) {
          cont.classList.add('cmp-fs-fallback');
        }
        pintarBotonFs();
        ajustarAlturas();
      }, 900);
    });
  }

  document.addEventListener('fullscreenchange', function () { pintarBotonFs(); ajustarAlturas(); });
  document.addEventListener('webkitfullscreenchange', function () { pintarBotonFs(); ajustarAlturas(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && cont.classList.contains('cmp-fs-fallback')) {
      cont.classList.remove('cmp-fs-fallback');
      pintarBotonFs();
      ajustarAlturas();
    }
  });

  /* Altura de los iframes para que quepan una o dos filas */
  function ajustarAlturas() {
    var grid = cont.querySelector('.comparador-grid');
    if (!grid) return;
    var iframes = iframesActuales();
    if (!iframes.length) return;

    if (window.innerWidth <= 900) {
      iframes.forEach(function (f) { f.style.height = ''; });
      return;
    }

    var n = Number(selCantidad ? selCantidad.value : 2) || 2;
    var filas = n === 4 ? 2 : 1;
    var rect = grid.getBoundingClientRect();
    var gap = parseFloat(window.getComputedStyle(grid).rowGap) || 10;
    var cabecera = cont.querySelector('.comparador-panel-head');
    var altoCabecera = cabecera ? cabecera.getBoundingClientRect().height : 47;
    var disponible = window.innerHeight - rect.top - 12;
    var altoFila = Math.max(180, Math.floor((disponible - gap * (filas - 1)) / filas));
    var alto = Math.max(140, altoFila - altoCabecera - 2);

    iframes.forEach(function (f) { f.style.height = alto + 'px'; });

    window.setTimeout(function () {
      iframes.forEach(function (f) {
        ajustarInterior(f);
        try { f.contentWindow.dispatchEvent(new Event('resize')); } catch (e) {}
      });
    }, 150);
  }

  /* Ajusta el contenido del iframe cuando cambia su altura (pantalla completa) */
  function ajustarInterior(iframe) {
    try {
      var doc = iframe.contentDocument;
      var win = iframe.contentWindow;
      if (!doc || !win) return;

      var tabla = doc.querySelector('.tabla-scroll');
      if (tabla) {
        var top = tabla.getBoundingClientRect().top;
        var alto = Math.max(120, win.innerHeight - top - 6);
        tabla.style.height = alto + 'px';
        tabla.style.maxHeight = alto + 'px';
      }

      var grafico = doc.getElementById('graficoPlotly') || doc.querySelector('.js-plotly-plot');
      if (grafico) {
        var topGrafico = grafico.getBoundingClientRect().top;
        var altoGrafico = Math.max(160, win.innerHeight - topGrafico - 8);
        grafico.style.height = altoGrafico + 'px';
        if (win.Plotly && win.Plotly.Plots) {
          win.Plotly.Plots.resize(grafico);
        }
      }
    } catch (e) {}
  }

  /* Sincroniza scroll y resaltado de fila entre los paneles */
  function conectarIframe(iframe) {
    try {
      var doc = iframe.contentDocument;
      if (!doc || !doc.body) return;

      if (!doc.getElementById('cmp-estilo')) {
        var estilo = doc.createElement('style');
        estilo.id = 'cmp-estilo';
        estilo.textContent = 'tbody tr.cmp-fila-hover td{background-color:rgba(255,196,80,.35)!important;}';
        (doc.head || doc.documentElement).appendChild(estilo);
      }

      var tabla = doc.querySelector('.tabla-scroll');
      if (tabla && tabla.dataset.cmpScroll !== '1') {
        tabla.dataset.cmpScroll = '1';
        tabla.addEventListener('scroll', function () {
          if (sincronizando) return;
          sincronizando = true;
          iframesActuales().forEach(function (otra) {
            try {
              var t = otra.contentDocument && otra.contentDocument.querySelector('.tabla-scroll');
              if (t && t !== tabla) t.scrollTop = tabla.scrollTop;
            } catch (e) {}
          });
          window.setTimeout(function () { sincronizando = false; }, 40);
        });
      }

      if (doc.body.dataset.cmpHover !== '1') {
        doc.body.dataset.cmpHover = '1';
        doc.addEventListener('mouseover', function (e) {
          var tr = e.target.closest ? e.target.closest('tbody tr') : null;
          if (!tr || !tr.parentNode) return;
          var indice = Array.prototype.indexOf.call(tr.parentNode.children, tr);
          resaltar(indice);
        });
        doc.addEventListener('mouseout', function (e) {
          if (e.target.closest && e.target.closest('tbody tr')) resaltar(-1);
        });
      }

      ajustarInterior(iframe);
    } catch (e) {}
  }

  function resaltar(indice) {
    iframesActuales().forEach(function (iframe) {
      try {
        var doc = iframe.contentDocument;
        if (!doc) return;
        doc.querySelectorAll('tbody tr').forEach(function (tr, i) {
          tr.classList.toggle('cmp-fila-hover', i === indice);
        });
      } catch (e) {}
    });
  }

  function conectarTodos() {
    iframesActuales().forEach(function (iframe) {
      if (iframe.contentDocument && iframe.contentDocument.readyState === 'complete') {
        conectarIframe(iframe);
      }
      iframe.addEventListener('load', function () {
        conectarIframe(iframe);
        ajustarAlturas();
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    conectarTodos();
    ajustarAlturas();
  });
  window.addEventListener('resize', ajustarAlturas);
  window.setTimeout(conectarTodos, 800);
  window.setTimeout(ajustarAlturas, 400);

  pintarBotonFs();
})();
