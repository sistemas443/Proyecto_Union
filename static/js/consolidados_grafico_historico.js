/*
 * Gráficos históricos de Consolidados: una línea por lote sobre las semanas.
 *
 * Cada tarjeta generada con templates/consolidados/_grafico_historico.html
 * trae un div .js-grafico-consolidado con los datos en un <script
 * type="application/json"> hermano. Este archivo dibuja todas las tarjetas de
 * la página con Plotly y las mantiene sincronizadas con la barra
 * "Lotes incluidos" (los mismos checkboxes .chk-incluir de la tabla).
 */
(function () {
  'use strict';

  var SELECTOR_CHECK = '.chk-incluir[data-lote]';
  var LOTE_POR_DEFECTO = 5;

  var COLORES = [
    '#2f7ed8', '#e07b39', '#3ba55d', '#c0392b', '#8e44ad',
    '#16a2b8', '#b8860b', '#d63384', '#5d6d7e', '#2e8b57',
    '#a0522d', '#1f618d', '#7d3c98', '#b9770e', '#117a65',
    '#922b21', '#2471a3', '#6c3483', '#9a7d0a', '#0e6655'
  ];

  document.addEventListener('DOMContentLoaded', function () {
    var contenedores = Array.prototype.slice.call(
      document.querySelectorAll('.js-grafico-consolidado')
    );
    if (!contenedores.length) return;

    var graficos = contenedores.map(function (cont) {
      var fuente = document.getElementById(cont.dataset.datos || '');
      var datos = null;
      if (fuente) {
        try { datos = JSON.parse(fuente.textContent); } catch (e) { datos = null; }
      }
      return {
        cont: cont,
        datos: datos || {},
        titulo: cont.dataset.titulo || 'Valor',
        dec: parseInt(cont.dataset.dec, 10) || 0,
        sufijo: cont.dataset.sufijo || '',
        factor: parseFloat(cont.dataset.factor) || 1,
        card: cont.closest('.card'),
        tabla: cont.dataset.contenedor
          ? document.getElementById(cont.dataset.contenedor)
          : null
      };
    }).filter(function (g) { return g.datos && g.datos.semanas; });

    if (!graficos.length) return;

    var listo = false;

    function lotesIncluidos(g) {
      var checks = Array.prototype.slice.call(document.querySelectorAll(SELECTOR_CHECK));
      if (!checks.length) return (g.datos.lotes || []).slice();
      var nombres = checks
        .filter(function (chk) { return chk.checked; })
        .map(function (chk) { return chk.dataset.lote; });
      // Respeta el orden de las columnas de la tabla.
      var orden = (g.datos.lotes || []);
      return orden.filter(function (n) { return nombres.indexOf(n) !== -1; });
    }

    function valorEn(g, semana, lote) {
      var fila = (g.datos.matriz || {})[String(semana)];
      if (!fila) return null;
      var crudo = fila[lote];
      if (crudo === null || crudo === undefined || crudo === '') return null;
      var numero = Number(crudo);
      if (isNaN(numero)) return null;
      return numero * g.factor;
    }

    function dibujar(g) {
      if (!window.Plotly) return;

      var semanas = g.datos.semanas || [];
      var nombres = lotesIncluidos(g);
      var hover =
        '<b>%{fullData.name}</b><br>Semana %{x}: ' +
        '%{y:,.' + g.dec + 'f}' + g.sufijo +
        '<extra></extra>';

      var trazas = nombres.map(function (nombre, indice) {
        var color = COLORES[indice % COLORES.length];
        return {
          x: semanas,
          y: semanas.map(function (s) { return valorEn(g, s, nombre); }),
          type: 'scatter',
          mode: 'lines',
          name: nombre,
          connectgaps: false,
          line: { width: 2, color: color },
          marker: { size: 5, color: color },
          hovertemplate: hover
        };
      });

      var layout = {
        margin: { l: 72, r: 24, t: 10, b: 76 },
        xaxis: {
          title: { text: 'Semana' },
          tickmode: 'linear',
          dtick: 5,
          gridcolor: '#eef1f4',
          zeroline: false
        },
        yaxis: {
          title: { text: g.titulo },
          gridcolor: '#eef1f4',
          zeroline: false,
          rangemode: 'tozero',
          tickformat: ',.' + g.dec + 'f'
        },
        hovermode: 'closest',
        legend: {
          orientation: 'h',
          x: 0.5,
          xanchor: 'center',
          y: -0.2,
          font: { size: 10 }
        },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#ffffff'
      };

      if (!trazas.length) {
        layout.annotations = [{
          text: 'Selecciona al menos un lote en la barra de filtros',
          xref: 'paper', yref: 'paper', x: 0.5, y: 0.5,
          showarrow: false, font: { size: 13, color: '#6c757d' }
        }];
      }

      window.Plotly.react(g.cont, trazas, layout, {
        responsive: true,
        displaylogo: false,
        displayModeBar: false
      });
    }

    function dibujarTodo() {
      graficos.forEach(dibujar);
    }

    function ajustarTabla(g) {
      if (!g.tabla) return;
      // En pantalla completa la tarjeta ocupa todo: la tabla no se ve.
      if (document.fullscreenElement || document.webkitFullscreenElement) return;
      var rect = g.tabla.getBoundingClientRect();
      var extra = g.card ? g.card.offsetHeight + 16 : 0;
      g.tabla.style.height =
        Math.max(window.innerHeight - rect.top - extra - 15, 240) + 'px';
    }

    function ajustarTodo() {
      graficos.forEach(ajustarTabla);
    }

    // La selección de lotes es compartida con los TOTALES/PROM de la tabla.
    document.querySelectorAll(SELECTOR_CHECK).forEach(function (chk) {
      chk.addEventListener('change', function () {
        if (!listo) return;
        dibujarTodo();
      });
    });

    // El selector de la barra dispara "change" sobre estos mismos checkboxes,
    // así que no hace falta escuchar los .cl-chk por separado.

    // Botones de pantalla completa de cada tarjeta.
    graficos.forEach(function (g) {
      var boton = g.card ? g.card.querySelector('.cons-fs') : null;
      if (!boton || !g.card || !window.pantallaCompletaGrafico) return;
      boton.addEventListener('click', function () {
        window.pantallaCompletaGrafico(g.card.id, g.cont.id, boton.id);
      });
    });

    // Arranque: si la tabla no trae lotes marcados, se incluyen los primeros
    // para que gráfico y promedios no salgan vacíos.
    var checks = Array.prototype.slice.call(document.querySelectorAll(SELECTOR_CHECK));
    var hayMarcados = checks.some(function (chk) { return chk.checked; });
    if (!hayMarcados && checks.length) {
      checks.slice(0, LOTE_POR_DEFECTO).forEach(function (chk) {
        chk.checked = true;
        chk.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }

    listo = true;
    dibujarTodo();
    ajustarTodo();

    if (window.ResizeObserver) {
      var observador = new ResizeObserver(function () { ajustarTodo(); });
      observador.observe(document.body);
      graficos.forEach(function (g) { if (g.card) observador.observe(g.card); });
    }
    window.addEventListener('resize', ajustarTodo);
    document.addEventListener('fullscreenchange', function () {
      window.setTimeout(ajustarTodo, 120);
    });
  });
})();
