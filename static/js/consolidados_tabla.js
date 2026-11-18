// Resalta la fila (desde la primera columna hasta el cursor) y la columna (desde la primera fila hasta el cursor)
// en las tablas matriciales de Consolidados
document.addEventListener('DOMContentLoaded', function () {
    // Columnas que se quedan fijas al hacer scroll horizontal
    const CLASES_FIJAS = ['col-semana', 'col-prom', 'col-tabla', 'col-total',
                          'col-nro', 'col-fija', 'col-dia'];

    function congelarColumnas(tabla) {
        const fila = tabla.querySelector('tbody tr');
        if (!fila || !fila.cells.length) return;

        // Se toman las primeras columnas mientras tengan una clase de columna fija
        const fijas = [];
        for (let i = 0; i < fila.cells.length; i++) {
            const celda = fila.cells[i];
            const esFija = CLASES_FIJAS.some(function (clase) {
                return celda.classList.contains(clase);
            });
            if (!esFija) break;
            fijas.push(celda);
        }
        if (!fijas.length) return;

        let izquierda = 0;
        fijas.forEach(function (celda, indice) {
            const ancho = celda.getBoundingClientRect().width;
            tabla.querySelectorAll('tr').forEach(function (tr) {
                const c = tr.cells[indice];
                if (!c) return;
                c.style.left = izquierda + 'px';
                c.classList.add('col-congelada');
            });
            izquierda += ancho;
        });

        // La última columna fija dibuja la sombra del borde
        const ultima = fijas.length - 1;
        tabla.querySelectorAll('tr').forEach(function (tr) {
            const c = tr.cells[ultima];
            if (c) c.classList.add('col-congelada-fin');
        });
    }

    document.querySelectorAll('table.tabla-compacta, table.serie-tabla').forEach(function (tabla) {
        congelarColumnas(tabla);

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

        // Marca fija al hacer clic: la fila y la columna quedan resaltadas
        // aunque se haga scroll o se mueva el mouse.
        function limpiarMarca() {
            tabla.querySelectorAll('.marca-fila, .marca-columna, .marca-celda').forEach(function (c) {
                c.classList.remove('marca-fila', 'marca-columna', 'marca-celda');
            });
        }

        function marcarCelda(celda) {
            limpiarMarca();
            const tr = celda.parentElement;
            const idx = celda.cellIndex;
            Array.from(tr.cells).forEach(function (c, i) {
                if (i <= idx) c.classList.add('marca-fila');
            });
            const tbody = celda.closest('tbody');
            const filas = Array.from(tbody.rows);
            const indiceFila = filas.indexOf(tr);
            for (let i = 0; i <= indiceFila; i++) {
                const c = filas[i].cells[idx];
                if (c) c.classList.add('marca-columna');
            }
            celda.classList.add('marca-celda');
        }

        tabla.addEventListener('click', function (e) {
            const celda = e.target.closest('tbody td');
            if (!celda || !tabla.contains(celda)) return;
            marcarCelda(celda);
        });
    });

    // Encabezados fijos al hacer scroll vertical: cada fila del thead se pega
    // debajo de la anterior usando su altura real.
    function ajustarEncabezados() {
        document.querySelectorAll('table.tabla-compacta, table.serie-tabla').forEach(function (tabla) {
            let acumulado = 0;
            tabla.querySelectorAll('thead tr').forEach(function (tr) {
                tr.querySelectorAll('th').forEach(function (th) {
                    th.style.top = acumulado + 'px';
                });
                acumulado += tr.offsetHeight;
            });
        });
    }

    ajustarEncabezados();
    window.addEventListener('load', ajustarEncabezados);

    let temporizadorEncabezados;
    window.addEventListener('resize', function () {
        clearTimeout(temporizadorEncabezados);
        temporizadorEncabezados = setTimeout(ajustarEncabezados, 150);
    });
});
