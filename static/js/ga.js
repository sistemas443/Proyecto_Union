/* ============================================================
   GESTION AMBIENTAL - Tablero
   Grafico mensual con desglose por tipo de agua, exportacion a
   Excel e impresion a PDF.
   ============================================================ */
(function () {
  'use strict';

  var datos = leerJson('ga-chart-data');
  var exportacion = null;
  var exportacionPendiente = null;

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

  /* ------------------------------------------------------------------
     Librerias pesadas bajo demanda (XLSX, html2canvas, jsPDF)
     ------------------------------------------------------------------ */
  var CDN = {
    xlsx: 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js',
    html2canvas: 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js',
    jspdf: 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js'
  };
  var cargas = {};

  function cargarScript(url) {
    if (cargas[url]) return cargas[url];
    cargas[url] = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = url;
      script.async = true;
      script.onload = function () { resolve(); };
      script.onerror = function () {
        delete cargas[url];
        reject(new Error('No se pudo cargar ' + url));
      };
      document.head.appendChild(script);
    });
    return cargas[url];
  }

  function asegurarXlsx() {
    return typeof XLSX !== 'undefined' ? Promise.resolve() : cargarScript(CDN.xlsx);
  }

  function asegurarPdf() {
    var tareas = [];
    if (typeof html2canvas === 'undefined') tareas.push(cargarScript(CDN.html2canvas));
    if (!(window.jspdf && window.jspdf.jsPDF)) tareas.push(cargarScript(CDN.jspdf));
    return tareas.length ? Promise.all(tareas) : Promise.resolve();
  }

  var PALETA = {
    claro: ['#6E747A', '#8E949A', '#4C5359', '#7A8086', '#5A6168', '#A0A6AC'],
    oscuro: ['#A8AEB4', '#8C9298', '#C6CBD0', '#9AA0A6', '#7A8086', '#B4B9BE']
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

  /* Eje Y compacto: 60.000.000 se muestra como '60 M'. */
  function formatearEje(valor) {
    var absoluto = Math.abs(valor);
    if (absoluto >= 1000000) {
      return formatear(valor / 1000000, absoluto >= 10000000 ? 0 : 1) + ' M';
    }
    return formatear(valor, decimalesEje());
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

    // Línea de referencia visual (por ejemplo "60 Millones"): no evalúa norma.
    if (datos.referencia_valor !== null && datos.referencia_valor !== undefined) {
      lineas.push(linea('Referencia', datos.referencia_valor, datos.referencia_texto));
    }
    return lineas;
  }

  function datasetsDeSeries() {
    var series = datos.series || [];
    var unaSola = series.length === 1;
    var esBarra = datos.tipo_grafico === 'bar';
    var decEtiqueta = (datos.decimales_etiqueta !== undefined &&
                       datos.decimales_etiqueta !== null)
      ? datos.decimales_etiqueta
      : datos.decimales;

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
            return formatear(valor, decEtiqueta);
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
                if (!conjunto) return true;
                if (conjunto._limite) return false;
                if (conjunto._opcional && item.hidden) return false;
                return true;
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
                return formatearEje(valor);
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

  function limpiarNombre(texto) {
    return String(texto || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[\\/:*?"<>|]/g, '-')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function nombreArchivo(extension) {
    var meta = (exportacion && exportacion.meta) || {};
    var partes = [
      'Gestion_Ambiental',
      limpiarNombre(meta.sede || ''),
      limpiarNombre((datos && datos.nombre) ? datos.nombre : ''),
      meta.generado || ''
    ].filter(function (parte) { return parte; });
    return partes.join('_').replace(/_+/g, '_') + '.' + extension;
  }

  /* ------------------------------------------------------------------
     Exportacion bajo demanda
     ------------------------------------------------------------------ */
  function obtenerExportacion() {
    if (exportacion) return Promise.resolve(exportacion);
    if (exportacionPendiente) return exportacionPendiente;

    var url = new URL(window.location.href);
    url.searchParams.set('formato', 'export');

    exportacionPendiente = fetch(url.toString(), {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    }).then(function (respuesta) {
      if (!respuesta.ok) throw new Error('export');
      return respuesta.json();
    }).then(function (datosExport) {
      exportacion = datosExport;
      return datosExport;
    }).finally(function () {
      exportacionPendiente = null;
    });

    return exportacionPendiente;
  }

  /* ------------------------------------------------------------------
     Exportacion a Excel
     ------------------------------------------------------------------ */
  function exportarExcel() {
    Promise.all([asegurarXlsx(), obtenerExportacion()]).then(function (resultados) {
      var exp = resultados[1];
      var libro = XLSX.utils.book_new();

      var hojaResumen = XLSX.utils.json_to_sheet(exp.resumen);
      hojaResumen['!cols'] = [
        { wch: 20 }, { wch: 32 }, { wch: 12 }, { wch: 13 }, { wch: 14 },
        { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 11 }, { wch: 11 },
        { wch: 15 }, { wch: 26 }, { wch: 14 }
      ];
      XLSX.utils.book_append_sheet(libro, hojaResumen, 'Indicadores');

      var serie = exp.serie;
      if (serie && serie.Fechas && serie.Fechas.length) {
        var filas = serie.Fechas.map(function (fecha, i) {
          var fila = { Fecha: fecha };
          if (serie.Tipos && serie.Tipos[i]) {
            fila[serie.Dimension || 'Tipo de agua'] = serie.Tipos[i];
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

      var tabla = exp.tabla;
      if (tabla && tabla.columnas && tabla.filas && tabla.filas.length) {
        var filasTabla = tabla.filas.map(function (fila) {
          var objeto = {};
          tabla.columnas.forEach(function (columna, indice) {
            objeto[columna] = fila[indice];
          });
          return objeto;
        });
        var hojaTabla = XLSX.utils.json_to_sheet(filasTabla, {
          header: tabla.columnas
        });
        hojaTabla['!cols'] = tabla.columnas.map(function (_col, indice) {
          return { wch: indice === 0 ? 22 : 16 };
        });
        XLSX.utils.book_append_sheet(libro, hojaTabla, 'Registros');
      }

      XLSX.writeFile(libro, nombreArchivo('xlsx'));
    }).catch(function () {
      window.alert('No se pudo preparar la exportación. Intenta de nuevo.');
    });
  }

  /* ------------------------------------------------------------------
     Descarga en PDF (grafico + tabla de registros)
     ------------------------------------------------------------------ */
  function recortarTexto(pdf, texto, ancho) {
    var limpio = String(texto === null || texto === undefined ? '' : texto)
      .replace(/\s+/g, ' ').trim();
    if (pdf.getTextWidth(limpio) <= ancho) return limpio;
    var recorte = limpio;
    while (recorte.length > 1 && pdf.getTextWidth(recorte + '...') > ancho) {
      recorte = recorte.slice(0, -1);
    }
    return recorte + '...';
  }

  /**
   * Dibuja la tabla de registros en paginas nuevas del PDF.
   * Se dibuja con texto real (no como imagen) para que quede nitida y
   * seleccionable, y para que las paginas largas sigan siendo legibles.
   */
  function dibujarTablaPdf(pdf, tabla, titulo) {
    var columnas = (tabla && tabla.columnas) || [];
    var filas = (tabla && tabla.filas) || [];
    if (!columnas.length || !filas.length) return;

    var margen = 10;
    var anchoPagina = pdf.internal.pageSize.getWidth();
    var altoPagina = pdf.internal.pageSize.getHeight();
    var ancho = anchoPagina - margen * 2;
    var altoFila = 5.8;
    var altoCabecera = 6.8;
    var limite = Math.min(filas.length, 300);
    var visibles = filas.slice(0, limite);

    var pesos = columnas.map(function (_columna, indice) {
      return indice === 0 ? 1.6 : 1;
    });
    var totalPesos = pesos.reduce(function (suma, peso) { return suma + peso; }, 0);
    var anchos = pesos.map(function (peso) { return ancho * peso / totalPesos; });

    var alinearDerecha = columnas.map(function (_columna, indice) {
      if (indice === 0) return false;
      var valores = visibles.slice(0, 30)
        .map(function (fila) { return fila[indice]; })
        .filter(function (valor) {
          return valor !== null && valor !== undefined && String(valor).trim() !== '';
        });
      if (!valores.length) return true;
      var numericos = valores.filter(function (valor) {
        return /^-?[\d.,\s]+$/.test(String(valor).trim());
      }).length;
      return numericos >= valores.length * 0.6;
    });

    pdf.addPage();
    var y = margen;

    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(11);
    pdf.setTextColor(40, 44, 48);
    pdf.text('Registros de ' + (titulo || ''), margen, y + 4);
    y += 10;

    function cabecera() {
      pdf.setFillColor(52, 56, 61);
      pdf.rect(margen, y, ancho, altoCabecera, 'F');
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(7);
      pdf.setTextColor(244, 241, 236);
      var x = margen;
      columnas.forEach(function (columna, indice) {
        pdf.text(recortarTexto(pdf, String(columna).toUpperCase(),
          anchos[indice] - 3), x + 1.5, y + 4.4);
        x += anchos[indice];
      });
      y += altoCabecera;
    }

    cabecera();

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7);
    visibles.forEach(function (fila, numero) {
      if (y + altoFila > altoPagina - margen) {
        pdf.addPage();
        y = margen;
        cabecera();
        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(7);
      }
      if (numero % 2 === 1) {
        pdf.setFillColor(244, 245, 246);
        pdf.rect(margen, y, ancho, altoFila, 'F');
      }
      pdf.setTextColor(45, 49, 54);
      var x = margen;
      columnas.forEach(function (_columna, indice) {
        var texto = recortarTexto(pdf, fila[indice], anchos[indice] - 3);
        if (alinearDerecha[indice]) {
          pdf.text(texto, x + anchos[indice] - 1.5, y + 4, { align: 'right' });
        } else {
          pdf.text(texto, x + 1.5, y + 4);
        }
        x += anchos[indice];
      });
      y += altoFila;
    });

    if (filas.length > limite) {
      pdf.setTextColor(110, 116, 122);
      pdf.setFontSize(7);
      pdf.text('Mostrando ' + limite + ' de ' + filas.length +
        ' registros. El Excel incluye el detalle completo.',
        margen, Math.min(y + 6, altoPagina - margen));
    }
  }

  function exportarPdf() {
    var panel = document.querySelector('.ga-focus');
    if (!panel) {
      window.print();
      return;
    }

    asegurarPdf().then(function () {
      var jsPDF = window.jspdf && window.jspdf.jsPDF;
      if (typeof html2canvas === 'undefined' || !jsPDF) {
        window.print();
        return null;
      }

      var fondo = esOscuro() ? '#161b21' : '#ffffff';

      // El nombre del archivo incluye la sede y el indicador, que vienen en el
      // JSON de exportacion. Si falla, se genera solo el grafico.
      return obtenerExportacion().catch(function () { return null; }).then(function (exp) {
        return html2canvas(panel, {
          backgroundColor: fondo,
          scale: 1.6,
          useCORS: true,
          logging: false
        }).then(function (lienzo) {
          var pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
          var anchoPagina = pdf.internal.pageSize.getWidth();
          var altoPagina = pdf.internal.pageSize.getHeight();
          var margen = 10;

          var escala = Math.min(
            (anchoPagina - margen * 2) / lienzo.width,
            (altoPagina - margen * 2) / lienzo.height
          );
          var ancho = lienzo.width * escala;
          var alto = lienzo.height * escala;

          pdf.addImage(lienzo.toDataURL('image/jpeg', 0.92), 'JPEG',
            margen, margen, ancho, alto);

          if (exp && exp.tabla) {
            dibujarTablaPdf(pdf, exp.tabla, datos && datos.nombre);
          }

          pdf.save(nombreArchivo('pdf'));
        });
      });
    }).catch(function (error) {
      console.warn('[GA] No se pudo generar el PDF:', error);
      window.print();
    });
  }

  /* ------------------------------------------------------------------
     Registros bajo demanda
     ------------------------------------------------------------------ */
  function escaparHtml(valor) {
    return String(valor === null || valor === undefined ? '' : valor)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function tipoAguaClase(valor) {
    var texto = String(valor || '').toLowerCase();
    if (texto.indexOf('sin tratar') >= 0) return 'cruda';
    if (texto.indexOf('tratada') >= 0) return 'tratada';
    if (texto.indexOf('acueducto') >= 0) return 'acueducto';
    return 'otro';
  }

  function celdaRegistro(valor, esTipo, indice) {
    var contenido = escaparHtml(valor);
    if (esTipo) {
      contenido = '<span class="ga-tag ga-tag-' + tipoAguaClase(valor) + '">' +
        contenido + '</span>';
    }
    return '<td' + (indice > 0 && !esTipo ? ' class="ga-num"' : '') + '>' +
      contenido + '</td>';
  }

  function cargarTabla(detalles) {
    if (!detalles || detalles.dataset.cargada === '1' ||
        detalles.dataset.cargando === '1') {
      return;
    }

    var cargando = document.getElementById('ga-records-loading');
    var tabla = document.getElementById('ga-records-table');
    var head = document.getElementById('ga-records-head');
    var body = document.getElementById('ga-records-body');
    var summary = document.getElementById('ga-records-summary');
    if (!tabla || !head || !body) return;

    detalles.dataset.cargando = '1';
    if (cargando) {
      cargando.hidden = false;
      cargando.textContent = 'Abriendo registros…';
    }

    var url = new URL(window.location.href);
    url.searchParams.set('formato', 'tabla');

    fetch(url.toString(), {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    }).then(function (respuesta) {
      if (!respuesta.ok) throw new Error('tabla');
      return respuesta.json();
    }).then(function (datosTabla) {
      var columnas = (datosTabla && datosTabla.columnas) || [];
      var filas = (datosTabla && datosTabla.filas) || [];

      if (!columnas.length || !filas.length) {
        if (cargando) cargando.textContent = 'Sin registros en el rango seleccionado.';
        return;
      }

      head.innerHTML = columnas.map(function (columna) {
        return '<th scope="col">' + escaparHtml(columna) + '</th>';
      }).join('');

      var esTipo = columnas.map(function (columna) {
        return String(columna).trim().toLowerCase() === 'tipo de agua';
      });

      body.innerHTML = filas.map(function (fila) {
        return '<tr>' + fila.map(function (celda, indice) {
          return celdaRegistro(celda, esTipo[indice], indice);
        }).join('') + '</tr>';
      }).join('');

      tabla.hidden = false;
      if (cargando) cargando.hidden = true;
      if (summary && datos && datos.nombre) {
        summary.textContent = 'Registros de ' + datos.nombre +
          ' (' + filas.length + ')';
      }
      detalles.dataset.cargada = '1';
    }).catch(function () {
      if (cargando) cargando.textContent = 'No se pudieron cargar los registros.';
    }).finally(function () {
      detalles.dataset.cargando = '';
    });
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
      if (icono) icono.className = activo ? 'bx bx-collapse' : 'bx bx-expand-alt';

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

    var registros = document.getElementById('ga-records');
    if (registros) {
      registros.addEventListener('toggle', function () {
        if (registros.open) cargarTabla(registros);
      });
      if (registros.open) cargarTabla(registros);
    }

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
