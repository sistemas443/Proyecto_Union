// Selector de lote propio: submenús por abreviatura (69, 70...), cerrados al abrir.
// Mantiene el <select> original como fuente del valor para que el formulario siga funcionando.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('select[data-lote-picker]').forEach(function (select) {
    crearPicker(select);
  });

  function crearPicker(select) {
    if (select.dataset.lpListo === '1') return;
    select.dataset.lpListo = '1';

    const contenedor = select.closest('.lote-picker') || select.parentElement;
    if (!contenedor) return;
    contenedor.classList.add('lp');

    const opciones = [];
    Array.from(select.options).forEach(function (opt) {
      if (!opt.value) return;
      opciones.push({
        valor: opt.value,
        estado: opt.dataset.estado || 'ACTIVO',
        prefijo: opt.dataset.prefijo || 'Otros',
        fecha: opt.dataset.fecha || '',
        variedad: opt.dataset.variedad || ''
      });
    });
    if (!opciones.length) return;

    let estado = 'ACTIVO';
    let busqueda = '';
    let abierto = false;

    select.classList.add('lp-native');
    select.tabIndex = -1;

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'lp-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.innerHTML = '<span class="lp-valor"></span>' +
      '<span class="lp-dot lp-dot-otro lp-dot-trigger" hidden></span>' +
      '<i class="bx bx-chevron-down lp-chevron" aria-hidden="true"></i>';

    const pop = document.createElement('div');
    pop.className = 'lp-popover';
    pop.hidden = true;
    pop.innerHTML = [
      '<div class="lp-tabs" role="tablist">',
      '<button type="button" class="lp-tab activo" role="tab" aria-selected="true" data-estado="ACTIVO">ACTIVOS <span class="lp-cuenta"></span></button>',
      '<button type="button" class="lp-tab" role="tab" aria-selected="false" data-estado="CONCLUIDO">CONCLUIDOS <span class="lp-cuenta"></span></button>',
      '</div>',
      '<div class="lp-buscar">',
      '<i class="bx bx-search" aria-hidden="true"></i>',
      '<input type="search" placeholder="Buscar lote…" aria-label="Buscar lote">',
      '</div>',
      '<div class="lp-lista" role="listbox" aria-label="Lotes"></div>',
      '<div class="lp-vacio" hidden>Sin lotes que coincidan.</div>'
    ].join('');

    contenedor.appendChild(trigger);
    contenedor.appendChild(pop);

    const valorEl = trigger.querySelector('.lp-valor');
    const dotEl = trigger.querySelector('.lp-dot-trigger');
    const input = pop.querySelector('.lp-buscar input');
    const lista = pop.querySelector('.lp-lista');
    const vacio = pop.querySelector('.lp-vacio');
    const tabs = Array.prototype.slice.call(pop.querySelectorAll('.lp-tab'));

    function formatearFecha(iso) {
      if (!iso) return '';
      const partes = String(iso).slice(0, 10).split('-');
      if (partes.length !== 3) return iso;
      const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
                     'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
      return partes[2] + ' ' + (meses[parseInt(partes[1], 10) - 1] || partes[1]) +
        ' ' + String(partes[0]).slice(2);
    }

    function claseVariedad(variedad) {
      const v = (variedad || '').toUpperCase();
      if (v.indexOf('LOHMANN') !== -1) return 'lp-dot-lohmann';
      if (v.indexOf('HY LINE') !== -1) return 'lp-dot-hyline';
      return 'lp-dot-otro';
    }

    function actualizarValor() {
      const valor = select.value;
      valorEl.textContent = valor ? 'LOTE ' + valor : '-- Seleccione --';
      valorEl.classList.toggle('lp-placeholder', !valor);

      if (dotEl) {
        const opcion = opciones.find(function (o) { return o.valor === valor; });
        dotEl.hidden = !opcion;
        dotEl.className = 'lp-dot lp-dot-trigger ' +
          claseVariedad(opcion ? opcion.variedad : '');
      }
    }

    function contar() {
      const activos = opciones.filter(function (o) { return o.estado === 'ACTIVO'; }).length;
      tabs[0].querySelector('.lp-cuenta').textContent = activos;
      tabs[1].querySelector('.lp-cuenta').textContent = opciones.length - activos;
    }

    function pintar() {
      const termino = busqueda.trim().toUpperCase();
      const items = opciones.filter(function (o) {
        if (o.estado !== estado) return false;
        return !termino || o.valor.toUpperCase().indexOf(termino) !== -1;
      });

      const grupos = [];
      items.forEach(function (o) {
        let grupo = grupos.find(function (g) { return g.prefijo === o.prefijo; });
        if (!grupo) {
          grupo = { prefijo: o.prefijo, items: [] };
          grupos.push(grupo);
        }
        grupo.items.push(o);
      });

      const expandido = Boolean(termino);
      let html = '';

      grupos.forEach(function (grupo) {
        html += '<div class="lp-grupo">';
        html += '<button type="button" class="lp-grupo-toggle" aria-expanded="' +
          (expandido ? 'true' : 'false') + '">' +
          '<span class="lp-grupo-nombre">' + grupo.prefijo + '</span>' +
          '<span class="lp-grupo-cuenta">' + grupo.items.length + '</span>' +
          '<i class="bx bx-chevron-down lp-grupo-flecha" aria-hidden="true"></i>' +
          '</button>';
        html += '<div class="lp-grupo-body' + (expandido ? '' : ' oculto') + '">';
        grupo.items.forEach(function (o) {
          const seleccionada = o.valor === select.value;
          html += '<button type="button" class="lp-opcion' +
            (seleccionada ? ' seleccionada' : '') + '" role="option" aria-selected="' +
            (seleccionada ? 'true' : 'false') + '" data-valor="' + o.valor + '">' +
            '<span class="lp-opcion-nombre">' + o.valor + '</span>' +
            '<span class="lp-opcion-fecha">' + formatearFecha(o.fecha) + '</span>' +
            '<span class="lp-dot ' + claseVariedad(o.variedad) + '" title="' +
            (o.variedad || 'Sin variedad') + '"></span>' +
            '<i class="bx bx-check lp-check" aria-hidden="true"></i>' +
            '</button>';
        });
        html += '</div></div>';
      });

      lista.innerHTML = html;
      vacio.hidden = items.length > 0;

      lista.querySelectorAll('.lp-grupo-toggle').forEach(function (boton) {
        boton.addEventListener('click', function () {
          const estaba = boton.getAttribute('aria-expanded') === 'true';
          boton.setAttribute('aria-expanded', estaba ? 'false' : 'true');
          const cuerpo = boton.nextElementSibling;
          if (cuerpo) cuerpo.classList.toggle('oculto', estaba);
        });
      });

      lista.querySelectorAll('.lp-opcion').forEach(function (opcion) {
        opcion.addEventListener('click', function () {
          select.value = opcion.dataset.valor;
          select.dispatchEvent(new Event('change', { bubbles: true }));
          actualizarValor();
          cerrar(true);
        });
      });
    }

    function posicionar() {
      const r = trigger.getBoundingClientRect();
      const ancho = Math.max(r.width, 300);
      let left = Math.min(r.left, window.innerWidth - ancho - 12);
      left = Math.max(12, left);
      const top = Math.min(r.bottom + 6, window.innerHeight - 160);
      pop.style.width = ancho + 'px';
      pop.style.left = left + 'px';
      pop.style.top = top + 'px';
      pop.style.maxHeight = Math.max(240, window.innerHeight - top - 12) + 'px';
    }

    function abrir() {
      if (abierto) return;
      abierto = true;
      pop.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      input.value = '';
      busqueda = '';
      contar();
      pintar();
      posicionar();
      setTimeout(function () { input.focus(); }, 30);
    }

    function cerrar(devolverFoco) {
      if (!abierto) return;
      abierto = false;
      pop.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      if (devolverFoco) trigger.focus();
    }

    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      if (abierto) cerrar();
      else abrir();
    });

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        estado = tab.dataset.estado;
        tabs.forEach(function (t) {
          const activo = t === tab;
          t.classList.toggle('activo', activo);
          t.setAttribute('aria-selected', activo ? 'true' : 'false');
        });
        pintar();
      });
    });

    input.addEventListener('input', function () {
      busqueda = input.value;
      pintar();
    });

    document.addEventListener('click', function (e) {
      if (abierto && !contenedor.contains(e.target)) cerrar();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && abierto) cerrar(true);
    });

    window.addEventListener('resize', function () { if (abierto) posicionar(); });
    window.addEventListener('scroll', function () { if (abierto) posicionar(); }, true);

    actualizarValor();
    contar();
    pintar();
  }
});
