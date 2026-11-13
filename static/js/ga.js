/* ============================================================
   GESTION AMBIENTAL - Tablero
   Grafico mensual con desglose por tipo de agua, exportacion a
   Excel e impresion a PDF.
   ============================================================ */
(function () {
  'use strict';

  var datos = leerJson('ga-chart-data');
  var exportacion = leerJson('ga-export-data');

  if (typeof Chart !== 'undefined' && window.ChartDataLabels) {
    Chart.register(window.ChartDataLabels);
  }

  function leerJson(id) {
    var nodo = document.getElementById(id);
    if (!nodo) return null;
    try {
      return JSON.parse(nodo.textContent);
    } catch (e) {
      return null;
    }
  }

  function esOscuro() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
  }

  var PALETA = {
    claro: ['#97271C', '#2b6b8f', '#6b7a2f', '#8a5a2b', '#5a4b8a', '#2f7a6b'],
    oscuro: ['#d0574a', '#6aa8c9', '#a3b45a', '#c9905a', '#9a8bc4', '#5fae9c']
  };

  function colorSerie(indice) {
    var paleta = esOscuro() ? PALETA.oscuro : PALETA.claro;
    return paleta[indice % paleta.length];
  }

  function conAlfa(hex, alfa) {
    var limpio = hex.replace('#', '');
    if (limpio.length === 3) {
      limpio = limpio.charAt(0) + limpio.charAt(0) + limpio.charAt(1) +
        limpio.charAt(1) + limpio.charAt(2) + limpio.charAt(2);
    }
    var r = parseInt(limpio.substring(0, 2), 16);
    var g = parseInt(limpio.substring(2, 4), 16);
    var b = parseInt(limpio.substring(4, 6), 16);
    return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alfa + ')';
  }

  function colorUtil(nombre) {
    var oscuro = esOscuro();
    var paleta = {
      limite: oscuro ? '#e0a24a' : '#a3600a',
      texto: oscuro ? '#b6c0ca' : '#4f5a63',
      rejilla: oscuro ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)'
    };
    return paleta[nombre];
  }

  function formatear(valor, decimales) {
    if (valor === null || valor === undefined) return '\u2014';
    var numero = Number(valor);
    var negativo = numero < 0;
    var partes = Math.abs(numero).toFixed(decimales).split('.');
    var entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    var texto = decimales > 0 ? entero + '.' + partes[1] : entero;
    return (negativo ? '-' : '') + texto;
  }

  function decimalesEje() {
    return Math.min(datos.decimales, 2);
  }

  /* ------------------------------------------------------------------
     Grafico principal
     ------------------------------------------------------------------ */
  var grafico = null;

  function datasetsDeLimite() {
    var lineas = [];

    function linea(etiqueta, valor, texto) {
      return {
        type: 'line',
        label: etiqueta,
        data: datos.etiquetas.map(function () { return valor; }),
        borderColor: colorUtil('limite'),
        borderWidth: 1.4,
        borderDash: [6, 4],
        pointRadius: 0,
        pointHitRadius: 0,
        fill: false,
        tension: 0,
        _limite: true,
        datalabels: texto ? {
          display: function (ctx) { return ctx.dataIndex === 0; },
          align: 'right',
          anchor: 'end',
          offset: 4,
          clamp: true,
          color: colorUtil('limite'),
          backgroundColor: esOscuro() ? 'rgba(22,27,33,0.88)' : 'rgba(255,255,255,0.88)',
          borderRadius: 2,
          padding: { top: 1, bottom: 1, left: 3, right: 3 },
          font: { size: 9, weight: '700' },
          formatter: function () { return texto; }
        } : { display: false }
      };
    }

    if (datos.criterio === 'rango') {
      if (datos.limite_min !== null) {
        lineas.push(linea('Límite mínimo', datos.limite_min, datos.etiqueta_limite_min));
      }
      if (datos.limite_max !== null) {
        lineas.push(linea('Límite máximo', datos.limite_max, datos.etiqueta_limite_max));
      }
    } else if (datos.criterio === 'maximo' && datos.limite_max !== null) {
      lineas.push(linea('Límite máximo', datos.limite_max, datos.etiqueta_limite_max));
    } else if (datos.criterio === 'cero') {
      lineas.push(linea('Límite (ausencia)', 0, null));
    }
    return lineas;
  }

  function datasetsDeSeries() {
    var series = datos.series || [];
    var unaSola = series.length === 1;
    var esBarra = datos.tipo_grafico === 'bar';

    return series.map(function (serie, indice) {
      var color = colorSerie(indice);
      var conjunto = {
        type: datos.tipo_grafico || 'line',
        label: serie.nombre,
        data: serie.valores,
        borderColor: color,
        backgroundColor: esBarra ? conAlfa(color, 0.85) : color,
        borderWidth: esBarra ? 0 : 2,
        borderRadius: esBarra ? 2 : 0,
        pointRadius: esBarra ? 0 : (datos.etiquetas.length > 150 ? 0 : 2.4),
        pointHoverRadius: esBarra ? 0 : 5,
        pointBackgroundColor: color,
        fill: !esBarra && unaSola && datos.etiquetas.length <= 24,
        spanGaps: !esBarra,
        tension: 0,
        barPercentage: 0.92,
        categoryPercentage: 0.96,
        datalabels: {
          display: datos.mostrar_valores ? true : false,
          color: color,
          anchor: 'end',
          align: 'top',
          offset: 2,
          clamp: true,
          font: { size: 9, weight: '600' },
          formatter: function (valor) {
            return formatear(valor, datos.decimales);
          }
        }
      };
      return conjunto;
    });
  }

  function tituloEjeY() {
    var titulo = datos.eje_y || 'Valor real';
    var unidad = datos.unidad || '';
    if (unidad && titulo.toLowerCase().indexOf(unidad.toLowerCase()) === -1) {
      titulo += ' (' + unidad + ')';
    }
    return titulo;
  }

  function datasetsOpcionales(inicio) {
    var opcionales = datos.opcionales || [];
    return opcionales.map(function (op, i) {
      var color = colorSerie(inicio + i);
      return {
        type: 'line',
        label: op.nombre,
        data: op.valores,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 1.6,
        borderDash: [4, 3],
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: false,
        spanGaps: true,
        tension: 0,
        hidden: true,
        _opcional: true,
        datalabels: { display: false }
      };
    });
  }

  function aplicarOpcionales() {
    if (!grafico) return;
    var base = (datos.series || []).length;
    var casillas = document.querySelectorAll('[data-serie-opcional]');
    casillas.forEach(function (casilla) {
      var indice = parseInt(casilla.getAttribute('data-serie-opcional'), 10);
      if (isNaN(indice)) return;
      grafico.setDatasetVisibility(base + indice, casilla.checked);
    });
    grafico.update();
  }

  function techoDelEje() {
    var valores = [];
    (datos.series || []).forEach(function (serie) {
      serie.valores.forEach(function (valor) {
        if (valor !== null && valor !== undefined) valores.push(valor);
      });
    });
    if (!valores.length) return undefined;

    var orden = valores.slice().sort(function (a, b) { return a - b; });
    var total = orden.length;
    var maximo = orden[total - 1];

    // El eje cubre todo el rango real; los limites solo se incluyen si no
    // deforman la escala (por ejemplo, sulfatos con limite 250 y datos de 10).
    var techo = maximo > 0 ? maximo * 1.12 : 1;

    if (datos.limite_max !== null && datos.limite_max !== undefined &&
        datos.limite_max <= techo * 2.2) {
      techo = Math.max(techo, datos.limite_max * 1.08);
    }
    return techo;
  }

  function avisarFueraDeEscala(techo) {
    var nota = document.getElementById('ga-chart-note');
    if (!nota) return;
    if (!techo) {
      nota.textContent = '';
      return;
    }
    var fuera = 0;
    (datos.series || []).forEach(function (serie) {
      serie.valores.forEach(function (valor) {
        if (valor !== null && valor !== undefined && valor > techo) fuera++;
      });
    });
    if (!fuera) {
      nota.textContent = '';
      return;
    }
    nota.textContent = fuera === 1
      ? '1 registro supera la escala del gráfico; su valor completo está en la tabla de registros.'
      : fuera + ' registros superan la escala del gráfico; sus valores completos están en la tabla de registros.';
  }

  function pintarGrafico() {
    var lienzo = document.getElementById('ga-chart');
    if (!lienzo || !datos || !datos.etiquetas || !datos.etiquetas.length) return;
    if (typeof Chart === 'undefined') return;

    if (grafico) {
      grafico.destroy();
      grafico = null;
    }

    var conjuntosSeries = datasetsDeSeries();
    var conjuntosOpcionales = datasetsOpcionales(conjuntosSeries.length);
    var conjuntos = conjuntosSeries.concat(conjuntosOpcionales).concat(datasetsDeLimite());
    var techo = techoDelEje();
    avisarFueraDeEscala(techo);

    grafico = new Chart(lienzo.getContext('2d'), {
      type: datos.tipo_grafico === 'bar' ? 'bar' : 'line',
      data: {
        labels: datos.etiquetas,
        datasets: conjuntos
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 420 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: (conjuntosSeries.length + conjuntosOpcionales.length) > 1 ||
              datos.tipo_grafico === 'bar',
            position: 'bottom',
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              color: colorUtil('texto'),
              font: { size: 11 },
              filter: function (item) {
                var conjunto = conjuntos[item.datasetIndex];
                return !(conjunto && conjunto._limite);
              }
            }
          },
          tooltip: {
            callbacks: {
              title: function (items) {
                return items.length ? items[0].label : '';
              },
              label: function (item) {
                return item.dataset.label + ': ' +
                  formatear(item.parsed.y, datos.decimales) + ' ' + datos.unidad;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: colorUtil('texto'),
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 10,
              font: { size: 11 }
            },
            title: {
              display: true,
              text: datos.eje_x || 'Fecha',
              color: colorUtil('texto'),
              font: { size: 10 }
            }
          },
          y: {
            grid: { color: colorUtil('rejilla') },
            border: { display: false },
            max: techo,
            ticks: {
              color: colorUtil('texto'),
              font: { size: 11 },
              callback: function (valor) {
                return formatear(valor, decimalesEje());
              }
            },
            title: {
              display: true,
              text: tituloEjeY(),
              color: colorUtil('texto'),
              font: { size: 10 }
            }
          }
        }
      }
    });

    aplicarOpcionales();
  }

  /* ------------------------------------------------------------------
     Exportacion a Excel
     ------------------------------------------------------------------ */
  function exportarExcel() {
    if (typeof XLSX === 'undefined' || !exportacion) {
      window.alert('No fue posible preparar la exportación.');
      return;
    }

    var libro = XLSX.utils.book_new();

    var hojaResumen = XLSX.utils.json_to_sheet(exportacion.resumen);
    hojaResumen['!cols'] = [
      { wch: 20 }, { wch: 32 }, { wch: 12 }, { wch: 13 }, { wch: 14 },
      { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 11 }, { wch: 11 },
      { wch: 15 }, { wch: 26 }, { wch: 14 }
    ];
    XLSX.utils.book_append_sheet(libro, hojaResumen, 'Indicadores');

    var serie = exportacion.serie;
    if (serie && serie.Fechas && serie.Fechas.length) {
      var filas = serie.Fechas.map(function (fecha, i) {
        var fila = { Fecha: fecha };
        if (serie.Tipos && serie.Tipos[i]) {
          fila['Tipo de agua'] = serie.Tipos[i];
        }
        fila['Valor real'] = serie.Valores[i];
        fila.Unidad = serie.Unidad;
        fila['Cumple norma'] = serie.Cumple[i];
        return fila;
      });
      var hojaSerie = XLSX.utils.json_to_sheet(filas);
      hojaSerie['!cols'] = [{ wch: 14 }, { wch: 16 }, { wch: 14 }, { wch: 14 }, { wch: 14 }];
      XLSX.utils.book_append_sheet(libro, hojaSerie, 'Serie');
    }

    var meta = exportacion.meta || {};
    var nombre = 'Gestion_Ambiental_' + (meta.sede || 'sede') + '_' +
      (meta.generado || '') + '.xlsx';
    XLSX.writeFile(libro, nombre);
  }

  /* ------------------------------------------------------------------
     Impresion a PDF
     ------------------------------------------------------------------ */
  function exportarPdf() {
    window.print();
  }

  /* ------------------------------------------------------------------
     Pantalla completa del indicador
     ------------------------------------------------------------------ */
  function activarPantallaCompleta() {
    var boton = document.getElementById('ga-fullscreen');
    var panel = document.querySelector('.ga-focus');
    if (!boton || !panel || !panel.requestFullscreen) return;

    boton.addEventListener('click', function () {
      if (!document.fullscreenElement) {
        panel.requestFullscreen();
      } else {
        document.exitFullscreen();
      }
    });

    document.addEventListener('fullscreenchange', function () {
      var activo = document.fullscreenElement === panel;
      boton.setAttribute('aria-pressed', activo ? 'true' : 'false');

      var texto = boton.querySelector('.ga-fullscreen-text');
      if (texto) texto.textContent = activo ? 'Salir' : 'Pantalla completa';

      var icono = boton.querySelector('i');
      if (icono) icono.className = activo ? 'bx bx-collapse-alt' : 'bx bx-expand-alt';

      window.setTimeout(function () {
        if (grafico) grafico.resize();
      }, 80);
    });
  }

  /* ------------------------------------------------------------------
     Arranque
     ------------------------------------------------------------------ */
  function conectar() {
    var btnExcel = document.getElementById('ga-export-xlsx');
    var btnPdf = document.getElementById('ga-export-pdf');
    if (btnExcel) btnExcel.addEventListener('click', exportarExcel);
    if (btnPdf) btnPdf.addEventListener('click', exportarPdf);

    pintarGrafico();
    activarPantallaCompleta();

    document.querySelectorAll('[data-serie-opcional]').forEach(function (casilla) {
      casilla.addEventListener('change', aplicarOpcionales);
    });

    // El tema puede cambiar sin recargar: se repintan los colores del grafico.
    var observador = new MutationObserver(function () {
      if (grafico) pintarGrafico();
    });
    observador.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme']
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', conectar);
  } else {
    conectar();
  }
})();
