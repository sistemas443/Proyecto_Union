// Tabla visual del Día 2 de Primera Semana.
// Genera, guarda y elimina las filas de primera_semana_dia2 sin tocar la tabla oficial.
(function () {
  'use strict';

  var cfg = window.PRIMERA_DIA2 || {};
  var contenedor = document.getElementById('tablaDia2Contenedor');
  var wrap = document.getElementById('wrapDia2');

  function limpiarValor(input, valor) {
    if (input.dataset && input.dataset.miles !== undefined && typeof window.limpiarMiles === 'function') {
      return window.limpiarMiles(valor);
    }
    return valor;
  }

  function marcar(input, color) {
    if (!input) return;
    var original = input.style.backgroundColor;
    input.style.backgroundColor = color;
    setTimeout(function () {
      input.style.backgroundColor = original || 'transparent';
    }, 900);
  }

  var CLAVES_ENTERAS = {
    saldo_aves: true,
    cons_k_acum: true,
    cons_gr_ave_tab_acum: true
  };

  function formatearMiles(numero) {
    return Math.round(numero).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function formatearCalculado(clave, valor) {
    if (valor === null || valor === undefined || valor === '') return '';
    var numero = parseFloat(String(valor).replace(',', '.'));
    if (!isFinite(numero) || numero === 0) return '';
    if (CLAVES_ENTERAS[clave]) return formatearMiles(numero);
    return numero.toFixed(2);
  }

  function actualizarCalculados(fila, datos) {
    if (!datos) return;
    Object.keys(datos).forEach(function (clave) {
      var celda = fila.querySelector('.celda-' + clave);
      if (!celda) return;
      celda.value = formatearCalculado(clave, datos[clave]);
    });
  }

  // ---------------- Guardado en línea ----------------
  if (contenedor) {
    contenedor.querySelectorAll('input[data-col]:not([readonly])').forEach(function (input) {
      input.addEventListener('change', function () {
        var fila = this.closest('tr');
        if (!fila || !fila.dataset.id) return;

        var id = fila.dataset.id;
        var columna = this.dataset.col;
        var valor = limpiarValor(this, this.value);

        fetch(cfg.apiActualizar, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id, columna: columna, valor: valor })
        })
          .then(function (respuesta) { return respuesta.json(); })
          .then(function (data) {
            if (data.status === 'ok') {
              marcar(input, 'rgba(40, 167, 69, 0.2)');
              actualizarCalculados(fila, data.updated_data);

              // El servidor devuelve todas las filas: actualizamos también
              // los acumulados de las filas siguientes.
              if (Array.isArray(data.filas)) {
                data.filas.forEach(function (f) {
                  var tr = contenedor.querySelector('tr[data-id="' + f.id_diario + '"]');
                  if (!tr) return;
                  actualizarCalculados(tr, {
                    porc_mort_sem: f.porc_mort_sem,
                    porc_mort_acum: f.porc_mort_acum,
                    saldo_aves: f.saldo_aves,
                    consumo_gr_a_d: f.consumo_gr_a_d,
                    cons_k_acum: f.cons_k_acum,
                    cons_gr_ave_tab_acum: f.cons_gr_ave_tab_acum,
                    cons_gr_ave_ac: f.cons_gr_ave_ac
                  });
                });
              }
            } else {
              marcar(input, 'rgba(220, 53, 69, 0.2)');
              alert('Error al guardar el Día 2:\n' + (data.msg || 'Error desconocido'));
            }
          })
          .catch(function (error) {
            console.error('Error de red guardando Día 2:', error);
            marcar(input, 'rgba(220, 53, 69, 0.2)');
          });
      });
    });
  }

  // ---------------- Fecha inicial y columna completa ----------------
  function sumarDias(iso, dias) {
    var partes = String(iso).split('-');
    if (partes.length < 3) return '';
    var fecha = new Date(parseInt(partes[0], 10), parseInt(partes[1], 10) - 1, parseInt(partes[2], 10));
    if (isNaN(fecha.getTime())) return '';
    fecha.setDate(fecha.getDate() + dias);
    var anio = fecha.getFullYear();
    var mes = ('0' + (fecha.getMonth() + 1)).slice(-2);
    var dia = ('0' + fecha.getDate()).slice(-2);
    return anio + '-' + mes + '-' + dia;
  }

  function formatearFechaVisual(iso) {
    var partes = String(iso).split('-');
    if (partes.length < 3) return '';
    var fecha = new Date(parseInt(partes[0], 10), parseInt(partes[1], 10) - 1, parseInt(partes[2], 10));
    if (isNaN(fecha.getTime())) return '';
    var texto = fecha.toLocaleDateString('es-ES', {
      weekday: 'short', day: '2-digit', month: 'short'
    }).replace(/\./g, '');
    var trozos = texto.replace(',', '').split(' ');
    return trozos.length >= 3 ? trozos[0] + ', ' + trozos[1] + '-' + trozos[2] : texto;
  }

  function actualizarFechasDesde(iso) {
    if (!contenedor) return;
    var filas = contenedor.querySelectorAll('tbody tr[data-id]');
    filas.forEach(function (fila, indice) {
      var input = fila.querySelector('input[data-fecha-original]');
      if (!input) return;
      var nueva = sumarDias(iso, indice);
      input.setAttribute('data-fecha-original', nueva);
      if (input.hasAttribute('data-fecha-dia2-inicio')) {
        input.value = nueva;
      } else {
        input.value = formatearFechaVisual(nueva);
      }
    });
  }

  function aplicarFechasDelServidor(filas) {
    if (!contenedor || !Array.isArray(filas)) return;
    filas.forEach(function (f) {
      var fila = contenedor.querySelector('tr[data-id="' + f.id_diario + '"]');
      if (!fila) return;
      var input = fila.querySelector('input[data-fecha-original]');
      if (!input) return;
      input.setAttribute('data-fecha-original', f.fecha_dia);
      if (input.hasAttribute('data-fecha-dia2-inicio')) {
        input.value = f.fecha_dia;
      } else {
        input.value = formatearFechaVisual(f.fecha_dia);
      }
    });
  }

  var inputFechaInicio = contenedor
    ? contenedor.querySelector('input[data-fecha-dia2-inicio]')
    : null;
  if (inputFechaInicio) {
    inputFechaInicio.addEventListener('change', function () {
      var iso = this.value;
      if (!iso) return;

      actualizarFechasDesde(iso);

      fetch(cfg.apiFecha, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lote: cfg.lote, fecha: iso })
      })
        .then(function (respuesta) { return respuesta.json(); })
        .then(function (data) {
          if (data.status === 'ok' && Array.isArray(data.filas)) {
            aplicarFechasDelServidor(data.filas);
          } else {
            alert('No se pudo actualizar la fecha:\n' + (data.msg || 'Error desconocido'));
            window.location.reload();
          }
        })
        .catch(function (error) {
          console.error('Error de red actualizando la fecha:', error);
          alert('No se pudo conectar con el servidor.');
          window.location.reload();
        });
    });
  }

  // ---------------- Generar ----------------
  var btnGenerar = document.getElementById('btnGenerarDia2');
  if (btnGenerar) {
    btnGenerar.addEventListener('click', function () {
      if (!cfg.lote) return;
      var original = btnGenerar.innerHTML;
      btnGenerar.disabled = true;
      btnGenerar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';

      fetch(cfg.apiGenerar, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lote: cfg.lote })
      })
        .then(function (respuesta) { return respuesta.json(); })
        .then(function (data) {
          if (data.status === 'ok') {
            window.location.reload();
            return;
          }
          alert('No se pudo generar el Día 2:\n' + (data.msg || 'Error desconocido'));
          btnGenerar.disabled = false;
          btnGenerar.innerHTML = original;
        })
        .catch(function (error) {
          console.error('Error de red generando Día 2:', error);
          alert('No se pudo conectar con el servidor.');
          btnGenerar.disabled = false;
          btnGenerar.innerHTML = original;
        });
    });
  }

  // ---------------- Mostrar / ocultar ----------------
  var btnToggle = document.getElementById('btnToggleDia2');
  if (btnToggle && wrap) {
    btnToggle.addEventListener('click', function () {
      var oculta = wrap.style.display === 'none';
      wrap.style.display = oculta ? '' : 'none';
      btnToggle.innerHTML = oculta
        ? '<i class="fas fa-eye-slash"></i> <span>Ocultar día 2</span>'
        : '<i class="fas fa-eye"></i> <span>Mostrar día 2</span>';

      // Si se oculta mientras hay una selección activa, limpiamos el panel.
      if (!oculta) {
        var cerrar = document.getElementById('btnCerrarSeleccion');
        if (cerrar) cerrar.click();
      }

      if (typeof window.ajustarAlturaPrimeraSemana === 'function') {
        window.ajustarAlturaPrimeraSemana();
      }
    });
  }

  // ---------------- Eliminar ----------------
  var btnEliminar = document.getElementById('btnEliminarDia2');
  if (btnEliminar) {
    btnEliminar.addEventListener('click', function () {
      if (!cfg.lote) return;
      if (!window.confirm('¿Eliminar la tabla del Día 2 del lote ' + cfg.lote + '?\n\nEsta acción borra los datos guardados en esa tabla.')) {
        return;
      }

      var original = btnEliminar.innerHTML;
      btnEliminar.disabled = true;
      btnEliminar.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      fetch(cfg.apiEliminar, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lote: cfg.lote })
      })
        .then(function (respuesta) { return respuesta.json(); })
        .then(function (data) {
          if (data.status === 'ok') {
            window.location.reload();
            return;
          }
          alert('No se pudo eliminar el Día 2:\n' + (data.msg || 'Error desconocido'));
          btnEliminar.disabled = false;
          btnEliminar.innerHTML = original;
        })
        .catch(function (error) {
          console.error('Error de red eliminando Día 2:', error);
          alert('No se pudo conectar con el servidor.');
          btnEliminar.disabled = false;
          btnEliminar.innerHTML = original;
        });
    });
  }
  // ---------------- Seleccionar tabla activa ----------------
  document.querySelectorAll('.js-usar-tabla').forEach(function (boton) {
    boton.addEventListener('click', function () {
      var tabla = boton.dataset.tabla;
      if (!cfg.lote || !tabla || !cfg.apiActiva) return;

      var original = boton.innerHTML;
      boton.disabled = true;
      boton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';

      fetch(cfg.apiActiva, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lote: cfg.lote, tabla: tabla })
      })
        .then(function (respuesta) { return respuesta.json(); })
        .then(function (data) {
          if (data.status === 'ok') {
            window.location.reload();
            return;
          }
          alert('No se pudo cambiar la tabla activa:\n' + (data.msg || 'Error desconocido'));
          boton.disabled = false;
          boton.innerHTML = original;
        })
        .catch(function (error) {
          console.error('Error de red cambiando la tabla activa:', error);
          alert('No se pudo conectar con el servidor.');
          boton.disabled = false;
          boton.innerHTML = original;
        });
    });
  });
})();
