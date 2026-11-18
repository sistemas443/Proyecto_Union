// Panel de lotes para las vistas de Consolidados.
// Filtra por variedad (TODAS / HY LINE / LOHMANN), agrupa en ACTIVOS y CONCLUIDOS
// y sincroniza los checkboxes de la tabla que calculan TOTALES / PROM.
document.addEventListener('DOMContentLoaded', function () {
  const raiz = document.getElementById('clLotes');
  const metaEl = document.getElementById('clLotesMeta');
  if (!raiz || !metaEl) return;

  let LOTES = [];
  try {
    LOTES = JSON.parse(metaEl.textContent) || [];
  } catch (e) {
    return;
  }
  if (!LOTES.length) return;

  const panel = document.getElementById('clPanel');
  const botonVer = document.getElementById('clVer');
  const lista = document.getElementById('clLista');
  const buscar = document.getElementById('clBuscar');
  const contador = document.getElementById('clContador');
  const contadorPanel = document.getElementById('clContadorPanel');
  const cuentaActivo = document.getElementById('clCuentaActivo');
  const cuentaConcluido = document.getElementById('clCuentaConcluido');

  let categoria = 'ACTIVO';
  let filtro = 'TODAS';

  const checksDe = function (nombre) {
    return Array.prototype.slice.call(
      document.querySelectorAll('.chk-incluir[data-lote="' + nombre + '"]')
    );
  };

  const estaIncluido = function (nombre) {
    const chks = checksDe(nombre);
    return chks.length ? chks[0].checked : false;
  };

  const incluir = function (nombre, valor) {
    checksDe(nombre).forEach(function (chk) {
      if (chk.checked === valor) return;
      chk.checked = valor;
      chk.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const panelChk = lista.querySelector('.cl-chk[value="' + nombre + '"]');
    if (panelChk) panelChk.checked = valor;
  };

  // Todas las celdas (encabezado y cuerpo) de la columna de un lote, en todas
  // las tablas de la página. Así también se ocultan las filas de FECHA/AVES.
  const celdasDeLote = function (nombre) {
    const celdas = [];
    document.querySelectorAll('table.tabla-compacta').forEach(function (tabla) {
      const chk = tabla.querySelector('thead .chk-incluir[data-lote="' + nombre + '"]');
      if (!chk) return;
      const th = chk.closest('th');
      const indice = Array.prototype.indexOf.call(th.parentElement.children, th);
      if (indice < 0) return;
      tabla.querySelectorAll('tr').forEach(function (fila) {
        const celda = fila.children[indice];
        if (celda) celdas.push(celda);
      });
    });
    return celdas;
  };

  const visibilidad = function () {
    LOTES.forEach(function (l) {
      const variedad = (l.variedad || '').toUpperCase();
      const coincide = filtro === 'TODAS' || variedad.indexOf(filtro) !== -1;
      celdasDeLote(l.nombre).forEach(function (celda) {
        celda.classList.toggle('cl-oculto', !coincide);
      });
    });
  };

  const actualizarContadores = function () {
    const total = LOTES.filter(function (l) { return estaIncluido(l.nombre); }).length;
    const etiqueta = total + ' de ' + LOTES.length;
    contador.textContent = etiqueta;
    contadorPanel.textContent = etiqueta;
  };

  const marcarActivo = function (boton) {
    document.querySelectorAll('.cl-filtro').forEach(function (b) {
      b.classList.toggle('activo', b === boton);
    });
  };

  const formatearFecha = function (iso) {
    if (!iso) return '';
    const partes = String(iso).slice(0, 10).split('-');
    if (partes.length !== 3) return iso;
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
                   'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const mes = meses[parseInt(partes[1], 10) - 1] || partes[1];
    return partes[2] + ' ' + mes + ' ' + String(partes[0]).slice(2);
  };

  const claseVariedad = function (variedad) {
    const v = (variedad || '').toUpperCase();
    if (v.indexOf('LOHMANN') !== -1) return 'cl-dot-lohmann';
    if (v.indexOf('HY LINE') !== -1) return 'cl-dot-hyline';
    return 'cl-dot-otro';
  };

  const grupoDe = function (nombre) {
    const guion = nombre.indexOf('-');
    return guion > 0 ? nombre.slice(0, guion) : 'Otros';
  };

  const pintarLista = function () {
    const termino = (buscar.value || '').toUpperCase();
    const items = LOTES.filter(function (l) {
      if ((l.estado || 'ACTIVO') !== categoria) return false;
      return !termino || l.nombre.toUpperCase().indexOf(termino) !== -1;
    }).sort(function (a, b) {
      const fa = String(a.fecha || '');
      const fb = String(b.fecha || '');
      return fb.localeCompare(fa) || String(a.nombre).localeCompare(String(b.nombre));
    });

    if (!items.length) {
      lista.innerHTML = '<div class="cl-vacio">Sin lotes que coincidan.</div>';
      return;
    }

    // Subgrupos por abreviatura (69, 70, 72...) en el orden de los datos.
    const grupos = [];
    items.forEach(function (l) {
      const clave = grupoDe(l.nombre);
      let grupo = grupos.find(function (g) { return g.nombre === clave; });
      if (!grupo) {
        grupo = { nombre: clave, lotes: [] };
        grupos.push(grupo);
      }
      grupo.lotes.push(l);
    });

    // Cerrados al abrir; con búsqueda activa se muestran abiertos.
    const abierto = Boolean(termino);

    let html = '';
    grupos.forEach(function (grupo) {
      html += '<div class="cl-grupo" data-grupo="' + grupo.nombre + '">';
      html += '<div class="cl-grupo-head">' +
        '<button type="button" class="cl-grupo-toggle" aria-expanded="' + (abierto ? 'true' : 'false') + '">' +
        '<span class="cl-grupo-nombre">' + grupo.nombre + '</span>' +
        '<span class="cl-grupo-cuenta">' + grupo.lotes.length + '</span>' +
        '<i class="bx bx-chevron-down cl-grupo-flecha" aria-hidden="true"></i>' +
        '</button></div>';
      html += '<div class="cl-grupo-body' + (abierto ? '' : ' colapsado') + '">';
      grupo.lotes.forEach(function (l) {
        html += '<label class="cl-item">' +
          '<input type="checkbox" class="cl-chk" value="' + l.nombre + '"' +
          (estaIncluido(l.nombre) ? ' checked' : '') + '>' +
          '<span class="cl-item-nombre">' + l.nombre + '</span>' +
          '<span class="cl-item-fecha">' + formatearFecha(l.fecha) + '</span>' +
          '<span class="cl-dot ' + claseVariedad(l.variedad) + '" title="' +
          (l.variedad || 'Sin variedad') + '"></span>' +
          '</label>';
      });
      html += '</div></div>';
    });

    lista.innerHTML = html;

    lista.querySelectorAll('.cl-chk').forEach(function (chk) {
      chk.addEventListener('change', function () {
        incluir(chk.value, chk.checked);
        actualizarContadores();
      });
    });

    lista.querySelectorAll('.cl-grupo-toggle').forEach(function (boton) {
      boton.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const expandido = boton.getAttribute('aria-expanded') === 'true';
        boton.setAttribute('aria-expanded', expandido ? 'false' : 'true');
        const cuerpo = boton.closest('.cl-grupo-head').nextElementSibling;
        if (cuerpo) cuerpo.classList.toggle('colapsado', expandido);
      });
    });
  };

  const actualizarCuentas = function () {
    const activos = LOTES.filter(function (l) { return (l.estado || 'ACTIVO') === 'ACTIVO'; }).length;
    cuentaActivo.textContent = activos;
    cuentaConcluido.textContent = LOTES.length - activos;
  };

  const marcarTodos = function (valor) {
    LOTES.forEach(function (l) { incluir(l.nombre, valor); });
    filtro = 'TODAS';
    visibilidad();
    marcarActivo(valor ? document.querySelector('.cl-filtro[data-variedad="TODAS"]') : null);
    actualizarContadores();
    pintarLista();
  };

  const filtrarVariedad = function (termino, boton) {
    filtro = termino;
    LOTES.forEach(function (l) {
      const coincide = (l.variedad || '').toUpperCase().indexOf(termino) !== -1;
      incluir(l.nombre, coincide);
    });
    visibilidad();
    marcarActivo(boton);
    actualizarContadores();
    pintarLista();
  };

  // Barra de filtros.
  document.querySelectorAll('.cl-filtro').forEach(function (boton) {
    boton.addEventListener('click', function (e) {
      e.stopPropagation();
      const variedad = boton.dataset.variedad;
      if (variedad === 'TODAS') {
        marcarTodos(true);
      } else {
        filtrarVariedad(variedad, boton);
      }
    });
  });

  document.getElementById('clNingunoBar').addEventListener('click', function (e) {
    e.stopPropagation();
    marcarTodos(false);
  });

  document.getElementById('clTodosPanel').addEventListener('click', function (e) {
    e.stopPropagation();
    marcarTodos(true);
  });

  document.getElementById('clNingunoPanel').addEventListener('click', function (e) {
    e.stopPropagation();
    marcarTodos(false);
  });

  // Pestañas del panel.
  document.querySelectorAll('.cl-tab').forEach(function (boton) {
    boton.addEventListener('click', function (e) {
      e.stopPropagation();
      categoria = boton.dataset.categoria;
      document.querySelectorAll('.cl-tab').forEach(function (b) {
        b.classList.toggle('activo', b === boton);
      });
      pintarLista();
    });
  });

  buscar.addEventListener('input', pintarLista);

  const cerrarPanel = function () {
    panel.classList.remove('abierto');
    botonVer.classList.remove('abierto');
    botonVer.setAttribute('aria-expanded', 'false');
  };

  botonVer.addEventListener('click', function (e) {
    e.stopPropagation();
    const abierto = panel.classList.toggle('abierto');
    botonVer.classList.toggle('abierto', abierto);
    botonVer.setAttribute('aria-expanded', abierto ? 'true' : 'false');
    if (abierto) {
      buscar.focus();
      buscar.select();
    }
  });

  document.getElementById('clListo').addEventListener('click', cerrarPanel);

  document.addEventListener('click', function (e) {
    if (!raiz.contains(e.target)) {
      cerrarPanel();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('abierto')) {
      cerrarPanel();
      botonVer.focus();
    }
  });

  // Cambios hechos directamente en los checkboxes de la tabla.
  document.addEventListener('change', function (e) {
    if (!e.target.classList || !e.target.classList.contains('chk-incluir')) return;
    const nombre = e.target.dataset.lote;
    const panelChk = lista.querySelector('.cl-chk[value="' + nombre + '"]');
    if (panelChk) panelChk.checked = e.target.checked;
    actualizarContadores();
  });

  actualizarCuentas();
  pintarLista();
  visibilidad();
  actualizarContadores();
});
