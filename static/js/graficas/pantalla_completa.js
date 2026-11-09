/*
 * Pantalla completa para los gráficos Plotly de Producción.
 *
 * Uso en la configuración de Plotly:
 *     modeBarButtonsToAdd: [window.botonPantallaCompleta()]
 *
 * Se pone en pantalla completa la tarjeta del gráfico (.card-grafico) para
 * que la ficha del lote (nutricionista, variedad, marca) también se vea.
 * Si el navegador no permite la API, se usa un modo de respaldo.
 */
(function () {
    'use strict';

    // Icono de las cuatro esquinas
    var ICONO = 'M80,80 H180 V120 H120 V180 H80 Z M320,80 H420 V180 H380 V120 H320 Z ' +
                'M80,320 H120 V380 H180 V420 H80 Z M380,320 H420 V420 H320 V380 H380 Z';

    var temporizadorRespaldo = null;

    function elementoActivo() {
        return document.fullscreenElement || document.webkitFullscreenElement || null;
    }

    function contenedorDe(gd) {
        return gd.closest('.card-grafico') || gd;
    }

    function activoEn(contenedor) {
        return elementoActivo() === contenedor
            || contenedor.classList.contains('pantalla-fs-fallback');
    }

    function redimensionar(gd, retardos) {
        if (!window.Plotly || !window.Plotly.Plots) return;
        (retardos || [60, 320]).forEach(function (ms) {
            window.setTimeout(function () { window.Plotly.Plots.resize(gd); }, ms);
        });
    }

    function clonarFranja(contenedor) {
        if (contenedor.querySelector('.ps-franja-fs')) return;
        var franja = document.querySelector('.ps-franja-lote');
        if (!franja) return;
        var clon = franja.cloneNode(true);
        clon.classList.remove('collapse', 'show');
        clon.classList.add('ps-franja-fs');
        clon.removeAttribute('id');
        var cuerpo = contenedor.querySelector('.card-body');
        if (cuerpo) contenedor.insertBefore(clon, cuerpo);
        else contenedor.appendChild(clon);
    }

    function quitarFranja(contenedor) {
        var clon = contenedor.querySelector('.ps-franja-fs');
        if (clon) clon.parentNode.removeChild(clon);
    }

    function agregarSalir(contenedor) {
        if (contenedor.querySelector('.grafico-fs-salir')) return;
        var boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'btn btn-sm grafico-fs-salir';
        boton.innerHTML = '<i class="fas fa-compress"></i> Salir';
        boton.title = 'Salir de pantalla completa';
        boton.addEventListener('click', function () { salir(contenedor); });
        contenedor.appendChild(boton);
    }

    function quitarSalir(contenedor) {
        var boton = contenedor.querySelector('.grafico-fs-salir');
        if (boton) boton.parentNode.removeChild(boton);
    }

    function reajustarNormal() {
        if (elementoActivo()) return;
        document.querySelectorAll('.js-plotly-plot').forEach(function (gd) {
            if (gd.closest('.pantalla-fs-fallback')) return;
            var rect = gd.getBoundingClientRect();
            var alto = Math.max(240, window.innerHeight - rect.top - 15);
            gd.style.height = alto + 'px';
            if (window.Plotly) window.Plotly.Plots.resize(gd);
        });
    }

    function limpiar(contenedor, gd) {
        contenedor.classList.remove('pantalla-fs-fallback');
        quitarFranja(contenedor);
        quitarSalir(contenedor);
        document.body.classList.remove('grafico-fs-abierta');
        if (gd) redimensionar(gd, [120, 380]);
    }

    function alCambiarPantalla() {
        var activo = elementoActivo();
        document.querySelectorAll('.js-plotly-plot').forEach(function (gd) {
            var contenedor = contenedorDe(gd);
            if (activo && activo.contains(gd)) {
                contenedor.classList.remove('pantalla-fs-fallback');
                clonarFranja(contenedor);
                agregarSalir(contenedor);
                redimensionar(gd, [60, 320, 650]);
            } else {
                limpiar(contenedor, gd);
            }
        });
        if (!activo) reajustarNormal();
    }

    function salir(contenedor) {
        if (elementoActivo() === contenedor) {
            var apiSalir = document.exitFullscreen || document.webkitExitFullscreen
                || document.msExitFullscreen;
            if (apiSalir) apiSalir.call(document);
            return;
        }
        if (contenedor.classList.contains('pantalla-fs-fallback')) {
            limpiar(contenedor, contenedor.querySelector('.js-plotly-plot'));
            reajustarNormal();
        }
    }

    function activarRespaldo(contenedor) {
        if (contenedor.classList.contains('pantalla-fs-fallback')) return;
        contenedor.classList.add('pantalla-fs-fallback');
        document.body.classList.add('grafico-fs-abierta');
        clonarFranja(contenedor);
        agregarSalir(contenedor);
        var gd = contenedor.querySelector('.js-plotly-plot');
        if (gd) redimensionar(gd, [60, 320]);
    }

    function activar(contenedor) {
        if (activoEn(contenedor)) {
            salir(contenedor);
            return;
        }
        var pedir = contenedor.requestFullscreen || contenedor.webkitRequestFullscreen
            || contenedor.msRequestFullscreen;
        if (!pedir) {
            activarRespaldo(contenedor);
            return;
        }
        var promesa;
        try {
            promesa = pedir.call(contenedor);
        } catch (e) {
            activarRespaldo(contenedor);
            return;
        }
        if (promesa && typeof promesa.catch === 'function') {
            promesa.catch(function () { activarRespaldo(contenedor); });
        }
        clearTimeout(temporizadorRespaldo);
        temporizadorRespaldo = window.setTimeout(function () {
            if (!elementoActivo()) activarRespaldo(contenedor);
        }, 900);
    }

    window.botonPantallaCompleta = function () {
        return {
            name: 'Pantalla completa',
            title: 'Pantalla completa',
            icon: { width: 500, height: 500, path: ICONO },
            click: function (gd) { activar(contenedorDe(gd)); }
        };
    };

    // API mínima (también usada por las pruebas y por otras vistas)
    window.graficoPantallaCompleta = {
        activar: function (id) {
            var gd = document.getElementById(id || 'graficoPlotly');
            if (gd) activar(contenedorDe(gd));
        },
        salir: function () {
            document.querySelectorAll('.card-grafico.pantalla-fs-fallback').forEach(function (contenedor) {
                salir(contenedor);
            });
        }
    };

    document.addEventListener('fullscreenchange', alCambiarPantalla);
    document.addEventListener('webkitfullscreenchange', alCambiarPantalla);

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        document.querySelectorAll('.card-grafico.pantalla-fs-fallback').forEach(function (contenedor) {
            salir(contenedor);
        });
    });

    document.addEventListener('shown.bs.collapse', function (e) {
        if (e.target && e.target.id === 'franjaLoteGrafico') reajustarNormal();
    });
    document.addEventListener('hidden.bs.collapse', function (e) {
        if (e.target && e.target.id === 'franjaLoteGrafico') reajustarNormal();
    });
})();
