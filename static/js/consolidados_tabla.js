// Resalta la fila (desde la primera columna hasta el cursor) y la columna (desde la primera fila hasta el cursor)
// en las tablas matriciales de Consolidados
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('table.tabla-compacta').forEach(function (tabla) {
        let celdaActual = null;

        function limpiar() {
            tabla.querySelectorAll('.hover-fila').forEach(function (c) { c.classList.remove('hover-fila'); });
            tabla.querySelectorAll('.hover-columna').forEach(function (c) { c.classList.remove('hover-columna'); });
        }

        tabla.addEventListener('mouseover', function (e) {
            const celda = e.target.closest('tbody td');
            if (!celda || !tabla.contains(celda) || celda === celdaActual) return;

            limpiar();
            celdaActual = celda;

            const tr = celda.parentElement;
            const idx = celda.cellIndex;
            Array.from(tr.cells).forEach(function (c, i) {
                if (i <= idx) c.classList.add('hover-fila');
            });

            const tbody = celda.closest('tbody');
            const filas = Array.from(tbody.rows);
            const indiceFila = filas.indexOf(tr);
            for (let i = 0; i <= indiceFila; i++) {
                const c = filas[i].cells[idx];
                if (c) c.classList.add('hover-columna');
            }
        });

        tabla.addEventListener('mouseleave', function () {
            limpiar();
            celdaActual = null;
        });
    });
});
