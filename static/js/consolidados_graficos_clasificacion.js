/*
 * Gráficos por categoría de clasificación (Rotura y Acumulados).
 *
 * Cada tarjeta .js-grafico-cat dibuja una línea por lote para su categoría.
 * La selección de lotes es la misma del panel (#clasifChecks): cualquier
 * cambio en la barra de lotes redibuja las 12 tarjetas.
 */
(function () {
  'use strict';

  var COLORES = [
    '#2f7ed8', '#e07b39', '#3ba55d', '#c0392b', '#8e44ad', '#16a2b8',
    '#b8860b', '#d63384', '#5d6d7e', '#2e8b57', '#a0522d', '#1f618d',
    '#7d3c98', '#b9770e', '#117a65', '#922b21', '#2471a3', '#6c3483',
    '#9a7d0a', '#0e6655', '#c2185b', '#00838f', '#5d4037', '#455a64',
    '#827717', '#4e342e', '#00695c', '#283593', '#ad1457', '#37474f'
  ];

  document.addEventListener('DOMContentLoaded', function () {
    var fuente = document.getElementById('datos-clasificacion');
    var contenedores = Array.prototype.slice.call(document.querySelectorAll('.js-grafico-cat'));
    if (!fuente || !contenedores.length || !window.Plotly) return;

    var datos;
    try { datos = JSON.parse(fuente.textContent); } catch (e) { return; }

    var semanas = datos.semanas || [];
    var lotesOrden = datos.lotes || [];
    var categorias = datos.categorias || [];
    var matriz = datos.matriz || {};
    var checks = Array.prototype.slice.call(
      document.querySelectorAll('#clasifChecks .chk-incluir[data-lote]')
    );

    function seleccionados() {
      if (!checks.length) return lotesOrden.slice();
      var activos = checks.filter(function (c) { return c.checked; })
        .map(function (c) { return c.dataset.lote; });
      return lotesOrden.filter(function (lote) { return activos.indexOf(lote) !== -1; });
    }

    function valorEn(semana, lote, clave) {
      var fila = matriz[String(semana)];
      if (!fila) return null;
      var celdasLote = fila[lote];
      if (!celdasLote) return null;
      var valor = celdasLote[clave];
      if (valor === null || valor === undefined || valor === '') return null;
      var numero = Number(valor);
      return isNaN(numero) ? null : numero;
    }

    function dibujar(contenedor, categoria, seleccion) {
      var ancho = contenedor.clientWidth || 400;
      var porFila = Math.max(1, Math.floor(ancho / 62));
      var filas = Math.max(1, Math.ceil(Math.max(seleccion.length, 1) / porFila));
      var margenInferior = Math.min(120, 44 + filas * 12);
      var altoPlot = Math.max(80, 240 - 6 - margenInferior);
      var yLeyenda = -(36 / altoPlot);

      var trazas = seleccion.map(function (lote, indice) {
        var color = COLORES[indice % COLORES.length];
        return {
          x: semanas,
          y: semanas.map(function (s) { return valorEn(s, lote, categoria.clave); }),
          type: 'scatter',
          mode: 'lines+markers',
          name: lote,
          connectgaps: false,
          line: { width: 1.6, color: color },
          marker: { size: 3, color: color },
          hovertemplate:
            '<b>' + lote + '</b><br>Semana %{x}: %{y:,.2f}%<extra></extra>'
        };
      });

      var layout = {
        margin: { l: 46, r: 10, t: 6, b: margenInferior },
        xaxis: {
          title: { text: 'Semana', font: { size: 9 } },
          dtick: 10,
          gridcolor: '#eef1f4',
          zeroline: false,
          tickfont: { size: 9 }
        },
        yaxis: {
          title: { text: categoria.titulo, font: { size: 9 } },
          gridcolor: '#eef1f4',
          zeroline: false,
          rangemode: 'tozero',
          tickfont: { size: 9 }
        },
        hovermode: 'closest',
        legend: {
          orientation: 'h',
          x: 0.5,
          xanchor: 'center',
          y: yLeyenda,
          font: { size: 8 }
        },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#ffffff'
      };

      if (!trazas.length) {
        layout.annotations = [{
          text: 'Selecciona al menos un lote',
          xref: 'paper', yref: 'paper', x: 0.5, y: 0.5,
          showarrow: false, font: { size: 11, color: '#6c757d' }
        }];
      }

      window.Plotly.react(contenedor, trazas, layout, {
        responsive: true,
        displaylogo: false,
        displayModeBar: false
      });
    }

    function dibujarTodo() {
      var seleccion = seleccionados();
      contenedores.forEach(function (contenedor) {
        var clave = contenedor.dataset.cat;
        var categoria = categorias.filter(function (c) { return c.clave === clave; })[0];
        if (categoria) dibujar(contenedor, categoria, seleccion);
      });
    }

    checks.forEach(function (chk) {
      chk.addEventListener('change', dibujarTodo);
    });

    dibujarTodo();
  });
})();
