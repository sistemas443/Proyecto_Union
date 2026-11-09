/* ==========================================================================
   Tema día / noche - Avícola San Martín
   - Guarda la preferencia en localStorage (asm-tema)
   - Botón en la barra superior ([data-theme-toggle])
   - Adapta los gráficos de Plotly al tema activo
   ========================================================================== */
(function () {
  'use strict';

  var CLAVE = 'asm-tema';
  var raiz = document.documentElement;
  var temporizadorPlotly = null;

  function temaActual() {
    return raiz.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
  }

  function esOscuro() {
    return temaActual() === 'dark';
  }

  function pintarBotones() {
    var oscuro = esOscuro();
    var etiqueta = oscuro ? 'Cambiar a modo día' : 'Cambiar a modo noche';
    document.querySelectorAll('[data-theme-toggle]').forEach(function (boton) {
      boton.setAttribute('aria-pressed', oscuro ? 'true' : 'false');
      boton.setAttribute('aria-label', etiqueta);
      boton.title = etiqueta;
    });
  }

  /* --- Plotly: fondo, ejes y etiquetas según el tema --- */
  function aplicarPlotly() {
    if (!window.Plotly) return;
    var oscuro = esOscuro();
    var fondo = oscuro ? '#1e242b' : '#ffffff';
    var texto = oscuro ? '#c9d3dd' : '#4a5462';
    var base = {
      paper_bgcolor: fondo,
      plot_bgcolor: fondo,
      'font.color': texto,
      'legend.font.color': texto,
      'hoverlabel.bgcolor': oscuro ? '#2b333c' : '#ffffff',
      'hoverlabel.bordercolor': oscuro ? '#46515c' : '#e2e6ea',
      'hoverlabel.font.color': oscuro ? '#e8edf3' : '#2b2f33'
    };

    document.querySelectorAll('.js-plotly-plot').forEach(function (grafico) {
      try {
        Plotly.relayout(grafico, base);
        var layout = grafico._fullLayout || {};
        var ejes = {};
        Object.keys(layout).forEach(function (clave) {
          if (!/^[xy]axis\d*$/.test(clave)) return;
          ejes[clave + '.gridcolor'] = oscuro ? '#2b343d' : '#eef1f5';
          ejes[clave + '.linecolor'] = oscuro ? '#3a444f' : '#dfe3e8';
          ejes[clave + '.zerolinecolor'] = oscuro ? '#3a444f' : '#e5e8eb';
          ejes[clave + '.tickfont.color'] = texto;
          ejes[clave + '.title.font.color'] = texto;
        });
        if (Object.keys(ejes).length) Plotly.relayout(grafico, ejes);
      } catch (e) {
        /* un gráfico a medio construir no debe romper el cambio de tema */
      }
    });
  }

  function programarPlotly() {
    clearTimeout(temporizadorPlotly);
    temporizadorPlotly = setTimeout(aplicarPlotly, 120);
  }

  function aplicarTema(tema, guardar) {
    var nuevo = tema === 'dark' ? 'dark' : 'light';
    raiz.setAttribute('data-bs-theme', nuevo);
    if (guardar !== false) {
      try { localStorage.setItem(CLAVE, nuevo); } catch (e) {}
    }
    pintarBotones();
    programarPlotly();
    document.dispatchEvent(new CustomEvent('asm:tema', { detail: { tema: nuevo } }));
  }

  function alternar() {
    aplicarTema(esOscuro() ? 'light' : 'dark', true);
  }

  document.addEventListener('DOMContentLoaded', function () {
    pintarBotones();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (boton) {
      boton.addEventListener('click', alternar);
    });
    programarPlotly();

    // Los gráficos se crean después de cargar la página: se detectan aquí.
    if (window.MutationObserver) {
      var observador = new MutationObserver(function (mutaciones) {
        for (var i = 0; i < mutaciones.length; i++) {
          var nodos = mutaciones[i].addedNodes;
          for (var j = 0; j < nodos.length; j++) {
            var nodo = nodos[j];
            if (nodo.nodeType !== 1) continue;
            if (nodo.classList && nodo.classList.contains('js-plotly-plot')) {
              programarPlotly();
              return;
            }
            if (nodo.querySelector && nodo.querySelector('.js-plotly-plot')) {
              programarPlotly();
              return;
            }
          }
        }
      });
      observador.observe(document.body, { childList: true, subtree: true });
    }
  });

  // API mínima por si otra vista necesita consultar o fijar el tema.
  window.asmTema = {
    actual: temaActual,
    aplicar: function (tema) { aplicarTema(tema, true); }
  };
})();
