/*
 * Pantalla completa para los gráficos de los consolidados.
 *
 * Uso:
 *   <div class="card card-pantalla-completa" id="cardGraficoX"> ... </div>
 *   <div class="grafico-fs" id="graficoX"></div>
 *   <button id="btnPantallaX">...</button>
 *
 *   onclick: pantallaCompletaGrafico('cardGraficoX', 'graficoX', 'btnPantallaX')
 *
 * La tarjeta pasa a pantalla completa (con sus controles) y el gráfico se
 * redimensiona al entrar y al salir. El botón cambia el icono expandir/comprimir.
 */
(function () {
    'use strict';

    function redimensionar(contenedor) {
        if (!window.Plotly || !window.Plotly.Plots) return;
        contenedor.querySelectorAll('.js-plotly-plot').forEach(function (gd) {
            [60, 320].forEach(function (ms) {
                window.setTimeout(function () { window.Plotly.Plots.resize(gd); }, ms);
            });
        });
    }

    function cambiarIcono(botonId, activo) {
        if (!botonId) return;
        var boton = document.getElementById(botonId);
        if (!boton) return;
        var icono = boton.querySelector('i');
        if (icono) icono.className = activo ? 'fas fa-compress' : 'fas fa-expand';
        boton.title = activo ? 'Salir de pantalla completa' : 'Ver en pantalla completa';
    }

    /*
     * Si la tarjeta trae data-barra="#selector", ese bloque (la barra de
     * filtros de la página) se mueve dentro de la tarjeta mientras dura la
     * pantalla completa y se devuelve a su sitio al salir. Se mueve el nodo,
     * no se copia, así conserva sus eventos y su estado.
     */
    function moverBarra(card, activo) {
        var selector = card.getAttribute('data-barra');
        if (!selector) return;

        if (activo) {
            var barra = document.querySelector(selector);
            if (!barra || card.contains(barra)) return;
            barra._origen = { padre: barra.parentNode, siguiente: barra.nextSibling };
            var cuerpo = card.querySelector('.card-body') || card;
            cuerpo.insertBefore(barra, cuerpo.firstChild);
            barra.classList.add('barra-en-pantalla');
            return;
        }

        var dentro = card.querySelector(selector);
        if (!dentro || !dentro._origen) return;
        dentro._origen.padre.insertBefore(dentro, dentro._origen.siguiente);
        delete dentro._origen;
        dentro.classList.remove('barra-en-pantalla');
    }

    window.pantallaCompletaGrafico = function (contenedorId, graficoId, botonId) {
        var contenedor = document.getElementById(contenedorId);
        if (!contenedor) return;

        var activo = document.fullscreenElement || document.webkitFullscreenElement;
        if (activo === contenedor) {
            var salir = document.exitFullscreen || document.webkitExitFullscreen;
            if (salir) salir.call(document);
            return;
        }

        contenedor.dataset.fsBoton = botonId || '';

        var pedir = contenedor.requestFullscreen || contenedor.webkitRequestFullscreen;
        if (!pedir) return;

        var promesa = pedir.call(contenedor);
        if (promesa && typeof promesa.catch === 'function') {
            promesa.catch(function (error) {
                console.warn('[pantalla completa] no se pudo activar:', error);
            });
        }
    };

    function alCambiarPantalla() {
        var activo = document.fullscreenElement || document.webkitFullscreenElement;

        document.querySelectorAll('.card-pantalla-completa').forEach(function (card) {
            var esActivo = card === activo;
            card.classList.toggle('pantalla-completa-activa', esActivo);
            cambiarIcono(card.dataset.fsBoton, esActivo);
            moverBarra(card, esActivo);
            redimensionar(card);
        });
    }

    document.addEventListener('fullscreenchange', alCambiarPantalla);
    document.addEventListener('webkitfullscreenchange', alCambiarPantalla);
})();
