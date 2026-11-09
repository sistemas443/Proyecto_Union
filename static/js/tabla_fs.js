/* ==========================================================================
   Pantalla completa para las tablas de Producción
   Botones: .js-tabla-fs (opcional data-tabla="#selector")
   ========================================================================== */
(function () {
  'use strict';

  const botones = document.querySelectorAll('.js-tabla-fs');
  if (!botones.length) return;

  function contenedorDe(boton) {
    const selector = boton.getAttribute('data-tabla');
    if (selector) return document.querySelector(selector);
    return document.querySelector('.tabla-scroll');
  }

  function estaActivo(contenedor) {
    return document.fullscreenElement === contenedor
      || document.webkitFullscreenElement === contenedor
      || contenedor.classList.contains('tabla-fs-fallback');
  }

  function pintar(boton, contenedor) {
    const activo = estaActivo(contenedor);
    const icono = boton.querySelector('i');
    const texto = boton.querySelector('span');
    if (icono) icono.className = 'fas ' + (activo ? 'fa-compress' : 'fa-expand');
    if (texto) texto.textContent = activo ? 'Salir' : 'Pantalla completa';
    boton.title = activo ? 'Salir de pantalla completa' : 'Ver la tabla en pantalla completa';
    boton.setAttribute('aria-pressed', activo ? 'true' : 'false');
    const salir = contenedor.querySelector('.tabla-fs-salir');
    if (salir) salir.style.display = activo ? 'inline-flex' : 'none';
  }

  function salir(contenedor) {
    const apiSalir = document.exitFullscreen
      || document.webkitExitFullscreen
      || document.msExitFullscreen;
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      if (apiSalir) apiSalir.call(document);
      return;
    }
    if (contenedor.classList.contains('tabla-fs-fallback')) {
      contenedor.classList.remove('tabla-fs-fallback');
      document.body.classList.remove('tabla-fs-abierta');
    }
  }

  function activarRespaldo(contenedor) {
    contenedor.classList.add('tabla-fs-fallback');
    document.body.classList.add('tabla-fs-abierta');
  }

  botones.forEach(function (boton) {
    const contenedor = contenedorDe(boton);
    if (!contenedor) return;

    if (!contenedor.querySelector('.tabla-fs-salir')) {
      const salirBtn = document.createElement('button');
      salirBtn.type = 'button';
      salirBtn.className = 'btn btn-sm tabla-fs-salir';
      salirBtn.innerHTML = '<i class="fas fa-compress"></i> Salir';
      salirBtn.title = 'Salir de pantalla completa';
      salirBtn.addEventListener('click', function () {
        salir(contenedor);
        pintar(boton, contenedor);
      });
      contenedor.appendChild(salirBtn);
    }

    boton.addEventListener('click', function () {
      if (estaActivo(contenedor)) {
        salir(contenedor);
        return;
      }
      const pedir = contenedor.requestFullscreen
        || contenedor.webkitRequestFullscreen
        || contenedor.msRequestFullscreen;
      if (!pedir) {
        activarRespaldo(contenedor);
        pintar(boton, contenedor);
        return;
      }
      try {
        const promesa = pedir.call(contenedor);
        if (promesa && promesa.catch) {
          promesa.catch(function () {
            activarRespaldo(contenedor);
            pintar(boton, contenedor);
          });
        }
      } catch (e) {
        activarRespaldo(contenedor);
        pintar(boton, contenedor);
        return;
      }
      // Si el navegador no responde a la API, se usa el modo de respaldo
      setTimeout(function () {
        if (!document.fullscreenElement && !document.webkitFullscreenElement
            && !contenedor.classList.contains('tabla-fs-fallback')) {
          activarRespaldo(contenedor);
          pintar(boton, contenedor);
        }
      }, 900);
    });

    function actualizar() {
      contenedor.classList.remove('tabla-fs-fallback');
      document.body.classList.remove('tabla-fs-abierta');
      pintar(boton, contenedor);
    }
    document.addEventListener('fullscreenchange', actualizar);
    document.addEventListener('webkitfullscreenchange', actualizar);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && contenedor.classList.contains('tabla-fs-fallback')) {
        salir(contenedor);
        actualizar();
      }
    });

    pintar(boton, contenedor);
  });
})();
