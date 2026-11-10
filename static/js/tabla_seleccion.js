// Selección de rango tipo Excel: recuento, suma y promedio por columna.
// Funciona sobre tablas con celdas <input data-col="...">, filas <tr data-id>
// y un contenedor .tabla-scroll. El panel se inserta con
// templates/produccion/_panel_seleccion.html.
(function () {
  'use strict';

  var ETIQUETAS = {
    fecha: 'Fecha',
    fecha_dia: 'Fecha',
    fecha_fin_sem: 'Fecha',
    sem: 'Semana',
    sem_prod: 'Semana',
    dias: 'Días',
    produccion: 'Producción',
    consumo_kg: 'Consumo kilos',
    mortalidad: 'Mortalidad',
    sel: 'Sel',
    otros: 'Otros',
    observaciones: 'Observaciones',
    saldo_aves: 'Saldo aves',
    saldo_ave: 'Saldo aves',
    consumo_gr_a_d: 'Cons. Gr.A.D',
    consumo_gr_a_tab: 'Gr.A.D Tab',
    cons_gr_a_d: 'Cons. Gr.A.D',
    cons_gr_a_tab: 'Gr.A.D Tab',
    percent_diario_prod: '% Prod',
    prom_ave_dia_cc: 'Prom. Ave',
    consumo_agua: 'Agua',
    cons_tab: 'Consumo tabla',
    cons_real: 'Consumo real',
    cons_kilos_real: 'Kilos real',
    cons_kilos_ajustado: 'Kilos ajust.',
    cons_k_acum: 'K. acum.',
    cons_gr_ave_tab: 'Gr. ave tabla',
    cons_gr_ave_ao: 'Gr. ave real',
    cons_gr_ave_tab_acum: 'Gr. ave tab. ac.',
    cons_gr_ave_ac: 'Gr. ave real ac.',
    mort_sem: 'Mort. semanal',
    mort_select_sem: 'Sel.',
    mort_venta: 'Venta',
    porc_mort_sem: '% Mort. sem.',
    porc_mort_acm: '% Mort. acum.',
    porc_mort_acum: '% Mort. acum.',
    peso_tab: 'Peso tabla',
    peso_tabla: 'Peso tabla',
    peso_real: 'Peso real',
    unif_10_menos: '10% menos',
    unif_porc_unif: '% uniformidad',
    porc_uniformidad: '% uniformidad',
    unif_10_mas: '10% más',
    coef_variacion: 'Coef. variación',
    ganancia_ave_dia: 'Gan. ave día',
    ganancia_ave: 'Gan. ave',
    conv_sem: 'Conversión sem.',
    conv_sem_tab: 'Conv. tabla',
    conv_sem_real: 'Conv. real',
    conv_acum_real: 'Conv. acum.',
    kg_sem: 'Kilos semana',
    kg_acum: 'Kilos acum.',
    prod_huevo_sem: 'Huevos semana',
    prod_huevo_tab: 'Huevos tabla',
    prod_huevo_real: 'Huevos real',
    h_av_aloj_real: 'Huevos ave alojada',
    h_av_aloj_tab: 'H.A.A. tabla',
    masa_huevo_real_sem: 'Masa semanal',
    masa_huevo_real_acum: 'Masa acumulada',
    sv: 'Semana/valor',
    clas_jum: 'Jumbo',
    clas_extra: 'Extra',
    clas_aa: 'AA',
    clas_a: 'A',
    clas_b: 'B',
    clas_c: 'C',
    clas_pipo: 'Pipo',
    clas_sucio: 'Sucio',
    clas_totiao: 'Totiao',
    clas_yema: 'Yema',
    clas_segundas: 'Segundas',
    clas_ttl: 'Total',
    acum_jum: 'Acum. jumbo',
    acum_extra: 'Acum. extra',
    acum_aa: 'Acum. AA',
    acum_a: 'Acum. A',
    acum_b: 'Acum. B',
    acum_c: 'Acum. C',
    acum_pipo: 'Acum. pipo',
    acum_sucio: 'Acum. sucio',
    acum_totiao: 'Acum. totiao',
    acum_yema: 'Acum. yema',
    acum_segundas: 'Acum. segundas',
    acum_total: 'Acum. total'
  };

  function etiquetaColumna(columna) {
    if (!columna) return '';
    if (ETIQUETAS[columna]) return ETIQUETAS[columna];
    return columna.replace(/_/g, ' ').replace(/\b\w/g, function (letra) {
      return letra.toUpperCase();
    });
  }

  function iniciar() {
    var contenedores = Array.prototype.filter.call(
      document.querySelectorAll('.tabla-scroll'),
      function (elemento) { return elemento.offsetParent !== null; }
    );
    if (contenedores.length !== 1) return;

    var contenedor = contenedores[0];
    var tabla = contenedor.querySelector('table');
    var panel = document.getElementById('panelSeleccion');
    if (!tabla || !panel) return;

    var cuerpo = tabla.querySelector('tbody');
    if (!cuerpo) return;
    var filas = Array.prototype.slice.call(cuerpo.querySelectorAll('tr[data-id]'));
    if (!filas.length) return;

    var rangoTexto = document.getElementById('seleccionRango');
    var resultados = document.getElementById('seleccionResultados');
    var datos = document.getElementById('seleccionDatos');
    if (!rangoTexto || !resultados || !datos) return;

    var columnaFecha = -1;
    if (filas[0]) {
      for (var i = 0; i < filas[0].cells.length; i++) {
        if (filas[0].cells[i].querySelector('input[data-fecha-original]')) {
          columnaFecha = i;
          break;
        }
      }
    }

    var ancla = null;
    var rango = null;
    var origen = null;
    var pendiente = false;
    var arrastrando = false;
    var celdasMarcadas = [];

    function rectangulo(a, b) {
      return {
        r1: Math.min(a.r, b.r), r2: Math.max(a.r, b.r),
        c1: Math.min(a.c, b.c), c2: Math.max(a.c, b.c)
      };
    }

    function inputDe(fila, columna) {
      if (!fila) return null;
      var celda = fila.cells[columna];
      return celda ? celda.querySelector('input') : null;
    }

    function columnaDe(fila, columna) {
      var input = inputDe(fila, columna);
      return input ? (input.dataset.col || '') : '';
    }

    function parseNumero(valor) {
      if (valor === null || valor === undefined) return null;
      var texto = String(valor).trim();
      if (texto === '') return null;
      if (texto.indexOf(',') !== -1 && texto.indexOf('.') !== -1) {
        texto = texto.replace(/\./g, '').replace(',', '.');
      } else if (texto.indexOf(',') !== -1) {
        texto = texto.replace(',', '.');
      } else if (/^-?\d{1,3}(\.\d{3})+$/.test(texto)) {
        // Formato español de miles sin decimales, por ejemplo 12.345
        texto = texto.replace(/\./g, '');
      }
      if (!/^-?\d+(\.\d+)?$/.test(texto)) return null;
      var numero = parseFloat(texto);
      return isFinite(numero) ? numero : null;
    }

    function formatear(numero) {
      return numero.toLocaleString('es-CO', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      });
    }

    function inputFecha(fila) {
      return fila ? fila.querySelector('input[data-fecha-original]') : null;
    }

    function fechaDeFila(fila) {
      var input = inputFecha(fila);
      var original = input ? (input.getAttribute('data-fecha-original') || '').trim() : '';
      var partes = original.split('-');
      if (partes.length < 3) return null;
      var fecha = new Date(
        parseInt(partes[0], 10),
        parseInt(partes[1], 10) - 1,
        parseInt(partes[2].slice(0, 2), 10)
      );
      return isNaN(fecha.getTime()) ? null : fecha;
    }

    function textoFecha(fecha) {
      if (!fecha) return '';
      return fecha.toLocaleDateString('es-CO', {
        weekday: 'short', day: '2-digit', month: 'short'
      }).replace(/\./g, '');
    }

    function fechaCrudaDe(fila) {
      var input = inputFecha(fila);
      if (!input) return '';
      var original = (input.getAttribute('data-fecha-original') || '').trim();
      return original ? original.split(' ')[0] : String(input.value || '');
    }

    function ajustarAltura() {
      if (typeof window.aplicarAlturaTabla === 'function') {
        window.aplicarAlturaTabla();
      } else {
        window.dispatchEvent(new Event('resize'));
      }
    }

    function limpiarMarcas() {
      celdasMarcadas.forEach(function (celda) {
        celda.classList.remove('celda-seleccionada');
        celda.classList.remove('celda-fecha-seleccionada');
        celda.style.boxShadow = '';
      });
      celdasMarcadas = [];
    }

    function esRangoMultiple() {
      return !!rango && !(rango.r1 === rango.r2 && rango.c1 === rango.c2);
    }

    function ocultarResultados() {
      datos.style.display = 'none';
      resultados.innerHTML = '';
      ajustarAltura();
    }

    function pintar() {
      limpiarMarcas();

      if (!rango) {
        ocultarResultados();
        return;
      }

      for (var r = rango.r1; r <= rango.r2; r++) {
        var fila = filas[r];
        if (!fila) continue;

        for (var c = rango.c1; c <= rango.c2; c++) {
          var celda = fila.cells[c];
          if (!celda) continue;
          celda.classList.add('celda-seleccionada');

          var sombras = [];
          if (r === rango.r1) sombras.push('inset 0 1px 0 0 var(--action-primary)');
          if (r === rango.r2) sombras.push('inset 0 -1px 0 0 var(--action-primary)');
          if (c === rango.c1) sombras.push('inset 1px 0 0 0 var(--action-primary)');
          if (c === rango.c2) sombras.push('inset -1px 0 0 0 var(--action-primary)');
          celda.style.boxShadow = sombras.join(', ');

          celdasMarcadas.push(celda);
        }

        if (columnaFecha >= 0 && fila.cells[columnaFecha]) {
          fila.cells[columnaFecha].classList.add('celda-fecha-seleccionada');
          celdasMarcadas.push(fila.cells[columnaFecha]);
        }
      }

      if (!arrastrando && !pendiente) actualizarPanel();
    }

    function resumirColumna(columna, desde, hasta) {
      var suma = 0;
      var cuenta = 0;
      for (var r = desde; r <= hasta; r++) {
        var input = inputDe(filas[r], columna);
        var valor = input ? parseNumero(input.value) : null;
        if (valor !== null) {
          suma += valor;
          cuenta += 1;
        }
      }
      if (cuenta === 0) return null;
      return { suma: suma, cuenta: cuenta, promedio: suma / cuenta };
    }

    function datoHtml(etiqueta, valor) {
      return '<span class="ps-seleccion-dato"><span class="ps-seleccion-etiqueta">' + etiqueta + ':</span>'
        + '<span class="ps-seleccion-valor">' + valor + '</span></span>';
    }

    function actualizarPanel() {
      if (!esRangoMultiple()) {
        ocultarResultados();
        return;
      }

      var primeraFila = filas[rango.r1];
      var ultimaFila = filas[rango.r2];
      var fechaInicio = textoFecha(fechaDeFila(primeraFila));
      var fechaFin = textoFecha(fechaDeFila(ultimaFila));
      var hayFechas = fechaInicio && fechaFin;

      rangoTexto.textContent = hayFechas ? fechaInicio + ' a ' + fechaFin : '';
      rangoTexto.style.display = hayFechas ? '' : 'none';

      var gruposHtml = '';
      for (var c = rango.c1; c <= rango.c2; c++) {
        var columna = columnaDe(primeraFila, c);
        if (!columna) continue;

        var resumen = resumirColumna(c, rango.r1, rango.r2);
        if (!resumen) continue;

        gruposHtml += '<span class="ps-seleccion-grupo">'
          + '<span class="ps-seleccion-columna">' + etiquetaColumna(columna) + '</span>'
          + datoHtml('Promedio', formatear(resumen.promedio))
          + datoHtml('Recuento', resumen.cuenta)
          + datoHtml('Suma', formatear(resumen.suma))
          + '</span>';
      }

      if (!gruposHtml) {
        gruposHtml = '<span class="ps-seleccion-grupo">La selección no contiene valores numéricos</span>';
      }

      resultados.innerHTML = gruposHtml;
      datos.style.display = 'flex';
      ajustarAltura();
    }

    function limpiarSeleccion() {
      rango = null;
      ancla = null;
      pintar();
    }

    function celdaBajo(x, y) {
      var elemento = document.elementFromPoint(x, y);
      if (!elemento) return null;
      var celda = elemento.closest('td');
      if (!celda) return null;
      var fila = celda.closest('tr[data-id]');
      if (!fila || !cuerpo.contains(fila)) return null;
      return { fila: filas.indexOf(fila), celda: celda };
    }

    function desplazarPorBorde(y) {
      var rect = contenedor.getBoundingClientRect();
      var margen = 32;
      if (y - rect.top < margen) contenedor.scrollTop -= 45;
      else if (rect.bottom - y < margen) contenedor.scrollTop += 45;
    }

    tabla.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      var celda = e.target.closest('td');
      if (!celda) return;
      var fila = celda.closest('tr[data-id]');
      if (!fila || !cuerpo.contains(fila)) return;

      var r = filas.indexOf(fila);
      var c = celda.cellIndex;
      if (r < 0) return;

      if (e.shiftKey && ancla) {
        pendiente = false;
        arrastrando = false;
        rango = rectangulo(ancla, { r: r, c: c });
        pintar();
        return;
      }

      ancla = { r: r, c: c };
      origen = { x: e.clientX, y: e.clientY };
      pendiente = true;
      arrastrando = false;
      rango = { r1: r, c1: c, r2: r, c2: c };
      pintar();
    });

    document.addEventListener('mousemove', function (e) {
      if (!pendiente && !arrastrando) return;

      if (!arrastrando) {
        var distancia = Math.hypot(e.clientX - origen.x, e.clientY - origen.y);
        if (distancia < 5) return;

        arrastrando = true;
        pendiente = false;
        contenedor.classList.add('seleccion-activa');
        var seleccion = window.getSelection();
        if (seleccion) seleccion.removeAllRanges();
        if (document.activeElement && tabla.contains(document.activeElement)) {
          document.activeElement.blur();
        }
      }

      e.preventDefault();
      desplazarPorBorde(e.clientY);

      var destino = celdaBajo(e.clientX, e.clientY);
      if (destino && destino.fila >= 0 && ancla) {
        var siguiente = rectangulo(ancla, { r: destino.fila, c: destino.celda.cellIndex });
        var cambio = !rango || siguiente.r1 !== rango.r1 || siguiente.r2 !== rango.r2 ||
          siguiente.c1 !== rango.c1 || siguiente.c2 !== rango.c2;
        if (cambio) {
          rango = siguiente;
          pintar();
        }
      }
    });

    function terminarArrastre() {
      if (arrastrando) {
        contenedor.classList.remove('seleccion-activa');
        arrastrando = false;
        pintar();
      }
      pendiente = false;
      ajustarAltura();
    }

    document.addEventListener('mouseup', terminarArrastre);
    window.addEventListener('blur', terminarArrastre);

    document.addEventListener('mousedown', function (e) {
      if (!rango) return;
      if (e.target.closest('#panelSeleccion')) return;
      if (tabla.contains(e.target)) return;
      limpiarSeleccion();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && rango) limpiarSeleccion();
    });

    function copiarConRespaldo(texto, alTerminar) {
      var area = document.createElement('textarea');
      area.value = texto;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand('copy');
        alTerminar();
      } catch (err) {
        console.error('No se pudo copiar la selección:', err);
      }
      document.body.removeChild(area);
    }

    function copiarAlPortapapeles(texto, boton) {
      var confirmar = function () {
        var original = boton.innerHTML;
        boton.innerHTML = "<i class='fas fa-check'></i>";
        boton.classList.add('ps-seleccion-ok');
        setTimeout(function () {
          boton.innerHTML = original;
          boton.classList.remove('ps-seleccion-ok');
        }, 1500);
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto)
          .then(confirmar)
          .catch(function () { copiarConRespaldo(texto, confirmar); });
      } else {
        copiarConRespaldo(texto, confirmar);
      }
    }

    document.getElementById('btnCopiarSeleccion').addEventListener('click', function () {
      if (!rango) return;

      var primeraFila = filas[rango.r1];
      var fechaInicio = fechaCrudaDe(primeraFila);
      var fechaFin = fechaCrudaDe(filas[rango.r2]);
      var hayFechas = !!(fechaInicio || fechaFin);
      var filasTexto = [hayFechas
        ? ['Fecha inicio', 'Fecha fin', 'Columna', 'Promedio', 'Recuento', 'Suma']
        : ['Columna', 'Promedio', 'Recuento', 'Suma']];

      for (var c = rango.c1; c <= rango.c2; c++) {
        var columna = columnaDe(primeraFila, c);
        if (!columna) continue;

        var resumen = resumirColumna(c, rango.r1, rango.r2);
        if (!resumen) continue;

        if (hayFechas) {
          filasTexto.push([
            fechaInicio,
            fechaFin,
            etiquetaColumna(columna),
            formatear(resumen.promedio),
            String(resumen.cuenta),
            formatear(resumen.suma)
          ]);
        } else {
          filasTexto.push([
            etiquetaColumna(columna),
            formatear(resumen.promedio),
            String(resumen.cuenta),
            formatear(resumen.suma)
          ]);
        }
      }

      if (filasTexto.length < 2) return;

      var anchos = filasTexto[0].map(function (_, i) {
        return Math.max.apply(null, filasTexto.map(function (fila) {
          return String(fila[i]).length;
        }));
      });
      var lineas = filasTexto.map(function (fila) {
        return fila.map(function (campo, i) {
          return String(campo).padEnd(anchos[i], ' ');
        }).join('   ').trimEnd();
      });

      copiarAlPortapapeles(lineas.join('\n'), this);
    });

    document.getElementById('btnCerrarSeleccion').addEventListener('click', limpiarSeleccion);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
