/*
 * Pantalla completa para los gráficos Plotly.
 *
 * Uso en la configuración de Plotly:
 *     modeBarButtonsToAdd: [window.botonPantallaCompleta()]
 *
 * El botón pide pantalla completa sobre el propio gráfico y, al entrar o
 * salir, redimensiona el Plotly para que ocupe la pantalla (sin esto el
 * gráfico conserva su tamaño original y queda sobre un fondo vacío).
 */
(function () {
    'use strict';

    // Icono de las cuatro esquinas (mismo que usaban las plantillas)
    var ICONO = 'M80,80 H180 V120 H120 V180 H80 Z M320,80 H420 V180 H380 V120 H320 Z ' +
                'M80,320 H120 V380 H180 V420 H80 Z M380,320 H420 V420 H320 V380 H380 Z';

    function elementoActivo() {
        return document.fullscreenElement || document.webkitFullscreenElement || null;
    }

    function redimensionar(gd) {
        if (!window.Plotly || !window.Plotly.Plots) return;
        // Dos pasadas: el navegador termina de aplicar el tamaño del fullscreen
        window.setTimeout(function () { window.Plotly.Plots.resize(gd); }, 60);
        window.setTimeout(function () { window.Plotly.Plots.resize(gd); }, 320);
    }

    function ajustar() {
        var activo = elementoActivo();

        document.querySelectorAll('.js-plotly-plot').forEach(function (gd) {
            gd.classList.toggle('plot-pantalla-completa', activo === gd);
            redimensionar(gd);
        });
    }

    document.addEventListener('fullscreenchange', ajustar);
    document.addEventListener('webkitfullscreenchange', ajustar);

    window.botonPantallaCompleta = function () {
        return {
            name: 'Pantalla completa',
            title: 'Pantalla completa',
            icon: { width: 500, height: 500, path: ICONO },
            click: function (gd) {
                if (!elementoActivo()) {
                    var pedir = gd.requestFullscreen || gd.webkitRequestFullscreen;
                    if (!pedir) return;
                    var resultado = pedir.call(gd);
                    if (resultado && typeof resultado.catch === 'function') {
                        resultado.catch(function (error) {
                            console.warn('[pantalla completa] No se pudo activar:', error);
                        });
                    }
                } else {
                    var salir = document.exitFullscreen || document.webkitExitFullscreen;
                    if (salir) salir.call(document);
                }
            }
        };
    };

    // Estilos que solo aplican cuando el gráfico está en pantalla completa
    function inyectarEstilos() {
        if (document.getElementById('estilos-pantalla-completa')) return;

        var estilo = document.createElement('style');
        estilo.id = 'estilos-pantalla-completa';
        estilo.textContent = [
            '.js-plotly-plot.plot-pantalla-completa {',
            '  background-color: #ffffff !important;',
            '  width: 100% !important;',
            '  height: 100% !important;',
            '  padding: 10px 14px;',
            '  box-sizing: border-box;',
            '}',
            '.js-plotly-plot:fullscreen { background-color: #ffffff; }',
            '.js-plotly-plot:-webkit-full-screen { background-color: #ffffff; }'
        ].join('\n');

        document.head.appendChild(estilo);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inyectarEstilos);
    } else {
        inyectarEstilos();
    }
})();
