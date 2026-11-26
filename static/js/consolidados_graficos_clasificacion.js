/*
 * Gráficos por categoría de clasificación (Rotura y Acumulados).
 *
 * Cada tarjeta .js-grafico-cat dibuja una línea por lote para su categoría.
 * La selección de lotes es la misma del panel (#clasifChecks): cualquier
 * cambio en la barra de lotes actualiza las tarjetas.
 *
 * Rendimiento: las trazas de los 31 lotes se crean una sola vez por tarjeta y
 * los filtros solo alternan su visibilidad con Plotly.restyle (~60 ms por
 * gráfico). Rehacer las trazas con Plotly.react costaba ~200 ms por tarjeta.
 * Además cada tarjeta se dibuja solo al entrar en pantalla y en su propio
 * frame, para que la tabla responda primero.
 *
 * Se usa SVG (tipo 'scatter'), no 'scattergl': el lienzo WebGL se pierde al
 * cambiar la visibilidad o al redimensionar (pantalla completa) y el gráfico
 * quedaba dibujado con los ejes pero sin líneas.
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

  var CONFIG_PLOT = {
    responsive: true,
    displaylogo: false,
    displayModeBar: false
  };

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

    var raf = window.requestAnimationFrame || function (cb) { return window.setTimeout(cb, 16); };

    function seleccionados() {
      if (!checks.length) return lotesOrden.slice();
      return checks.filter(function (c) { return c.checked; })
        .map(function (c) { return c.dataset.lote; });
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

    // Serie de un lote para una categoría (se calcula una vez y se reutiliza).
    function serieDe(lote, clave) {
      return semanas.map(function (s) { return valorEn(s, lote, clave); });
    }

    function layoutDe(categoria) {
      return {
        margin: { l: 46, r: 10, t: 6, b: 46 },
        showlegend: false,
        xaxis: {
          title: { text: 'Semana', font: { size: 9 } },
          dtick: 10,
          gridcolor: '#eef1f4',
          zeroline: false,
          tickfont: { size: 9 }
        },
        yaxis: {
          title: {
            text: categoria.titulo,
            font: { size: 9, color: categoria.color || '#41505f' }
          },
          gridcolor: '#eef1f4',
          zeroline: false,
          rangemode: 'tozero',
          tickfont: { size: 9 },
          hoverformat: ',.2f'
        },
        hovermode: 'closest',
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#ffffff'
      };
    }

    // Trazas fijas de la tarjeta: un traza por lote, visible según la selección.
    // Se usa SVG (no scattergl): el lienzo WebGL se pierde tras restyle/resize
    // y el gráfico queda vacío al entrar a pantalla completa.
    function trazasDe(contenedor, categoria, seleccion) {
      contenedor._layout = layoutDe(categoria);
      return lotesOrden.map(function (lote, indice) {
        var color = COLORES[indice % COLORES.length];
        return {
          x: semanas,
          y: serieDe(lote, categoria.clave),
          type: 'scatter',
          mode: 'lines+markers',
          name: lote,
          visible: seleccion.has(lote),
          connectgaps: false,
          line: { width: 1.6, color: color },
          marker: { size: 3, color: color }
        };
      });
    }

    function categoriaDe(clave) {
      return categorias.filter(function (c) { return c.clave === clave; })[0];
    }

    // Leyenda propia (HTML) encima del gráfico: la de Plotly se dibujaba dentro
    // del área de trazado en pantalla completa y las líneas la atravesaban.
    function crearLeyenda(contenedor) {
      if (contenedor._leyendaEl) return contenedor._leyendaEl;
      var div = document.createElement('div');
      div.className = 'cons-leyenda';
      contenedor.parentNode.insertBefore(div, contenedor);
      contenedor._leyendaEl = div;
      return div;
    }

    function pintarLeyenda(contenedor) {
      var div = crearLeyenda(contenedor);
      while (div.firstChild) div.removeChild(div.firstChild);
      lotesOrden.forEach(function (lote, indice) {
        if (!contenedor._seleccion.has(lote)) return;
        var color = COLORES[indice % COLORES.length];
        var item = document.createElement('span');
        var marca = document.createElement('i');
        marca.style.background = color;
        item.appendChild(marca);
        item.appendChild(document.createTextNode(String(lote)));
        div.appendChild(item);
      });
    }

    // Alterna la visibilidad de las trazas ya creadas (barato).
    function aplicarSeleccion(contenedor) {
      if (!contenedor._trazas) return;
      var flags = lotesOrden.map(function (lote) {
        return contenedor._seleccion.has(lote);
      });
      var sinLotes = flags.every(function (f) { return !f; });

      // Con un cambio pequeño se actualizan solo esas trazas (mitad de costo).
      var previos = contenedor._flags;
      var indices = [];
      if (previos) {
        flags.forEach(function (valor, i) {
          if (previos[i] !== valor) indices.push(i);
        });
      }

      if (previos && indices.length && indices.length <= 4) {
        window.Plotly.restyle(contenedor, {
          visible: indices.map(function (i) { return flags[i]; })
        }, indices);
      } else if (!previos || indices.length) {
        window.Plotly.restyle(contenedor, { visible: flags });
      }
      contenedor._flags = flags;

      if (!previos || indices.length) pintarLeyenda(contenedor);

      // El aviso "Selecciona al menos un lote" es una capa CSS: no re-layout.
      contenedor.classList.toggle('sin-lotes', sinLotes);
    }

    // Primer dibujo de la tarjeta: crea las trazas y aplica la selección.
    function dibujarCont(contenedor) {
      var categoria = categoriaDe(contenedor.dataset.cat);
      if (!categoria) return;
      if (!contenedor._trazas) {
        var seleccion = contenedor._seleccion || new Set(seleccionados());
        contenedor._seleccion = seleccion;
        contenedor._trazas = trazasDe(contenedor, categoria, seleccion);
        // Estado inicial conocido: la visibilidad con la que nacieron las trazas.
        contenedor._flags = lotesOrden.map(function (lote) { return seleccion.has(lote); });
        crearLeyenda(contenedor);
        pintarLeyenda(contenedor);
        window.Plotly.react(contenedor, contenedor._trazas, contenedor._layout, CONFIG_PLOT)
          .then(function () {
            contenedor.dataset.dibujado = '1';
            aplicarSeleccion(contenedor);
          });
        return;
      }
      aplicarSeleccion(contenedor);
    }

    function enPantallaCompleta(contenedor) {
      var card = contenedor.closest('.card');
      return !!card && (document.fullscreenElement === card
        || document.webkitFullscreenElement === card);
    }

    // Cola de dibujo: una tarjeta por frame, para no bloquear el clic.
    var cola = [];
    var colaActiva = false;

    function procesarCola() {
      if (!cola.length) {
        colaActiva = false;
        return;
      }
      var contenedor = cola.shift();
      if (contenedor.dataset.sucio === '1') {
        contenedor.dataset.sucio = '';
        dibujarCont(contenedor);
      }
      raf(procesarCola);
    }

    function encolar(contenedor) {
      if (contenedor.dataset.sucio !== '1') return;
      if (cola.indexOf(contenedor) === -1) cola.push(contenedor);
      if (!colaActiva) {
        colaActiva = true;
        raf(procesarCola);
      }
    }

    function dibujarTodo() {
      var seleccion = seleccionados();
      contenedores.forEach(function (contenedor) {
        contenedor.dataset.sucio = '1';
        contenedor._seleccion = new Set(seleccion);
        // Solo se dibujan los visibles (o el que esté en pantalla completa).
        if (!observador || visibles.has(contenedor) || enPantallaCompleta(contenedor)) {
          encolar(contenedor);
        }
      });
    }

    var pendienteDibujo = null;

    function programarDibujo() {
      if (pendienteDibujo) return;
      pendienteDibujo = raf(function () {
        pendienteDibujo = null;
        dibujarTodo();
      });
    }

    var observador = null;
    var visibles = new Set();

    checks.forEach(function (chk) {
      chk.addEventListener('change', programarDibujo);
    });

    // Pantalla completa de cada tarjeta: incluye la barra de lotes (#clLotes).
    contenedores.forEach(function (contenedor) {
      var card = contenedor.closest('.card');
      var boton = card ? card.querySelector('.cons-fs') : null;
      if (!card || !boton || !window.pantallaCompletaGrafico) return;
      boton.addEventListener('click', function () {
        contenedor._seleccion = new Set(seleccionados());
        contenedor.dataset.sucio = '';
        dibujarCont(contenedor);
        window.pantallaCompletaGrafico(card.id, contenedor.id, boton.id);
      });
    });

    if ('IntersectionObserver' in window) {
      // Render diferido: cada gráfico se dibuja al entrar en pantalla.
      observador = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          var cont = entry.target;
          if (entry.isIntersecting) {
            visibles.add(cont);
            if (cont.dataset.dibujado !== '1' || cont.dataset.sucio === '1') {
              encolar(cont);
            }
          } else {
            visibles.delete(cont);
          }
        });
      }, { rootMargin: '0px' });

      contenedores.forEach(function (cont) {
        cont.dataset.sucio = '1';
        cont.dataset.dibujado = '0';
        observador.observe(cont);
      });
    } else {
      dibujarTodo();
    }
  });
})();
