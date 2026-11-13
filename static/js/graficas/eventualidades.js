/*
 * Eventualidades por lote.
 *
 * Uso:
 *   Eventualidades.iniciar({
 *       lote: '70-12',
 *       ambito: 'PRODUCCION',        // PRODUCCION | LEVANTE | PRIMERA_SEMANA
 *       plotId: 'graficoPlotly',
 *       modo: 'semana',              // 'semana' usa el eje X; 'dia' usa el índice del punto
 *       alCambiar: function () {}    // opcional, para refrescar el gráfico
 *   });
 */
(function () {
    'use strict';

    var URL_LISTAR = '/eventualidades/api/listar';
    var URL_CREAR = '/eventualidades/api/crear';
    var URL_TIPOS = '/eventualidades/api/tipos';

    var config = null;
    var tipos = [];
    var eventos = [];
    var semanaActual = null;
    var modal = null;
    var contenedor = null;
    var editandoId = null;

    var ETIQUETA_AMBITO = {
        PRODUCCION: 'Semana',
        LEVANTE: 'Semana de levante',
        PRIMERA_SEMANA: 'Día'
    };

    function esc(texto) {
        return String(texto == null ? '' : texto)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function inyectarEstilos() {
        if (document.getElementById('estilos-eventualidades')) return;
        var estilo = document.createElement('style');
        estilo.id = 'estilos-eventualidades';
        estilo.textContent = [
            '.ev-lista { display:flex; flex-direction:column; gap:.4rem; max-height:240px; overflow-y:auto; }',
            '.ev-item { display:flex; gap:.55rem; align-items:flex-start; padding:.45rem .55rem;',
            '  border:1px solid var(--border,#dee2e6); border-radius:.4rem; background:#f8f9fa; }',
            '.ev-punto { width:9px; height:9px; border-radius:50%; margin-top:.35rem; flex:0 0 9px; }',
            '.ev-cuerpo { flex:1 1 auto; min-width:0; }',
            '.ev-titulo { font-weight:600; font-size:.82rem; color:#212529; }',
            '.ev-meta { font-size:.7rem; color:#6c757d; }',
            '.ev-detalle { font-size:.76rem; color:#495057; margin-top:.15rem; white-space:pre-wrap; }',
            '.ev-borrar { border:0; background:transparent; color:#dc3545; padding:0 .15rem; line-height:1; }',
            '.ev-editar { border:0; background:transparent; color:#2c3e50; padding:0 .15rem; line-height:1; margin-right:.25rem; }',
            '.ev-item.activo { border-color:#2c3e50; box-shadow:0 0 0 2px rgba(44,62,80,.12); }',
            '.ev-vacio { font-size:.8rem; color:#6c757d; font-style:italic; padding:.3rem 0; }',
            '.ev-ayuda { font-size:.72rem; color:#6c757d; margin-top:.35rem; }'
        ].join('\n');
        document.head.appendChild(estilo);
    }

    function construirModal() {
        contenedor = document.createElement('div');
        contenedor.innerHTML = [
            '<div class="modal fade" id="modalEventualidades" tabindex="-1" aria-hidden="true">',
            ' <div class="modal-dialog modal-dialog-centered modal-lg">',
            '  <div class="modal-content">',
            '   <div class="modal-header">',
            '    <h5 class="modal-title">Eventualidades · <span id="evSemanaTitulo"></span></h5>',
            '    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>',
            '   </div>',
            '   <div class="modal-body">',
            '    <div id="evListaSemana" class="ev-lista"></div>',
            '    <hr class="my-3">',
            '    <form id="evForm" autocomplete="off">',
            '     <div class="row g-2">',
            '      <div class="col-md-5">',
            '       <label class="form-label-design" for="evTipo">Tipo</label>',
            '       <div class="d-flex gap-1">',
            '        <select id="evTipo" class="form-select form-select-sm"></select>',
            '        <button type="button" class="btn btn-outline-secondary btn-sm" id="evNuevoTipo" title="Crear tipo">+</button>',
            '       </div>',
            '      </div>',
            '      <div class="col-md-7">',
            '       <label class="form-label-design" for="evTitulo">Título</label>',
            '       <input id="evTitulo" class="form-control form-control-sm" maxlength="200" required>',
            '      </div>',
            '      <div class="col-12">',
            '       <label class="form-label-design" for="evDetalle">Detalle</label>',
            '       <textarea id="evDetalle" class="form-control form-control-sm" rows="2" maxlength="1000"></textarea>',
            '      </div>',
            '      <div class="col-md-6">',
            '       <label class="form-label-design" for="evImpacto">Impacto (opcional)</label>',
            '       <input id="evImpacto" class="form-control form-control-sm" maxlength="200" placeholder="Ej: caída de 8 %">',
            '      </div>',
            '     </div>',
            '     <div class="d-flex justify-content-end gap-2 mt-3">',
            '      <button type="button" class="btn btn-outline-secondary btn-sm d-none" id="evCancelar">Cancelar edición</button>',
            '      <button type="submit" class="btn btn-primary btn-sm" id="evGuardar"><i class="fas fa-save me-1"></i> Guardar</button>',
            '     </div>',
            '    </form>',
            '    <div id="evNuevoTipoBox" class="d-none mt-2">',
            '     <div class="input-group input-group-sm">',
            '      <input id="evNuevoTipoNombre" class="form-control" maxlength="60" placeholder="Nombre del nuevo tipo">',
            '      <button class="btn btn-outline-primary" type="button" id="evCrearTipo">Crear</button>',
            '     </div>',
            '    </div>',
            '    <div class="mt-3">',
            '     <button class="btn btn-link btn-sm p-0" type="button" data-bs-toggle="collapse" data-bs-target="#evTodas">',
            '      Ver todas las del lote',
            '     </button>',
            '     <div class="collapse" id="evTodas"><div id="evListaTodas" class="ev-lista mt-2"></div></div>',
            '    </div>',
            '   </div>',
            '  </div>',
            ' </div>',
            '</div>'
        ].join('\n');
        document.body.appendChild(contenedor);

        document.getElementById('evForm').addEventListener('submit', guardar);
        document.getElementById('evCancelar').addEventListener('click', resetForm);
        document.getElementById('modalEventualidades').addEventListener('hidden.bs.modal', restaurarPantallaCompleta);
        document.addEventListener('fullscreenchange', function () {
            if (!document.fullscreenElement) restaurarPantallaCompleta();
        });
        document.getElementById('evNuevoTipo').addEventListener('click', function () {
            document.getElementById('evNuevoTipoBox').classList.toggle('d-none');
            document.getElementById('evNuevoTipoNombre').focus();
        });
        document.getElementById('evCrearTipo').addEventListener('click', crearTipo);

        modal = new bootstrap.Modal(document.getElementById('modalEventualidades'));
    }

    function pintarTipos() {
        var select = document.getElementById('evTipo');
        select.innerHTML = '<option value="">Sin tipo</option>' + tipos.map(function (t) {
            return '<option value="' + t.id + '">' + esc(t.nombre) + '</option>';
        }).join('');
    }

    function formatearFecha(valor) {
        if (!valor) return '';
        var partes = String(valor).slice(0, 10).split('-');
        if (partes.length !== 3) return String(valor);
        return partes[2] + '/' + partes[1] + '/' + partes[0];
    }

    function itemHtml(evento) {
        var color = evento.tipo_color || '#adb5bd';
        var meta = [evento.tipo, 'Semana ' + evento.semana];
        if (evento.fecha) meta.push('Registrada el ' + formatearFecha(evento.fecha));
        if (evento.creado_por_nombre) meta.push(evento.creado_por_nombre);
        return [
            '<div class="ev-item" data-id="' + evento.id + '">',
            ' <span class="ev-punto" style="background:' + esc(color) + '"></span>',
            ' <div class="ev-cuerpo">',
            '  <div class="ev-titulo">' + esc(evento.titulo) + '</div>',
            '  <div class="ev-meta">' + esc(meta.filter(Boolean).join(' · ')) + '</div>',
            evento.detalle ? '  <div class="ev-detalle">' + esc(evento.detalle) + '</div>' : '',
            evento.impacto ? '  <div class="ev-meta">Impacto: ' + esc(evento.impacto) + '</div>' : '',
            ' </div>',
            ' <div class="d-flex align-items-start">',
            '  <button type="button" class="ev-editar" data-editar="' + evento.id + '" title="Editar">',
            '   <i class="fas fa-pen"></i>',
            '  </button>',
            '  <button type="button" class="ev-borrar" data-borrar="' + evento.id + '" title="Eliminar">',
            '   <i class="fas fa-trash-alt"></i>',
            '  </button>',
            ' </div>',
            '</div>'
        ].join('\n');
    }

    function pintarListas() {
        var deSemana = eventos.filter(function (e) { return Number(e.semana) === Number(semanaActual); });
        var listaSemana = document.getElementById('evListaSemana');
        var listaTodas = document.getElementById('evListaTodas');

        listaSemana.innerHTML = deSemana.length
            ? deSemana.map(itemHtml).join('')
            : '<div class="ev-vacio">Todavía no hay eventualidades para esta ' +
              (config.ambito === 'PRIMERA_SEMANA' ? 'día' : 'semana') + '.</div>';

        listaTodas.innerHTML = eventos.length
            ? eventos.map(itemHtml).join('')
            : '<div class="ev-vacio">El lote no tiene eventualidades registradas.</div>';

        contenedor.querySelectorAll('[data-borrar]').forEach(function (boton) {
            boton.addEventListener('click', function () { borrar(boton.getAttribute('data-borrar')); });
        });
        contenedor.querySelectorAll('[data-editar]').forEach(function (boton) {
            boton.addEventListener('click', function () { editar(boton.getAttribute('data-editar')); });
        });
        contenedor.querySelectorAll('#evListaTodas .ev-item').forEach(function (item) {
            item.addEventListener('click', function (evento) {
                if (evento.target.closest('[data-borrar]')) return;
                var id = Number(item.getAttribute('data-id'));
                var encontrado = eventos.find(function (e) { return Number(e.id) === id; });
                if (encontrado) abrir(Number(encontrado.semana));
            });
        });
    }

    function prepararPantallaCompleta() {
        var pantalla = document.fullscreenElement;
        if (!pantalla) return;

        if (!document.getElementById('evBackdropFS')) {
            var fondo = document.createElement('div');
            fondo.id = 'evBackdropFS';
            fondo.className = 'modal-backdrop fade show';
            pantalla.appendChild(fondo);
        }
        if (contenedor.parentNode !== pantalla) {
            pantalla.appendChild(contenedor);
        }
    }

    function restaurarPantallaCompleta() {
        var fondo = document.getElementById('evBackdropFS');
        if (fondo) fondo.remove();
        if (contenedor && contenedor.parentNode !== document.body) {
            document.body.appendChild(contenedor);
        }
    }

    function resetForm() {
        editandoId = null;
        document.getElementById('evTitulo').value = '';
        document.getElementById('evDetalle').value = '';
        document.getElementById('evImpacto').value = '';
        document.getElementById('evTipo').value = '';
        document.getElementById('evNuevoTipoBox').classList.add('d-none');
        document.getElementById('evGuardar').innerHTML = '<i class="fas fa-save me-1"></i> Guardar';
        document.getElementById('evCancelar').classList.add('d-none');
        contenedor.querySelectorAll('.ev-item.activo').forEach(function (el) {
            el.classList.remove('activo');
        });
    }

    function editar(id) {
        var evento = eventos.find(function (e) { return Number(e.id) === Number(id); });
        if (!evento) return;

        editandoId = evento.id;
        document.getElementById('evTipo').value = evento.tipo_id ? String(evento.tipo_id) : '';
        document.getElementById('evTitulo').value = evento.titulo || '';
        document.getElementById('evDetalle').value = evento.detalle || '';
        document.getElementById('evImpacto').value = evento.impacto || '';
        document.getElementById('evGuardar').innerHTML = '<i class="fas fa-pen me-1"></i> Actualizar';
        document.getElementById('evCancelar').classList.remove('d-none');
        document.getElementById('evTitulo').focus();
    }

    function abrir(semana) {
        semanaActual = semana;
        var etiqueta = ETIQUETA_AMBITO[config.ambito] || 'Semana';
        document.getElementById('evSemanaTitulo').textContent = etiqueta + ' ' + semana;
        resetForm();
        pintarListas();
        prepararPantallaCompleta();
        modal.show();
        setTimeout(function () { document.getElementById('evTitulo').focus(); }, 350);
    }

    function recargar() {
        return fetch(URL_LISTAR + '?lote=' + encodeURIComponent(config.lote) +
                     '&ambito=' + encodeURIComponent(config.ambito))
            .then(function (r) { return r.json(); })
            .then(function (datos) {
                if (datos.status === 'ok') {
                    eventos = datos.eventualidades || [];
                }
            });
    }

    function guardar(evento) {
        evento.preventDefault();
        var cuerpo = {
            tipo_id: document.getElementById('evTipo').value || null,
            titulo: document.getElementById('evTitulo').value,
            detalle: document.getElementById('evDetalle').value,
            impacto: document.getElementById('evImpacto').value
        };

        var url = URL_CREAR;
        if (editandoId) {
            url = '/eventualidades/api/' + editandoId + '/editar';
        } else {
            cuerpo.lote = config.lote;
            cuerpo.ambito = config.ambito;
            cuerpo.semana = semanaActual;
        }

        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo)
        })
            .then(function (r) { return r.json(); })
            .then(function (datos) {
                if (datos.status !== 'ok') {
                    alert(datos.mensaje || 'No se pudo guardar.');
                    return;
                }
                return recargar().then(function () {
                    resetForm();
                    pintarListas();
                    aplicarAlGrafico();
                    if (typeof config.alCambiar === 'function') config.alCambiar();
                });
            })
            .catch(function () { alert('No se pudo guardar la eventualidad.'); });
    }

    function borrar(id) {
        if (!confirm('¿Eliminar esta eventualidad?')) return;
        fetch('/eventualidades/api/' + id + '/eliminar', { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (datos) {
                if (datos.status !== 'ok') {
                    alert(datos.mensaje || 'No se pudo eliminar.');
                    return;
                }
                return recargar().then(function () {
                    pintarListas();
                    aplicarAlGrafico();
                    if (typeof config.alCambiar === 'function') config.alCambiar();
                });
            })
            .catch(function () { alert('No se pudo eliminar la eventualidad.'); });
    }

    function crearTipo() {
        var nombre = document.getElementById('evNuevoTipoNombre').value.trim();
        if (!nombre) return;

        fetch(URL_TIPOS, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: nombre })
        })
            .then(function (r) { return r.json(); })
            .then(function (datos) {
                if (datos.status !== 'ok') {
                    alert(datos.mensaje || 'No se pudo crear el tipo.');
                    return;
                }
                return fetch(URL_TIPOS).then(function (r) { return r.json(); }).then(function (res) {
                    tipos = res.tipos || [];
                    pintarTipos();
                    document.getElementById('evTipo').value = datos.tipo.id;
                    document.getElementById('evNuevoTipoNombre').value = '';
                    document.getElementById('evNuevoTipoBox').classList.add('d-none');
                });
            })
            .catch(function () { alert('No se pudo crear el tipo.'); });
    }

    function htmlGrupo(semana, grupo) {
        var etiqueta = config.ambito === 'PRIMERA_SEMANA' ? 'Día ' + semana : 'Semana ' + semana;
        var lineas = grupo.map(function (evento) {
            var tipo = evento.tipo ? ' (' + esc(evento.tipo) + ')' : '';
            var detalle = evento.detalle
                ? '<br><span style="font-size:11px;color:#6c757d">' + esc(evento.detalle) + '</span>'
                : '';
            return '&#9679; <b>' + esc(evento.titulo) + '</b>' + tipo + detalle;
        });
        return '<b>' + etiqueta + '</b><br>' + lineas.join('<br>');
    }

    function indiceDeSemana(semana, x) {
        if (config.modo === 'dia') return Number(semana);
        var objetivo = Number(semana);
        for (var i = 0; i < x.length; i++) {
            var valor = parseInt(String(x[i]).replace(/[^0-9-]/g, ''), 10);
            if (valor === objetivo) return i;
        }
        return -1;
    }

    function agregarTraza(gd) {
        var base = gd.data[0];
        if (!base || !base.x) return;

        var x = base.x;
        var y = base.y || [];
        var maxY = 0;
        y.forEach(function (valor) {
            var n = Number(valor);
            if (isFinite(n) && n > maxY) maxY = n;
        });

        var porSemana = {};
        eventos.forEach(function (evento) {
            var clave = Number(evento.semana);
            if (!porSemana[clave]) porSemana[clave] = [];
            porSemana[clave].push(evento);
        });

        var xs = [];
        var ys = [];
        var conteos = [];
        var textos = [];

        Object.keys(porSemana).sort(function (a, b) { return a - b; }).forEach(function (clave) {
            var indice = indiceDeSemana(clave, x);
            if (indice < 0 || indice >= x.length) return;

            var valor = Number(y[indice]);
            if (!isFinite(valor)) valor = maxY;

            var grupo = porSemana[clave];
            xs.push(x[indice]);
            ys.push(valor);
            conteos.push(grupo.length > 1 ? String(grupo.length) : '');
            textos.push(htmlGrupo(clave, grupo));
        });

        if (!xs.length) return;

        Plotly.addTraces(gd, [{
            x: xs,
            y: ys,
            type: 'scatter',
            mode: 'markers+text',
            name: 'Eventualidades',
            showlegend: false,
            marker: {
                symbol: 'diamond',
                size: 12,
                color: '#dc3545',
                line: { color: '#ffffff', width: 1.5 }
            },
            text: conteos,
            textposition: 'top center',
            textfont: { size: 9, color: '#dc3545' },
            customdata: textos,
            hovertemplate: '%{customdata}<extra></extra>',
            hoverlabel: { align: 'left', bgcolor: '#ffffff', bordercolor: '#dc3545' },
            yaxis: base.yaxis || 'y'
        }]);
    }

    function aplicarAlGrafico() {
        var gd = document.getElementById(config.plotId);
        if (!gd || !gd.data || !gd.data.length) return;

        var indices = [];
        gd.data.forEach(function (traza, i) {
            if (traza.name === 'Eventualidades') indices.push(i);
        });

        if (indices.length) {
            Plotly.deleteTraces(gd, indices).then(function () { agregarTraza(gd); });
        } else {
            agregarTraza(gd);
        }
    }

    function conectarGrafico() {
        var gd = document.getElementById(config.plotId);
        if (!gd || typeof gd.on !== 'function') return;

        gd.on('plotly_click', function (data) {
            if (!data || !data.points || !data.points.length) return;
            var punto = data.points[0];
            var semana = null;

            if (config.modo === 'dia') {
                semana = punto.pointNumber;
            } else {
                semana = parseInt(String(punto.x).replace(/[^0-9-]/g, ''), 10);
            }
            if (!isFinite(semana)) return;
            abrir(semana);
        });

        var ayuda = document.createElement('p');
        ayuda.className = 'ev-ayuda';
        ayuda.innerHTML = '<i class="fas fa-mouse-pointer me-1"></i>Haz clic en un punto del gráfico para anotar una eventualidad.';
        if (gd.parentNode) gd.parentNode.insertBefore(ayuda, gd.nextSibling);
    }

    window.Eventualidades = {
        iniciar: function (opciones) {
            if (!opciones || !opciones.lote || opciones.lote === 'VACIO') return;
            config = opciones;
            inyectarEstilos();
            construirModal();

            fetch(URL_TIPOS)
                .then(function (r) { return r.json(); })
                .then(function (datos) { tipos = datos.tipos || []; pintarTipos(); })
                .then(recargar)
                .then(conectarGrafico)
                .then(aplicarAlGrafico)
                .catch(function (e) { console.error('[eventualidades]', e); });
        }
    };
})();
