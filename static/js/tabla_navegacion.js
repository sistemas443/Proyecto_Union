/* ==========================================================================
   Navegación entre celdas con flechas del teclado
   Aplica a cualquier tabla con campos editables (Producción y Planta de Alimentos).

   - Flechas arriba/abajo: misma columna, fila anterior/siguiente.
   - Flechas izquierda/derecha: celda anterior/siguiente de la fila; solo
     cuando el cursor está al inicio/fin del texto (para no romper la edición).
   - Enter: baja una fila. Shift+Enter: sube.
   ========================================================================== */
(function () {
  'use strict';

  const SELECTOR = 'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])'
    + ':not([type="file"]):not([type="button"]):not([type="submit"]):not([type="reset"])'
    + ':not([type="range"]):not([type="color"]):not([readonly]):not([disabled]), '
    + '[contenteditable="true"]';

  function esEditable(el) {
    if (!el || !el.matches) return false;
    if (el.matches('textarea, select')) return false;
    if (el.matches('input')) {
      const tipo = (el.type || 'text').toLowerCase();
      if (['hidden', 'checkbox', 'radio', 'file', 'button', 'submit', 'reset', 'range', 'color'].includes(tipo)) return false;
      return !el.readOnly && !el.disabled;
    }
    return el.isContentEditable === true;
  }

  function controlesDeFila(fila) {
    if (!fila) return [];
    return Array.from(fila.querySelectorAll(SELECTOR)).filter(esEditable);
  }

  function centroX(el) {
    const r = el.getBoundingClientRect();
    return r.left + r.width / 2;
  }

  function moverHorizontal(control, direccion) {
    const fila = control.closest('tr');
    const lista = controlesDeFila(fila);
    const pos = lista.indexOf(control);
    if (pos === -1) return null;
    return lista[pos + direccion] || null;
  }

  function moverVertical(control, direccion) {
    const tabla = control.closest('table');
    const fila = control.closest('tr');
    if (!tabla || !fila) return null;
    const filas = Array.from(tabla.rows);
    const inicio = filas.indexOf(fila);
    if (inicio === -1) return null;
    const x = centroX(control);

    for (let i = inicio + direccion; i >= 0 && i < filas.length; i += direccion) {
      const candidatos = controlesDeFila(filas[i]);
      if (!candidatos.length) continue;
      let mejor = null;
      candidatos.forEach(function (c) {
        const d = Math.abs(centroX(c) - x);
        if (!mejor || d < mejor.distancia) mejor = { control: c, distancia: d };
      });
      return mejor ? mejor.control : null;
    }
    return null;
  }

  function enBordeHorizontal(control, direccion) {
    if (control.isContentEditable) {
      const seleccion = window.getSelection();
      if (!seleccion || !seleccion.rangeCount || !seleccion.isCollapsed) return false;
      const rango = seleccion.getRangeAt(0);
      if (!control.contains(rango.startContainer)) return false;
      const antes = rango.cloneRange();
      antes.selectNodeContents(control);
      antes.setEnd(rango.startContainer, rango.startOffset);
      const posicion = antes.toString().length;
      const total = control.textContent.length;
      return direccion < 0 ? posicion === 0 : posicion === total;
    }

    if (control.tagName !== 'INPUT') return false;
    const tipo = (control.type || 'text').toLowerCase();
    if (!['text', 'search', 'number', 'tel', 'email', 'url', 'password'].includes(tipo)) return false;
    if (typeof control.selectionStart !== 'number') return false;
    if (control.selectionStart !== control.selectionEnd) return false;
    return direccion < 0
      ? control.selectionStart === 0
      : control.selectionStart === control.value.length;
  }

  function enfocar(destino) {
    if (!destino) return false;
    destino.focus({ preventScroll: true });
    if (destino.scrollIntoView) {
      destino.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
    return true;
  }

  document.addEventListener('keydown', function (e) {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.isComposing) return;
    const control = e.target;
    if (!esEditable(control)) return;
    if (!control.closest('table')) return;

    let destino = null;

    if (e.key === 'ArrowDown' || (e.key === 'Enter' && !e.shiftKey)) {
      destino = moverVertical(control, 1);
    } else if (e.key === 'ArrowUp' || (e.key === 'Enter' && e.shiftKey)) {
      destino = moverVertical(control, -1);
    } else if (e.key === 'ArrowRight') {
      if (enBordeHorizontal(control, 1)) destino = moverHorizontal(control, 1);
    } else if (e.key === 'ArrowLeft') {
      if (enBordeHorizontal(control, -1)) destino = moverHorizontal(control, -1);
    } else {
      return;
    }

    if (destino && enfocar(destino)) {
      e.preventDefault();
    }
  });
})();
