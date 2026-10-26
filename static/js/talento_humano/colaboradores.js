// static/js/talento_humano/colaboradores.js
// Lógica frontend para módulo Talento Humano - Colaboradores
// Siguiendo patrones del proyecto: SweetAlert2, anti-doble-clic, validación tiempo real

let modalColaboradorUI;
let modalBuscarJefeUI;
let tomSelectJefe = null;

// --- Pestañas auxiliares (Capacitaciones / Experiencia / Familiares) ---
let modalCapacitacionUI = null;
let modalExperienciaUI = null;
let modalFamiliarUI = null;
let colaboradorActualId = null;
let cacheCapacitaciones = [];
let cacheExperiencia = [];
let cacheFamiliares = [];

// ============================================================
// INICIALIZACIÓN
// ============================================================
document.addEventListener("DOMContentLoaded", function () {

    // Instanciar modales Bootstrap
    const modalEl = document.getElementById('modalColaborador');
    const modalJefeEl = document.getElementById('modalBuscarJefe');
    if (modalEl) modalColaboradorUI = new bootstrap.Modal(modalEl);
    if (modalJefeEl) modalBuscarJefeUI = new bootstrap.Modal(modalJefeEl);

    // Inicializar TomSelect para jefe inmediato (en modal buscar)
    inicializarTomSelectJefe();

    // BUSCADOR TABLA PRINCIPAL (tiempo real)
    const buscador = document.getElementById('buscadorColaboradores');
    if (buscador) {
        let debounceTimer;
        buscador.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => filtrarTabla(), 300);
        });
    }

    // FILTROS DROPDOWN (cambio -> recargar con query params)
    ['filtroEstado', 'filtroArea', 'filtroCargo'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', aplicarFiltrosUrl);
    });

    // BOTONES ACCIÓN TABLA (delegación de eventos)
    document.addEventListener('click', function (e) {
        const btnEditar = e.target.closest('.btn-editar-colab');
        if (btnEditar) {
            const id = btnEditar.getAttribute('data-id');
            abrirModalEditar(id);
        }
    });

    // VALIDACIÓN TIEMPO REAL: N° DOCUMENTO (solo números)
    const inputNumDoc = document.getElementById('form_num_doc');
    if (inputNumDoc) {
        inputNumDoc.addEventListener('input', function (e) {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
    }

    // VALIDACIÓN TIEMPO REAL: CELULAR / TELÉFONO
    ['form_celular', 'form_telefono', 'form_contacto_telefono'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', function () {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
    });

    // FECHA NACIMIENTO: máx 18 años (se setea en template, pero reforzamos)
    const inputFechaNac = document.getElementById('form_fecha_nacimiento');
    if (inputFechaNac) {
        const hoy = new Date();
        const maxDate = new Date(hoy.getFullYear() - 18, hoy.getMonth(), hoy.getDate());
        inputFechaNac.max = maxDate.toISOString().split('T')[0];
    }

    // FECHA INGRESO: por defecto hoy
    const inputFechaIng = document.getElementById('form_fecha_ingreso');
    if (inputFechaIng && !inputFechaIng.value) {
        inputFechaIng.value = new Date().toISOString().split('T')[0];
    }

    // AJUSTE ALTURA TABLA (ResponsiveObserver como en usuarios.html)
    ajustarAlturaTabla();
    new ResizeObserver(ajustarAlturaTabla).observe(document.body);

    // PREVENIR ENVÍO CON ENTER EN INPUTS DEL MODAL
    document.querySelectorAll('#formColaborador input').forEach(input => {
        input.addEventListener('keydown', e => { if (e.key === 'Enter') e.preventDefault(); });
    });

    // CARGAR CATÁLOGOS EPS/ARL UNA SOLA VEZ
    // (recargarlos en cada apertura del modal reiniciaba la selección)
    cargarEPS();
    cargarARL();

    // CATÁLOGOS DE TALLAS EPP (cada uno con su propia tabla)
    cargarTallasTodas();

    // CATÁLOGOS DE TEXTO LIBRE (departamento, ciudad, área, banco, etc.)
    cargarCatalogosTodos();
    const inputCatalogo = document.getElementById('nuevo_catalogo_nombre');
    if (inputCatalogo) {
        inputCatalogo.addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); guardarNuevoCatalogo(); }
        });
    }

    // Modales anidados (EPS, ARL, tallas, catálogos): al cerrarse, Bootstrap quita
    // "modal-open" del body aunque el modal de colaborador siga abierto.
    ['modalNuevaEPS', 'modalNuevaARL', 'modalNuevaTalla', 'modalNuevoCatalogo'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('hidden.bs.modal', () => {
            const colab = document.getElementById('modalColaborador');
            if (colab && colab.classList.contains('show')) {
                document.body.classList.add('modal-open');
            }
        });
    });

});

// ============================================================
// AJUSTE ALTURA TABLA
// ============================================================
function ajustarAlturaTabla() {
    const card = document.getElementById('contenedorTablaColaboradores');
    const scrollDiv = document.getElementById('scrollTablaColaboradores');
    if (card && scrollDiv) {
        const rect = card.getBoundingClientRect();
        const pixelesLibres = window.innerHeight - rect.top;
        const alturaPerfecta = pixelesLibres - 20;
        card.style.height = alturaPerfecta + "px";
        scrollDiv.style.maxHeight = alturaPerfecta + "px";
    }
}

// ============================================================
// FILTRADO TABLA (CLIENT-SIDE para búsqueda, SERVER-SIDE para dropdowns)
// ============================================================
function filtrarTabla() {
    const texto = document.getElementById('buscadorColaboradores').value.toLowerCase();
    const filas = document.querySelectorAll('#scrollTablaColaboradores tbody tr, #mobileCardsContainer .colab-card');
    filas.forEach(fila => {
        if (fila.querySelector('td[colspan]')) return; // fila "no hay datos"
        const textoFila = fila.textContent.toLowerCase();
        fila.style.display = textoFila.includes(texto) ? '' : 'none';
    });
}

function aplicarFiltrosUrl() {
    const params = new URLSearchParams(window.location.search);
    ['filtroEstado', 'filtroArea', 'filtroCargo'].forEach(id => {
        const val = document.getElementById(id).value;
        if (val) params.set(id.replace('filtro', '').toLowerCase(), val);
        else params.delete(id.replace('filtro', '').toLowerCase());
    });
    params.set('pagina', '1');
    window.location.href = `${window.location.pathname}?${params.toString()}`;
}

// ============================================================
// MODAL NUEVO COLABORADOR
// ============================================================
function abrirModalNuevo() {
    resetFormulario();
    aplicarCatalogosPorDefecto();
    document.getElementById('modalColaboradorTitulo').innerHTML = "<i class='bx bx-user-plus me-2'></i>Registrar Colaborador";
    document.getElementById('btnGuardarTexto').textContent = "Guardar Colaborador";
    const form = document.getElementById('formColaborador');
    form.action = form.dataset.urlCrear;
    
    // Deshabilitar botón de documentos al crear nuevo
    const btnDocs = document.getElementById('btnGestionarDocumentos');
    if (btnDocs) {
        btnDocs.disabled = true;
        btnDocs.href = '#';
    }
    const btnNuevoDoc = document.getElementById('btnNuevoDocumento');
    if (btnNuevoDoc) btnNuevoDoc.disabled = true;

    // Sin colaborador guardado: pestañas auxiliares bloqueadas
    colaboradorActualId = null;
    reiniciarPestanasAuxiliares();

    modalColaboradorUI.show();
}

// ============================================================
// MODAL EDITAR COLABORADOR
// ============================================================
function abrirModalEditar(id) {
    fetch(`/talento_humano/api/colaboradores/${id}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'ok') throw new Error(data.msg || 'Error cargando datos');
            poblarFormulario(data.colaborador);
            document.getElementById('modalColaboradorTitulo').innerHTML = "<i class='bx bx-edit me-2'></i>Editar Colaborador";
            document.getElementById('btnGuardarTexto').textContent = "Actualizar Colaborador";
            const form = document.getElementById('formColaborador');
            // Reemplazar el ID=0 en la URL base por el ID real
            form.action = form.dataset.urlEditar.replace('/0', `/${id}`);

            // Pestañas auxiliares del colaborador
            colaboradorActualId = data.colaborador.id;
            activarTabColaborador('tabDatos');
            cargarPestanasAuxiliares();

            modalColaboradorUI.show();
        })
        .catch(err => {
            console.error(err);
            Swal.fire('Error', 'No se pudo cargar la información del colaborador', 'error');
        });
}

function resetFormulario() {
    const form = document.getElementById('formColaborador');
    form.reset();
    document.getElementById('form_id').value = '';
    document.getElementById('form_eliminar_foto').value = '0';

    // Reset preview foto
    document.getElementById('preview_foto').style.display = 'none';
    document.getElementById('preview_foto').src = '';
    document.getElementById('preview_placeholder').style.display = 'flex';

    // Reset validaciones visuales
    form.querySelectorAll('.is-invalid, .is-valid').forEach(el => el.classList.remove('is-invalid', 'is-valid'));

    // Volver a la pestaña "Datos"
    if (document.getElementById('tabDatos-tab')) {
        activarTabColaborador('tabDatos');
    }

    // Reset jefe
    document.getElementById('form_jefe_id').value = '';
    document.getElementById('form_jefe_nombre').value = '';

    // Reiniciar desplegables de selección múltiple
    sincronizarMultiSelects();
}

function valorFechaInput(v) {
    if (!v) return '';
    const s = String(v);
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.substring(0, 10);
    const d = new Date(s);
    if (isNaN(d.getTime())) return '';
    const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(d.getUTCDate()).padStart(2, '0');
    return `${d.getUTCFullYear()}-${mm}-${dd}`;
}

// ============================================================
// DESPLEGABLES DE SELECCIÓN MÚLTIPLE (botón tipo select + casillas)
// ============================================================
function actualizarTextoMultiSelect(contenedor) {
    const select = document.getElementById(contenedor.dataset.target);
    const texto = contenedor.querySelector('.multi-select-text');
    if (!select || !texto) return;

    const valores = Array.from(select.selectedOptions).map(o => o.value);
    texto.textContent = valores.length ? valores.join(', ') : 'Seleccione';
    texto.classList.toggle('text-muted', valores.length === 0);
}

function sincronizarMultiSelect(contenedor) {
    const select = document.getElementById(contenedor.dataset.target);
    if (!select) return;

    const seleccionados = Array.from(select.selectedOptions).map(o => o.value);
    contenedor.querySelectorAll('.multi-select-check').forEach(chk => {
        chk.checked = seleccionados.includes(chk.value);
    });
    actualizarTextoMultiSelect(contenedor);
}

function sincronizarMultiSelects() {
    document.querySelectorAll('.multi-select').forEach(sincronizarMultiSelect);
}

document.addEventListener('change', function (e) {
    const chk = e.target.closest('.multi-select-check');
    if (!chk) return;

    const contenedor = chk.closest('.multi-select');
    if (!contenedor) return;

    const select = document.getElementById(contenedor.dataset.target);
    if (!select) return;

    const opcion = Array.from(select.options).find(o => o.value === chk.value);
    if (opcion) opcion.selected = chk.checked;

    actualizarTextoMultiSelect(contenedor);
});

document.addEventListener('DOMContentLoaded', sincronizarMultiSelects);

function poblarFormulario(colab) {
    resetFormulario();
    cerrarFormDocumento();
    docEditandoId = null;

    // Guardar valores de EPS y ARL para setear después de cargar opciones
    const epsVal = colab.eps;
    const arlVal = colab.arl;

    // Valores de tallas: se aplican cuando su catálogo termina de cargar
    const tallasVal = {
        camisa: colab.talla_camisa,
        pantalon: colab.talla_pantalon,
        botas: colab.talla_botas,
        casco: colab.talla_casco
    };

    // Relleno genérico: usa el atributo name de cada control del formulario
    const formEl = document.getElementById('formColaborador');

    formEl.querySelectorAll('input[name], select[name], textarea[name]').forEach(el => {
        const key = el.name;
        if (key === 'id' || key === 'eliminar_foto' || el.type === 'file') return;

        const raw = colab[key];

        if (el.type === 'checkbox') {
            el.checked = (raw === true || raw === 1 || raw === '1' || raw === 'true' || raw === 't');
            return;
        }

        // Selects de selección múltiple: se guardan como "LUZ, CELULAR"
        if (el.tagName === 'SELECT' && el.multiple) {
            const seleccionados = String(raw === null || raw === undefined ? '' : raw)
                .split(',')
                .map(s => s.trim())
                .filter(Boolean);
            Array.from(el.options).forEach(op => {
                op.selected = seleccionados.includes(op.value);
            });
            return;
        }

        // Selects "Sí/No" que en BD son booleanos (NULL se muestra como "No")
        if (el.tagName === 'SELECT' && (typeof raw === 'boolean' || key === 'tiene_internet')) {
            const activo = (raw === true || raw === 1 || raw === '1' || raw === 'true' || raw === 't');
            el.value = activo ? '1' : '0';
            return;
        }

        if (el.type === 'date') {
            el.value = valorFechaInput(raw);
            return;
        }

        el.value = (raw === null || raw === undefined) ? '' : raw;
    });

    // Reflejar en los desplegables múltiples lo cargado en los <select> ocultos
    sincronizarMultiSelects();

    // Jefe inmediato
    if (colab.jefe_inmediato_id) {
        document.getElementById('form_jefe_id').value = colab.jefe_inmediato_id;
        fetch(`/talento_humano/api/colaboradores/${colab.jefe_inmediato_id}`)
            .then(r => r.json())
            .then(d => { if (d.status === 'ok') document.getElementById('form_jefe_nombre').value = d.colaborador.nombre_completo; });
    }

    // Foto perfil
    if (colab.foto_perfil) {
        document.getElementById('preview_foto').src = `/static/${colab.foto_perfil}`;
        document.getElementById('preview_foto').style.display = 'block';
        document.getElementById('preview_placeholder').style.display = 'none';
    }

    // Cargar EPS y ARL y luego setear valores
    Promise.all([
        cargarEPS(epsVal),
        cargarARL(arlVal),
        cargarTalla('camisa', tallasVal.camisa),
        cargarTalla('pantalon', tallasVal.pantalon),
        cargarTalla('botas', tallasVal.botas),
        cargarTalla('casco', tallasVal.casco),
        cargarCatalogosColaborador(colab)
    ]).then(() => {
        // Habilitar/deshabilitar botón de documentos según si hay ID
        const btnDocs = document.getElementById('btnGestionarDocumentos');
        const formId = document.getElementById('form_id').value;
        if (btnDocs) {
            if (formId) {
                btnDocs.disabled = false;
                btnDocs.href = `/talento_humano/documentos?colaborador_id=${formId}`;
                const btnNuevoDoc = document.getElementById('btnNuevoDocumento');
                if (btnNuevoDoc) btnNuevoDoc.disabled = false;
            } else {
                btnDocs.disabled = true;
                btnDocs.href = '#';
            }
        }
    });
}

// ============================================================
// PREVISUALIZAR FOTO
// ============================================================
function previsualizarFoto(input) {
    const previewImg = document.getElementById('preview_foto');
    const placeholder = document.getElementById('preview_placeholder');

    if (input.files && input.files[0]) {
        const file = input.files[0];
        // Validar tamaño cliente (5MB)
        if (file.size > 5 * 1024 * 1024) {
            Swal.fire('Archivo muy grande', 'La foto no debe superar 5 MB', 'warning');
            input.value = '';
            return;
        }
        // Validar tipo
        if (!file.type.startsWith('image/')) {
            Swal.fire('Tipo inválido', 'Solo se permiten imágenes (JPG, PNG, WEBP)', 'warning');
            input.value = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            previewImg.src = e.target.result;
            previewImg.style.display = 'block';
            placeholder.style.display = 'none';
        };
        reader.readAsDataURL(file);
    } else {
        previewImg.style.display = 'none';
        previewImg.src = '';
        placeholder.style.display = 'flex';
    }
}

// ============================================================
// VALIDAR DOCUMENTO ÚNICO (AJAX)
// ============================================================
function validarDocUnico() {
    const tipoDoc = document.getElementById('form_tipo_doc').value;
    const numDoc = document.getElementById('form_num_doc').value.trim();
    const idActual = document.getElementById('form_id').value; // vacío si nuevo

    if (!numDoc) {
        Swal.fire('Campo requerido', 'Ingrese el número de documento', 'warning');
        return;
    }

    const btn = document.getElementById('btnValidarDoc');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;

    fetch(`/talento_humano/api/colaboradores/validar-doc?tipo=${tipoDoc}&num=${numDoc}${idActual ? `&excluir=${idActual}` : ''}`)
        .then(r => r.json())
        .then(data => {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
            if (data.disponible) {
                Swal.fire('Disponible', `El documento ${tipoDoc} ${numDoc} está disponible`, 'success');
                document.getElementById('form_num_doc').classList.add('is-valid');
                document.getElementById('form_num_doc').classList.remove('is-invalid');
            } else {
                Swal.fire('Ya existe', `Ya hay un colaborador con ${tipoDoc} ${numDoc}: ${data.nombre_existente}`, 'error');
                document.getElementById('form_num_doc').classList.add('is-invalid');
                document.getElementById('form_num_doc').classList.remove('is-valid');
            }
        })
        .catch(() => {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
            Swal.fire('Error', 'No se pudo validar el documento', 'error');
        });
}

// ============================================================
// BUSCAR JEFE INMEDIATO (TomSelect en modal)
// ============================================================
function inicializarTomSelectJefe() {
    const input = document.getElementById('inputBuscarJefe');
    if (!input || window.tomSelectJefeInited) return;

    window.tomSelectJefeInited = true;

    tomSelectJefe = new TomSelect(input, {
        valueField: 'id',
        labelField: 'text',
        searchField: ['text', 'num_doc'],
        create: false,
        render: {
            option: (data, escape) => `
                <div class="d-flex align-items-center gap-2 p-2">
                    <div class="fw-bold">${escape(data.text)}</div>
                    <small class="text-muted">Doc: ${escape(data.num_doc)}</small>
                </div>
            `,
            item: (data, escape) => `<div>${escape(data.text)}</div>`
        },
        load: (query, callback) => {
            if (!query || query.length < 2) return callback();
            fetch(`/talento_humano/api/colaboradores/buscar?q=${encodeURIComponent(query)}&limit=20`)
                .then(r => r.json())
                .then(data => callback(data.results || []))
                .catch(() => callback());
        },
        onChange: (value) => {
            if (value) {
                const item = tomSelectJefe.options[value];
                document.getElementById('form_jefe_id').value = value;
                document.getElementById('form_jefe_nombre').value = item.text;
                modalBuscarJefeUI.hide();
            }
        }
    });
}

function abrirBuscarJefe() {
    modalBuscarJefeUI.show();
    // Focus input después de mostrar modal
    setTimeout(() => document.getElementById('inputBuscarJefe').focus(), 300);
}

// ============================================================
// TOGGLE ESTADO (ACTIVO/INACTIVO)
// ============================================================
function toggleEstado(id) {
    const fila = document.querySelector(`[data-id="${id}"]`);
    const estadoActual = fila?.querySelector('.badge-estado')?.textContent?.trim() || 'Activo';
    const nuevoEstado = estadoActual === 'Activo' ? 'Inactivo' : 'Activo';
    const accion = nuevoEstado === 'Activo' ? 'activar' : 'desactivar';

    Swal.fire({
        title: `¿${accion.charAt(0).toUpperCase() + accion.slice(1)} colaborador?`,
        text: `El estado cambiará a "${nuevoEstado}"`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#97271C',
        cancelButtonColor: '#6c757d',
        confirmButtonText: `Sí, ${accion}`,
        cancelButtonText: 'Cancelar'
    }).then(result => {
        if (result.isConfirmed) {
            fetch(`/talento_humano/api/colaboradores/toggle/${id}`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'ok') {
                        window.location.reload();
                    } else {
                        Swal.fire('Error', data.msg || 'No se pudo cambiar el estado', 'error');
                    }
                });
        }
    });
}

// ============================================================
// VER FICHA COMPLETA (HOJA DE VIDA)
// ============================================================
function verDetalle(id) {
    window.location.href = `/talento_humano/colaboradores/${id}/ficha`;
}

// ============================================================
// ELIMINAR (SOFT DELETE)
// ============================================================
function eliminarColaborador(id, nombre) {
    Swal.fire({
        title: '¿Eliminar colaborador?',
        html: `Se marcará como eliminado (soft delete) a:<br><strong>${nombre}</strong><br><br>Los documentos, estudios y cursos se conservarán.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#97271C',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    }).then(result => {
        if (result.isConfirmed) {
            fetch(`/talento_humano/api/colaboradores/eliminar/${id}`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'ok') {
                        Swal.fire('Eliminado', 'Colaborador marcado como eliminado', 'success').then(() => window.location.reload());
                    } else {
                        Swal.fire('Error', data.msg || 'No se pudo eliminar', 'error');
                    }
                });
        }
    });
}

// ============================================================
// SUBMIT FORM (ANTI-DOBLE-CLIC + SPINNER) - Se usa el global de layout.js
// ============================================================
// El layout.js ya intercepta todos los forms y maneja spinner/doble-clic
// Solo necesitamos validar antes de enviar
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formColaborador');
    if (form) {
        form.addEventListener('submit', function (e) {
            // Validaciones finales
            const requiredFields = form.querySelectorAll('[required]');
            let invalido = false;
            let firstInvalidField = null;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    if (!invalido) firstInvalidField = field;
                    invalido = true;
                } else {
                    field.classList.remove('is-invalid');
                }
            });

            // Validar jefe si se ingresó nombre pero no ID
            const jefeNombre = document.getElementById('form_jefe_nombre').value;
            const jefeId = document.getElementById('form_jefe_id').value;
            if (jefeNombre && !jefeId) {
                document.getElementById('form_jefe_nombre').classList.add('is-invalid');
                if (!invalido) firstInvalidField = document.getElementById('form_jefe_nombre');
                invalido = true;
            }

            if (invalido) {
                e.preventDefault();
                e.stopPropagation();

                // Restaurar botón (layout.js lo dejó en loading)
                const btn = form.querySelector('button[type="submit"]');
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<i class='bx bx-save me-1'></i> <span id="btnGuardarTexto">${document.getElementById('form_id').value ? 'Actualizar Colaborador' : 'Guardar Colaborador'}</span>`;
                }

                // Ir a la pestaña que contiene el primer campo inválido
                if (firstInvalidField) {
                    const pane = firstInvalidField.closest('.tab-pane');
                    if (pane && pane.id) {
                        activarTabColaborador(pane.id);
                    }
                    setTimeout(() => firstInvalidField.focus(), 300);
                }

                Swal.fire('Campos requeridos', 'Complete todos los campos marcados con *', 'warning');
            }
        });
    }
});

// ============================================================
// CATÁLOGOS EPS / ARL
// ============================================================

let modalNuevaEPS_UI, modalNuevaARL_UI;
let epsCargadas = false;
let arlCargadas = false;

/**
 * Selecciona un valor en un <select> aunque no exista como opción.
 * Si el valor guardado ya no está en el catálogo (nombre viejo) o viene
 * como id numérico, lo agrega/selecciona para no perderlo.
 */
function aplicarValorSelect(select, valor) {
    if (!select || valor === null || valor === undefined || valor === '') return;
    const v = String(valor);

    select.value = v;
    if (select.value === v) return;

    // ¿Viene como id numérico? Buscar la opción por data-id
    const porId = Array.from(select.options).find(o => o.dataset.id === v);
    if (porId) {
        select.value = porId.value;
        return;
    }

    // Valor legado que ya no está en el catálogo: mostrarlo igual
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    opt.dataset.legado = '1';
    select.appendChild(opt);
    select.value = v;
}

function cargarEPS(seleccionar = null, forzar = false) {
    const select = document.getElementById('form_eps');
    if (!select) return Promise.resolve();
    const objetivo = (seleccionar !== null && seleccionar !== undefined && seleccionar !== '')
        ? seleccionar
        : (select.value || null);

    // Ya cargadas: solo aplicar el valor (evita carreras entre peticiones)
    if (epsCargadas && !forzar && select.options.length > 1) {
        aplicarValorSelect(select, objetivo);
        return Promise.resolve();
    }

    return fetch('/talento_humano/api/eps')
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'ok') return;
            select.innerHTML = '<option value="">Seleccione EPS</option>';
            data.eps.forEach(e => {
                const opt = document.createElement('option');
                opt.value = e.nombre;  // La BD guarda el NOMBRE
                opt.textContent = e.nombre;
                opt.dataset.id = e.id;
                select.appendChild(opt);
            });
            epsCargadas = true;
            aplicarValorSelect(select, objetivo);
        })
        .catch(() => {});
}

function cargarARL(seleccionar = null, forzar = false) {
    const select = document.getElementById('form_arl');
    if (!select) return Promise.resolve();
    const objetivo = (seleccionar !== null && seleccionar !== undefined && seleccionar !== '')
        ? seleccionar
        : (select.value || null);

    if (arlCargadas && !forzar && select.options.length > 1) {
        aplicarValorSelect(select, objetivo);
        return Promise.resolve();
    }

    return fetch('/talento_humano/api/arl')
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'ok') return;
            select.innerHTML = '<option value="">Seleccione ARL</option>';
            data.arl.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.nombre;  // La BD guarda el NOMBRE
                opt.textContent = a.nombre;
                opt.dataset.id = a.id;
                select.appendChild(opt);
            });
            arlCargadas = true;
            aplicarValorSelect(select, objetivo);
        })
        .catch(() => {});
}

function abrirModalNuevaEPS() {
    if (!modalNuevaEPS_UI) {
        const el = document.getElementById('modalNuevaEPS');
        if (el) modalNuevaEPS_UI = new bootstrap.Modal(el);
    }
    document.getElementById('nueva_eps_nombre').value = '';
    document.getElementById('nueva_eps_codigo').value = '';
    modalNuevaEPS_UI.show();
    setTimeout(() => document.getElementById('nueva_eps_nombre').focus(), 300);
}

function abrirModalNuevaARL() {
    if (!modalNuevaARL_UI) {
        const el = document.getElementById('modalNuevaARL');
        if (el) modalNuevaARL_UI = new bootstrap.Modal(el);
    }
    document.getElementById('nueva_arl_nombre').value = '';
    document.getElementById('nueva_arl_codigo').value = '';
    modalNuevaARL_UI.show();
    setTimeout(() => document.getElementById('nueva_arl_nombre').focus(), 300);
}

function guardarNuevaEPS() {
    const nombre = document.getElementById('nueva_eps_nombre').value.trim();
    const codigo = document.getElementById('nueva_eps_codigo').value.trim().toUpperCase() || null;

    if (!nombre) {
        Swal.fire('Campo requerido', 'El nombre de la EPS es obligatorio', 'warning');
        return;
    }

    const btn = event.target;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creando...';

    fetch('/talento_humano/api/eps/crear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, codigo })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = 'Crear EPS';
            if (data.status === 'ok') {
                Swal.fire('¡Creado!', `EPS "${data.nombre}" creada exitosamente`, 'success');
                modalNuevaEPS_UI.hide();
                cargarEPS(data.nombre, true); // Recargar select y seleccionar la nueva
            } else {
                Swal.fire('Error', data.msg || 'No se pudo crear la EPS', 'error');
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = 'Crear EPS';
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

function guardarNuevaARL() {
    const nombre = document.getElementById('nueva_arl_nombre').value.trim();
    const codigo = document.getElementById('nueva_arl_codigo').value.trim().toUpperCase() || null;

    if (!nombre) {
        Swal.fire('Campo requerido', 'El nombre de la ARL es obligatorio', 'warning');
        return;
    }

    const btn = event.target;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creando...';

    fetch('/talento_humano/api/arl/crear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, codigo })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = 'Crear ARL';
            if (data.status === 'ok') {
                Swal.fire('¡Creado!', `ARL "${data.nombre}" creada exitosamente`, 'success');
                modalNuevaARL_UI.hide();
                cargarARL(data.nombre, true); // Recargar select y seleccionar la nueva
            } else {
                Swal.fire('Error', data.msg || 'No se pudo crear la ARL', 'error');
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = 'Crear ARL';
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

// ============================================================
// CATÁLOGOS DE TALLAS EPP (camisa, pantalón, botas, casco)
// ============================================================

const CATALOGOS_TALLA = {
    camisa:   { select: 'form_talla_camisa',   etiqueta: 'camisa' },
    pantalon: { select: 'form_talla_pantalon', etiqueta: 'pantalón' },
    botas:    { select: 'form_talla_botas',    etiqueta: 'botas' },
    casco:    { select: 'form_talla_casco',    etiqueta: 'casco' }
};

const tallasCargadas = { camisa: false, pantalon: false, botas: false, casco: false };
let modalNuevaTalla_UI = null;

function cargarTalla(tipo, seleccionar = null, forzar = false) {
    const cfg = CATALOGOS_TALLA[tipo];
    if (!cfg) return Promise.resolve();

    const select = document.getElementById(cfg.select);
    if (!select) return Promise.resolve();

    const objetivo = (seleccionar !== null && seleccionar !== undefined && seleccionar !== '')
        ? seleccionar
        : (select.value || null);

    // Ya cargadas: solo aplicar el valor (evita carreras entre peticiones)
    if (tallasCargadas[tipo] && !forzar && select.options.length > 1) {
        aplicarValorSelect(select, objetivo);
        return Promise.resolve();
    }

    return fetch(`/talento_humano/api/tallas/${tipo}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'ok') return;
            select.innerHTML = '<option value="">Seleccione</option>';
            data.tallas.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.nombre;  // La BD guarda el NOMBRE
                opt.textContent = t.nombre;
                opt.dataset.id = t.id;
                select.appendChild(opt);
            });
            tallasCargadas[tipo] = true;
            aplicarValorSelect(select, objetivo);
        })
        .catch(() => {});
}

function cargarTallasTodas() {
    return Promise.all(Object.keys(CATALOGOS_TALLA).map(t => cargarTalla(t)));
}

function abrirModalNuevaTalla(tipo) {
    const cfg = CATALOGOS_TALLA[tipo];
    if (!cfg) return;

    if (!modalNuevaTalla_UI) {
        const el = document.getElementById('modalNuevaTalla');
        if (el) modalNuevaTalla_UI = new bootstrap.Modal(el);
    }
    if (!modalNuevaTalla_UI) return;

    document.getElementById('nueva_talla_tipo').value = tipo;
    document.getElementById('nueva_talla_titulo').textContent = cfg.etiqueta;
    document.getElementById('nueva_talla_nombre').value = '';
    document.getElementById('nueva_talla_codigo').value = '';
    modalNuevaTalla_UI.show();
    setTimeout(() => document.getElementById('nueva_talla_nombre').focus(), 300);
}

function guardarNuevaTalla(boton) {
    const tipo = document.getElementById('nueva_talla_tipo').value;
    const cfg = CATALOGOS_TALLA[tipo];
    if (!cfg) return;

    const nombre = document.getElementById('nueva_talla_nombre').value.trim();
    const codigo = document.getElementById('nueva_talla_codigo').value.trim().toUpperCase() || null;

    if (!nombre) {
        Swal.fire('Campo requerido', `El nombre de la talla de ${cfg.etiqueta} es obligatorio`, 'warning');
        return;
    }

    const btn = boton || null;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creando...';
    }

    fetch(`/talento_humano/api/tallas/${tipo}/crear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, codigo })
    })
        .then(r => r.json())
        .then(data => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Crear talla';
            }
            if (data.status === 'ok') {
                Swal.fire('¡Creada!', `Talla "${data.nombre}" creada exitosamente`, 'success');
                if (modalNuevaTalla_UI) modalNuevaTalla_UI.hide();
                cargarTalla(tipo, data.nombre, true); // Recargar select y seleccionar la nueva
            } else {
                Swal.fire('Error', data.msg || 'No se pudo crear la talla', 'error');
            }
        })
        .catch(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Crear talla';
            }
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

// ============================================================
// CATÁLOGOS DE TEXTO LIBRE
// (departamento, ciudad, nacimiento, nacionalidad, religión,
//  área, fondos, caja de compensación y banco)
// Cada campo tiene su propia tabla y su propio endpoint.
// ============================================================

const CATALOGOS_TH = {
    departamento:            { select: 'form_departamento',      etiqueta: 'Departamento',              nombre_label: 'Nombre del departamento' },
    ciudad:                  { select: 'form_ciudad',            etiqueta: 'Ciudad',                    nombre_label: 'Nombre de la ciudad' },
    ciudad_nacimiento:       { select: 'form_lugar_nac_ciudad',  etiqueta: 'Ciudad de nacimiento',       campo: 'lugar_nacimiento_ciudad',       nombre_label: 'Nombre de la ciudad' },
    departamento_nacimiento: { select: 'form_lugar_nac_depto',   etiqueta: 'Departamento de nacimiento', campo: 'lugar_nacimiento_departamento', nombre_label: 'Nombre del departamento' },
    pais_nacimiento:         { select: 'form_lugar_nac_pais',    etiqueta: 'País de nacimiento',         campo: 'lugar_nacimiento_pais',         nombre_label: 'Nombre del país' },
    nacionalidad:            { select: 'form_nacionalidad',      etiqueta: 'Nacionalidad',              nombre_label: 'Nombre de la nacionalidad' },
    religion:                { select: 'form_religion',          etiqueta: 'Religión',                  nombre_label: 'Nombre de la religión' },
    area:                    { select: 'form_area',              etiqueta: 'Área',                      nombre_label: 'Nombre del área' },
    fondo_pension:           { select: 'form_fondo_pension',     etiqueta: 'Fondo de pensión',          nombre_label: 'Nombre del fondo' },
    fondo_cesantias:         { select: 'form_fondo_cesantias',   etiqueta: 'Fondo de cesantías',        nombre_label: 'Nombre del fondo' },
    caja_compensacion:       { select: 'form_caja_compensacion', etiqueta: 'Caja de compensación',      nombre_label: 'Nombre de la caja' },
    banco:                   { select: 'form_banco',             etiqueta: 'Banco',                     nombre_label: 'Nombre del banco' }
};

// Solo se aplican al registrar un colaborador nuevo (no al editar)
const CATALOGOS_TH_DEFECTOS = {
    pais_nacimiento: 'COLOMBIA',
    nacionalidad: 'COLOMBIANA'
};

const catalogosCargados = {};
let modalNuevoCatalogo_UI = null;

function campoColaboradorCatalogo(campo) {
    const cfg = CATALOGOS_TH[campo];
    return (cfg && cfg.campo) ? cfg.campo : campo;
}

function cargarCatalogo(campo, seleccionar = null, forzar = false) {
    const cfg = CATALOGOS_TH[campo];
    if (!cfg) return Promise.resolve();

    const select = document.getElementById(cfg.select);
    if (!select) return Promise.resolve();

    const objetivo = (seleccionar !== null && seleccionar !== undefined && seleccionar !== '')
        ? seleccionar
        : (select.value || null);

    // Ya cargado: solo aplicar el valor (evita carreras entre peticiones)
    if (catalogosCargados[campo] && !forzar && select.options.length > 1) {
        aplicarValorSelect(select, objetivo);
        return Promise.resolve();
    }

    return fetch(`/talento_humano/api/catalogos/${campo}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'ok') return;
            select.innerHTML = `<option value="">Seleccione ${cfg.etiqueta.toLowerCase()}</option>`;
            data.registros.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r.nombre;  // La BD guarda el NOMBRE
                opt.textContent = r.nombre;
                opt.dataset.id = r.id;
                select.appendChild(opt);
            });
            catalogosCargados[campo] = true;
            aplicarValorSelect(select, objetivo);
        })
        .catch(() => {});
}

function cargarCatalogosTodos() {
    return Promise.all(Object.keys(CATALOGOS_TH).map(c => cargarCatalogo(c)));
}

function cargarCatalogosColaborador(colab) {
    return Promise.all(Object.keys(CATALOGOS_TH).map(campo => {
        const valor = colab[campoColaboradorCatalogo(campo)];
        return cargarCatalogo(campo, valor);
    }));
}

function aplicarCatalogosPorDefecto() {
    Object.keys(CATALOGOS_TH_DEFECTOS).forEach(campo => {
        const cfg = CATALOGOS_TH[campo];
        if (!cfg) return;
        const select = document.getElementById(cfg.select);
        if (select) aplicarValorSelect(select, CATALOGOS_TH_DEFECTOS[campo]);
    });
}

function abrirModalNuevoCatalogo(campo) {
    const cfg = CATALOGOS_TH[campo];
    if (!cfg) return;

    if (!modalNuevoCatalogo_UI) {
        const el = document.getElementById('modalNuevoCatalogo');
        if (el) modalNuevoCatalogo_UI = new bootstrap.Modal(el);
    }
    if (!modalNuevoCatalogo_UI) return;

    document.getElementById('nuevo_catalogo_campo').value = campo;
    document.getElementById('nuevo_catalogo_titulo').textContent = cfg.etiqueta;
    document.getElementById('nuevo_catalogo_etiqueta').innerHTML =
        `${cfg.nombre_label} <span class="text-danger">*</span>`;
    document.getElementById('nuevo_catalogo_nombre').value = '';
    modalNuevoCatalogo_UI.show();
    setTimeout(() => document.getElementById('nuevo_catalogo_nombre').focus(), 300);
}

function guardarNuevoCatalogo(boton) {
    const campo = document.getElementById('nuevo_catalogo_campo').value;
    const cfg = CATALOGOS_TH[campo];
    if (!cfg) return;

    const nombre = document.getElementById('nuevo_catalogo_nombre').value.trim();

    if (!nombre) {
        Swal.fire('Campo requerido', 'El nombre es obligatorio', 'warning');
        return;
    }

    const btn = boton || document.getElementById('btnGuardarCatalogo');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creando...';
    }

    fetch(`/talento_humano/api/catalogos/${campo}/crear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre })
    })
        .then(r => r.json())
        .then(data => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Crear registro';
            }
            if (data.status === 'ok') {
                Swal.fire('¡Creado!', `"${data.nombre}" se agregó al catálogo de ${cfg.etiqueta.toLowerCase()}`, 'success');
                if (modalNuevoCatalogo_UI) modalNuevoCatalogo_UI.hide();
                cargarCatalogo(campo, data.nombre, true); // Recargar select y seleccionar el nuevo
            } else {
                Swal.fire('Error', data.msg || 'No se pudo crear el registro', 'error');
            }
        })
        .catch(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Crear registro';
            }
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

// ============================================================
// PESTAÑAS DEL MODAL DE COLABORADOR
// ============================================================
function activarTabColaborador(tabId) {
    const btn = document.getElementById(tabId + '-tab');
    if (!btn) return;
    if (window.bootstrap && bootstrap.Tab) {
        bootstrap.Tab.getOrCreateInstance(btn).show();
    } else {
        btn.click();
    }
}

function actualizarAvisosPestanas() {
    ['tabCapacitaciones', 'tabExperiencia', 'tabFamiliares', 'tabDocumentos'].forEach(id => {
        const aviso = document.getElementById('aviso_' + id);
        if (aviso) aviso.classList.toggle('d-none', !!colaboradorActualId);
    });
}

function reiniciarPestanasAuxiliares() {
    cacheCapacitaciones = [];
    cacheExperiencia = [];
    cacheFamiliares = [];
    cacheDocumentos = [];
    renderCapacitaciones();
    renderExperiencia();
    renderFamiliares();
    renderDocumentos();
    renderChecklistDocumentos({});
    cerrarFormDocumento();
    actualizarAvisosPestanas();
    activarTabColaborador('tabDatos');
}

function cargarPestanasAuxiliares() {
    actualizarAvisosPestanas();
    cargarCapacitaciones();
    cargarExperiencia();
    cargarFamiliares();
    cargarDocumentos();
}

function volverAlColaborador(tabId) {
    setTimeout(() => {
        if (modalColaboradorUI) modalColaboradorUI.show();
        setTimeout(() => activarTabColaborador(tabId || 'tabDatos'), 250);
    }, 220);
}

// Utilidades de formato
function esc(v) {
    if (v === null || v === undefined) return '';
    return String(v)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function fmtFecha(v) {
    if (!v) return '—';
    const s = String(v).substring(0, 10);
    const p = s.split('-');
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : s;
}

function filaVacia(tbodyId, columnas) {
    const tb = document.getElementById(tbodyId);
    if (tb) {
        tb.innerHTML = `<tr><td colspan="${columnas}" class="text-center text-muted py-3">
            <i class='bx bx-info-circle me-1'></i> Sin registros</td></tr>`;
    }
}

// ============================================================
// CAPACITACIONES
// ============================================================
function cargarCapacitaciones() {
    const id = colaboradorActualId;
    if (!id) { cacheCapacitaciones = []; renderCapacitaciones(); return; }
    fetch(`/talento_humano/api/colaboradores/${id}/capacitaciones?todas=1`)
        .then(r => r.json())
        .then(data => {
            if (id !== colaboradorActualId) return;
            cacheCapacitaciones = data.capacitaciones || [];
            renderCapacitaciones();
        })
        .catch(() => { cacheCapacitaciones = []; renderCapacitaciones(); });
}

function renderCapacitaciones() {
    const tb = document.getElementById('tbodyCapacitaciones');
    if (!tb) return;
    if (!cacheCapacitaciones.length) { filaVacia('tbodyCapacitaciones', 7); return; }

    tb.innerHTML = cacheCapacitaciones.map(c => {
        const vencida = c.fecha_vencimiento && String(c.fecha_vencimiento).substring(0, 10) <
            new Date().toISOString().substring(0, 10);
        return `<tr>
            <td class="fw-semibold">${esc(c.nombre_curso)}</td>
            <td><span class="badge bg-secondary-subtle text-dark">${esc(c.tipo_capacitacion)}</span></td>
            <td>${esc(c.entidad_certificadora) || '—'}</td>
            <td>${fmtFecha(c.fecha_inicio)}</td>
            <td class="${vencida ? 'text-danger fw-bold' : ''}">${fmtFecha(c.fecha_vencimiento)}${vencida ? ' <i class="bx bx-error"></i>' : ''}</td>
            <td>${c.horas_duracion || '—'}</td>
            <td class="text-end text-nowrap">
                <button type="button" class="btn btn-sm btn-outline-primary py-0 px-1 me-1" title="Editar"
                    onclick="editarCapacitacion(${c.id})"><i class='bx bx-edit'></i></button>
                <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" title="Eliminar"
                    onclick="eliminarCapacitacion(${c.id})"><i class='bx bx-trash'></i></button>
            </td>
        </tr>`;
    }).join('');
}

function abrirModalCapacitacion() {
    if (!colaboradorActualId) {
        Swal.fire('Atención', 'Guarde primero el colaborador para registrar capacitaciones.', 'info');
        return;
    }
    const el = document.getElementById('modalCapacitacion');
    if (!modalCapacitacionUI) modalCapacitacionUI = new bootstrap.Modal(el);

    document.getElementById('cap_id').value = '';
    document.getElementById('cap_tipo').value = '';
    document.getElementById('cap_curso').value = '';
    document.getElementById('cap_entidad').value = '';
    document.getElementById('cap_horas').value = '';
    document.getElementById('cap_inicio').value = '';
    document.getElementById('cap_fin').value = '';
    document.getElementById('cap_vencimiento').value = '';
    document.getElementById('cap_aprobado').value = 'true';
    document.getElementById('cap_observaciones').value = '';

    if (modalColaboradorUI) modalColaboradorUI.hide();
    setTimeout(() => modalCapacitacionUI.show(), 250);
}

function editarCapacitacion(id) {
    const c = cacheCapacitaciones.find(x => Number(x.id) === Number(id));
    if (!c) return;
    abrirModalCapacitacion();
    document.getElementById('cap_id').value = c.id;
    document.getElementById('cap_tipo').value = c.tipo_capacitacion || '';
    document.getElementById('cap_curso').value = c.nombre_curso || '';
    document.getElementById('cap_entidad').value = c.entidad_certificadora || '';
    document.getElementById('cap_horas').value = c.horas_duracion || '';
    document.getElementById('cap_inicio').value = (c.fecha_inicio || '').substring(0, 10);
    document.getElementById('cap_fin').value = (c.fecha_fin || '').substring(0, 10);
    document.getElementById('cap_vencimiento').value = (c.fecha_vencimiento || '').substring(0, 10);
    document.getElementById('cap_aprobado').value = c.aprobado ? 'true' : 'false';
    document.getElementById('cap_observaciones').value = c.observaciones || '';
}

function guardarCapacitacion() {
    const id = document.getElementById('cap_id').value;
    const payload = {
        tipo_capacitacion: document.getElementById('cap_tipo').value,
        nombre_curso: document.getElementById('cap_curso').value.trim(),
        entidad_certificadora: document.getElementById('cap_entidad').value.trim(),
        horas_duracion: document.getElementById('cap_horas').value || null,
        fecha_inicio: document.getElementById('cap_inicio').value || null,
        fecha_fin: document.getElementById('cap_fin').value || null,
        fecha_vencimiento: document.getElementById('cap_vencimiento').value || null,
        aprobado: document.getElementById('cap_aprobado').value === 'true',
        observaciones: document.getElementById('cap_observaciones').value.trim()
    };

    if (!payload.tipo_capacitacion || !payload.nombre_curso) {
        Swal.fire('Campos requeridos', 'Seleccione el tipo y escriba el nombre del curso.', 'warning');
        return;
    }

    const btn = document.getElementById('btnGuardarCapacitacion');
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Guardando...';

    const url = id
        ? `/talento_humano/api/capacitaciones/${id}`
        : `/talento_humano/api/colaboradores/${colaboradorActualId}/capacitaciones`;

    fetch(url, {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = html;
            if (data.status === 'ok') {
                if (modalCapacitacionUI) modalCapacitacionUI.hide();
                cargarCapacitaciones();
                volverAlColaborador('tabCapacitaciones');
            } else {
                Swal.fire('Error', data.msg || 'No se pudo guardar la capacitación', 'error');
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = html;
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

function eliminarCapacitacion(id) {
    const c = cacheCapacitaciones.find(x => Number(x.id) === Number(id));
    Swal.fire({
        title: '¿Eliminar capacitación?',
        text: c ? c.nombre_curso : '',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#97271C',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then(res => {
        if (!res.isConfirmed) return;
        fetch(`/talento_humano/api/capacitaciones/${id}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    cargarCapacitaciones();
                    Swal.fire('Eliminada', 'La capacitación fue eliminada', 'success');
                } else {
                    Swal.fire('Error', data.msg || 'No se pudo eliminar', 'error');
                }
            })
            .catch(() => Swal.fire('Error', 'Error de conexión', 'error'));
    });
}

// ============================================================
// EXPERIENCIA LABORAL
// ============================================================
function cargarExperiencia() {
    const id = colaboradorActualId;
    if (!id) { cacheExperiencia = []; renderExperiencia(); return; }
    fetch(`/talento_humano/api/colaboradores/${id}/experiencia`)
        .then(r => r.json())
        .then(data => {
            if (id !== colaboradorActualId) return;
            cacheExperiencia = data.experiencia || [];
            renderExperiencia();
        })
        .catch(() => { cacheExperiencia = []; renderExperiencia(); });
}

function renderExperiencia() {
    const tb = document.getElementById('tbodyExperiencia');
    if (!tb) return;
    if (!cacheExperiencia.length) { filaVacia('tbodyExperiencia', 7); return; }

    tb.innerHTML = cacheExperiencia.map(e => `<tr>
            <td class="fw-semibold">${esc(e.empresa)}</td>
            <td>${esc(e.cargo)}</td>
            <td>${fmtFecha(e.fecha_inicio)}</td>
            <td>${e.fecha_fin ? fmtFecha(e.fecha_fin) : '<span class="badge bg-success-subtle text-dark">Actual</span>'}</td>
            <td>${esc(e.jefe_inmediato) || '—'}</td>
            <td>${esc(e.motivo_retiro) || '—'}</td>
            <td class="text-end text-nowrap">
                <button type="button" class="btn btn-sm btn-outline-primary py-0 px-1 me-1" title="Editar"
                    onclick="editarExperiencia(${e.id})"><i class='bx bx-edit'></i></button>
                <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" title="Eliminar"
                    onclick="eliminarExperiencia(${e.id})"><i class='bx bx-trash'></i></button>
            </td>
        </tr>`).join('');
}

function abrirModalExperiencia() {
    if (!colaboradorActualId) {
        Swal.fire('Atención', 'Guarde primero el colaborador para registrar experiencia.', 'info');
        return;
    }
    const el = document.getElementById('modalExperiencia');
    if (!modalExperienciaUI) modalExperienciaUI = new bootstrap.Modal(el);

    document.getElementById('exp_id').value = '';
    ['exp_empresa', 'exp_cargo', 'exp_sector', 'exp_inicio', 'exp_fin',
        'exp_jefe', 'exp_telefono', 'exp_motivo', 'exp_funciones'].forEach(i => {
            const f = document.getElementById(i);
            if (f) f.value = '';
        });

    if (modalColaboradorUI) modalColaboradorUI.hide();
    setTimeout(() => modalExperienciaUI.show(), 250);
}

function editarExperiencia(id) {
    const e = cacheExperiencia.find(x => Number(x.id) === Number(id));
    if (!e) return;
    abrirModalExperiencia();
    document.getElementById('exp_id').value = e.id;
    document.getElementById('exp_empresa').value = e.empresa || '';
    document.getElementById('exp_cargo').value = e.cargo || '';
    document.getElementById('exp_sector').value = e.sector_empresa || '';
    document.getElementById('exp_inicio').value = (e.fecha_inicio || '').substring(0, 10);
    document.getElementById('exp_fin').value = (e.fecha_fin || '').substring(0, 10);
    document.getElementById('exp_jefe').value = e.jefe_inmediato || '';
    document.getElementById('exp_telefono').value = e.telefono_referencia || '';
    document.getElementById('exp_motivo').value = e.motivo_retiro || '';
    document.getElementById('exp_funciones').value = e.funciones_principales || '';
}

function guardarExperiencia() {
    const id = document.getElementById('exp_id').value;
    const payload = {
        empresa: document.getElementById('exp_empresa').value.trim(),
        cargo: document.getElementById('exp_cargo').value.trim(),
        sector_empresa: document.getElementById('exp_sector').value.trim(),
        fecha_inicio: document.getElementById('exp_inicio').value || null,
        fecha_fin: document.getElementById('exp_fin').value || null,
        jefe_inmediato: document.getElementById('exp_jefe').value.trim(),
        telefono_referencia: document.getElementById('exp_telefono').value.trim(),
        motivo_retiro: document.getElementById('exp_motivo').value,
        funciones_principales: document.getElementById('exp_funciones').value.trim()
    };

    if (!payload.empresa || !payload.cargo) {
        Swal.fire('Campos requeridos', 'Empresa y cargo son obligatorios.', 'warning');
        return;
    }

    const btn = document.getElementById('btnGuardarExperiencia');
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Guardando...';

    const url = id
        ? `/talento_humano/api/experiencia/${id}`
        : `/talento_humano/api/colaboradores/${colaboradorActualId}/experiencia`;

    fetch(url, {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = html;
            if (data.status === 'ok') {
                if (modalExperienciaUI) modalExperienciaUI.hide();
                cargarExperiencia();
                volverAlColaborador('tabExperiencia');
            } else {
                Swal.fire('Error', data.msg || 'No se pudo guardar la experiencia', 'error');
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = html;
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

function eliminarExperiencia(id) {
    const e = cacheExperiencia.find(x => Number(x.id) === Number(id));
    Swal.fire({
        title: '¿Eliminar experiencia?',
        text: e ? `${e.empresa} - ${e.cargo}` : '',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#97271C',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then(res => {
        if (!res.isConfirmed) return;
        fetch(`/talento_humano/api/experiencia/${id}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    cargarExperiencia();
                    Swal.fire('Eliminada', 'El registro fue eliminado', 'success');
                } else {
                    Swal.fire('Error', data.msg || 'No se pudo eliminar', 'error');
                }
            })
            .catch(() => Swal.fire('Error', 'Error de conexión', 'error'));
    });
}

// ============================================================
// FAMILIARES
// ============================================================
function cargarFamiliares() {
    const id = colaboradorActualId;
    if (!id) { cacheFamiliares = []; renderFamiliares(); return; }
    fetch(`/talento_humano/api/colaboradores/${id}/familiares`)
        .then(r => r.json())
        .then(data => {
            if (id !== colaboradorActualId) return;
            cacheFamiliares = data.familiares || [];
            renderFamiliares();
        })
        .catch(() => { cacheFamiliares = []; renderFamiliares(); });
}

function renderFamiliares() {
    const tb = document.getElementById('tbodyFamiliares');
    if (!tb) return;
    if (!cacheFamiliares.length) { filaVacia('tbodyFamiliares', 7); return; }

    tb.innerHTML = cacheFamiliares.map(f => {
        const doc = f.numero_documento
            ? `${esc(f.tipo_documento) || ''} ${esc(f.numero_documento)}`.trim()
            : '—';
        return `<tr>
            <td class="fw-semibold">${esc(f.nombre_completo)}</td>
            <td>${esc(f.tipo_familiar)}</td>
            <td>${doc}</td>
            <td>${fmtFecha(f.fecha_nacimiento)}</td>
            <td>${esc(f.telefono) || '—'}</td>
            <td>${f.dependiente_economico
                ? '<span class="badge bg-success-subtle text-dark">Sí</span>'
                : '<span class="badge bg-secondary-subtle text-dark">No</span>'}</td>
            <td class="text-end text-nowrap">
                <button type="button" class="btn btn-sm btn-outline-primary py-0 px-1 me-1" title="Editar"
                    onclick="editarFamiliar(${f.id})"><i class='bx bx-edit'></i></button>
                <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" title="Eliminar"
                    onclick="eliminarFamiliar(${f.id})"><i class='bx bx-trash'></i></button>
            </td>
        </tr>`;
    }).join('');
}

function abrirModalFamiliar() {
    if (!colaboradorActualId) {
        Swal.fire('Atención', 'Guarde primero el colaborador para registrar familiares.', 'info');
        return;
    }
    const el = document.getElementById('modalFamiliar');
    if (!modalFamiliarUI) modalFamiliarUI = new bootstrap.Modal(el);

    document.getElementById('fam_id').value = '';
    ['fam_tipo', 'fam_nombre', 'fam_tipo_doc', 'fam_num_doc', 'fam_nacimiento',
        'fam_telefono', 'fam_correo', 'fam_eps', 'fam_observaciones'].forEach(i => {
            const f = document.getElementById(i);
            if (f) f.value = '';
        });
    document.getElementById('fam_dependiente').checked = true;
    document.getElementById('fam_vive').checked = true;
    document.getElementById('fam_estudia').checked = false;

    if (modalColaboradorUI) modalColaboradorUI.hide();
    setTimeout(() => modalFamiliarUI.show(), 250);
}

function editarFamiliar(id) {
    const f = cacheFamiliares.find(x => Number(x.id) === Number(id));
    if (!f) return;
    abrirModalFamiliar();
    document.getElementById('fam_id').value = f.id;
    document.getElementById('fam_tipo').value = f.tipo_familiar || '';
    document.getElementById('fam_nombre').value = f.nombre_completo || '';
    document.getElementById('fam_tipo_doc').value = f.tipo_documento || '';
    document.getElementById('fam_num_doc').value = f.numero_documento || '';
    document.getElementById('fam_nacimiento').value = (f.fecha_nacimiento || '').substring(0, 10);
    document.getElementById('fam_telefono').value = f.telefono || '';
    document.getElementById('fam_correo').value = f.correo || '';
    document.getElementById('fam_eps').value = f.eps_familiar || '';
    document.getElementById('fam_dependiente').checked = !!f.dependiente_economico;
    document.getElementById('fam_vive').checked = !!f.vive_con_colaborador;
    document.getElementById('fam_estudia').checked = !!f.estudia;
    document.getElementById('fam_observaciones').value = f.observaciones || '';
}

function guardarFamiliar() {
    const id = document.getElementById('fam_id').value;
    const payload = {
        tipo_familiar: document.getElementById('fam_tipo').value,
        nombre_completo: document.getElementById('fam_nombre').value.trim(),
        tipo_documento: document.getElementById('fam_tipo_doc').value || null,
        numero_documento: document.getElementById('fam_num_doc').value.trim() || null,
        fecha_nacimiento: document.getElementById('fam_nacimiento').value || null,
        telefono: document.getElementById('fam_telefono').value.trim() || null,
        correo: document.getElementById('fam_correo').value.trim() || null,
        eps_familiar: document.getElementById('fam_eps').value.trim() || null,
        dependiente_economico: document.getElementById('fam_dependiente').checked,
        vive_con_colaborador: document.getElementById('fam_vive').checked,
        estudia: document.getElementById('fam_estudia').checked,
        observaciones: document.getElementById('fam_observaciones').value.trim() || null
    };

    if (!payload.tipo_familiar || !payload.nombre_completo) {
        Swal.fire('Campos requeridos', 'Parentesco y nombre completo son obligatorios.', 'warning');
        return;
    }

    const btn = document.getElementById('btnGuardarFamiliar');
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Guardando...';

    const url = id
        ? `/talento_humano/api/familiares/${id}`
        : `/talento_humano/api/colaboradores/${colaboradorActualId}/familiares`;

    fetch(url, {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = html;
            if (data.status === 'ok') {
                if (modalFamiliarUI) modalFamiliarUI.hide();
                cargarFamiliares();
                volverAlColaborador('tabFamiliares');
            } else {
                Swal.fire('Error', data.msg || 'No se pudo guardar el familiar', 'error');
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = html;
            Swal.fire('Error', 'Error de conexión', 'error');
        });
}

function eliminarFamiliar(id) {
    const f = cacheFamiliares.find(x => Number(x.id) === Number(id));
    Swal.fire({
        title: '¿Eliminar familiar?',
        text: f ? f.nombre_completo : '',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#97271C',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then(res => {
        if (!res.isConfirmed) return;
        fetch(`/talento_humano/api/familiares/${id}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    cargarFamiliares();
                    Swal.fire('Eliminado', 'El familiar fue eliminado', 'success');
                } else {
                    Swal.fire('Error', data.msg || 'No se pudo eliminar', 'error');
                }
            })
            .catch(() => Swal.fire('Error', 'Error de conexión', 'error'));
    });
}

// ============================================================
// DOCUMENTOS DEL COLABORADOR
// ============================================================
const DOCS_OBLIGATORIOS = [
    'Contrato', 'Hoja de Vida', 'Examenes Medicos', 'Certificado Laboral',
    'Curso Capacitacion', 'Carne Vacunacion', 'ARL', 'EPS', 'Fondo Pension',
    'Fondo Cesantias', 'Cuenta Bancaria', 'Licencia Conduccion', 'Pasaporte',
    'Antecedentes Penales'
];

let cacheDocumentos = [];
let docEditandoId = null;

function cargarDocumentos() {
    const id = colaboradorActualId;
    if (!id) {
        cacheDocumentos = [];
        renderDocumentos();
        renderChecklistDocumentos({});
        return;
    }
    fetch(`/talento_humano/api/colaboradores/${id}/documentos`)
        .then(r => r.json())
        .then(data => {
            if (id !== colaboradorActualId) return;
            cacheDocumentos = data.documentos || [];
            renderDocumentos();
            renderChecklistDocumentos((data.resumen && data.resumen.por_tipo) || {});
        })
        .catch(() => {
            cacheDocumentos = [];
            renderDocumentos();
            renderChecklistDocumentos({});
        });
}

function pesoLegible(bytes) {
    if (!bytes) return '\u2014';
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function badgeVencimiento(dias) {
    if (dias === null || dias === undefined) {
        return '<span class="badge bg-secondary-subtle text-secondary">Sin vencimiento</span>';
    }
    if (dias < 0) return `<span class="badge bg-danger">Vencido (${Math.abs(dias)}d)</span>`;
    if (dias <= 30) return `<span class="badge bg-warning text-dark">Vence en ${dias}d</span>`;
    return '<span class="badge bg-success-subtle text-success">Vigente</span>';
}

function renderDocumentos() {
    const tb = document.getElementById('tbodyDocumentos');
    if (!tb) return;
    if (!cacheDocumentos.length) {
        filaVacia('tbodyDocumentos', 6);
        return;
    }

    tb.innerHTML = cacheDocumentos.map(d => `
        <tr>
            <td class="fw-semibold">${esc(d.tipo_documento)}</td>
            <td>
                <div class="text-truncate" style="max-width:220px;" title="${esc(d.nombre_original)}">${esc(d.nombre_original)}</div>
                <small class="text-muted">${pesoLegible(d.tamano_bytes)}</small>
            </td>
            <td>${fmtFecha(d.fecha_documento)}</td>
            <td>${fmtFecha(d.fecha_vencimiento)}</td>
            <td>${badgeVencimiento(d.dias_restantes)}</td>
            <td class="text-end text-nowrap">
                <a class="btn btn-sm btn-outline-secondary" href="/talento_humano/api/documentos/${d.id}/archivo"
                   target="_blank" title="Ver"><i class='bx bx-show'></i></a>
                <a class="btn btn-sm btn-outline-secondary" href="/talento_humano/api/documentos/${d.id}/archivo?descargar=1"
                   title="Descargar"><i class='bx bx-download'></i></a>
                <button type="button" class="btn btn-sm btn-outline-primary" onclick="editarDocumento(${d.id})"
                        title="Editar"><i class='bx bx-edit'></i></button>
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarDocumento(${d.id})"
                        title="Eliminar"><i class='bx bx-trash'></i></button>
            </td>
        </tr>`).join('');
}

function renderChecklistDocumentos(porTipo) {
    const caja = document.getElementById('checklistDocumentos');
    if (!caja) return;

    const presentes = Object.keys(porTipo || {}).filter(k => (porTipo[k] || 0) > 0);
    caja.innerHTML = DOCS_OBLIGATORIOS.map(t => {
        const ok = presentes.includes(t);
        return `<span class="badge ${ok ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-light text-muted border'}">
            <i class='bx ${ok ? 'bx-check-circle' : 'bx-circle'} me-1'></i>${esc(t)}</span>`;
    }).join('');

    const total = DOCS_OBLIGATORIOS.filter(t => presentes.includes(t)).length;
    const pct = Math.round(total / DOCS_OBLIGATORIOS.length * 100);
    const txt = document.getElementById('docProgresoTexto');
    const barra = document.getElementById('docProgresoBarra');
    if (txt) txt.textContent = `${total} de ${DOCS_OBLIGATORIOS.length}`;
    if (barra) barra.style.width = pct + '%';
}

function validarArchivoDocumento(archivo) {
    const EXT = /\.(pdf|docx?|xlsx?|png|jpe?g|webp|gif|txt)$/i;
    if (!EXT.test(archivo.name) && archivo.type !== 'application/pdf') {
        Swal.fire('Formato no permitido', 'Use PDF, Word, Excel, imágenes o TXT.', 'warning');
        return false;
    }
    if (archivo.size > 10 * 1024 * 1024) {
        Swal.fire('Archivo muy grande', 'El tamaño máximo permitido es 10 MB.', 'warning');
        return false;
    }
    return true;
}

function abrirFormDocumento() {
    if (!colaboradorActualId) {
        Swal.fire('Guarde primero', 'Debe guardar el colaborador antes de adjuntar documentos.', 'info');
        return;
    }
    docEditandoId = null;
    document.getElementById('doc_tipo').value = '';
    document.getElementById('doc_fecha').value = '';
    document.getElementById('doc_vencimiento').value = '';
    document.getElementById('doc_observaciones').value = '';
    document.getElementById('doc_archivo').value = '';
    document.getElementById('cajaArchivoDocumento').classList.remove('d-none');
    document.getElementById('btnGuardarDocumento').innerHTML = "<i class='bx bx-save'></i> Guardar";
    document.getElementById('docAyudaTipo').textContent = 'PDF, Word, Excel, imágenes o TXT. Máximo 10 MB.';
    document.getElementById('cajaFormDocumento').classList.remove('d-none');
    document.getElementById('doc_tipo').focus();
}

function cerrarFormDocumento() {
    docEditandoId = null;
    document.getElementById('cajaFormDocumento').classList.add('d-none');
}

function editarDocumento(id) {
    const d = cacheDocumentos.find(x => x.id === id);
    if (!d) return;

    docEditandoId = id;
    document.getElementById('doc_tipo').value = d.tipo_documento || '';
    document.getElementById('doc_fecha').value = valorFechaInput(d.fecha_documento);
    document.getElementById('doc_vencimiento').value = valorFechaInput(d.fecha_vencimiento);
    document.getElementById('doc_observaciones').value = d.observaciones || '';
    document.getElementById('cajaArchivoDocumento').classList.add('d-none');
    document.getElementById('btnGuardarDocumento').innerHTML = "<i class='bx bx-check'></i> Actualizar";
    document.getElementById('docAyudaTipo').textContent =
        `Editando metadatos de "${d.nombre_original}". Para reemplazar el archivo, elimínelo y súbalo de nuevo.`;
    document.getElementById('cajaFormDocumento').classList.remove('d-none');
}

function guardarDocumento() {
    const tipo = document.getElementById('doc_tipo').value;
    const fecha = document.getElementById('doc_fecha').value;
    const vence = document.getElementById('doc_vencimiento').value;
    const obs = document.getElementById('doc_observaciones').value.trim();

    if (!tipo) {
        Swal.fire('Falta el tipo', 'Seleccione el tipo de documento.', 'warning');
        return;
    }

    // --- Edición de metadatos ---
    if (docEditandoId) {
        fetch(`/talento_humano/api/documentos/${docEditandoId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo_documento: tipo,
                fecha_documento: fecha,
                fecha_vencimiento: vence,
                observaciones: obs
            })
        })
            .then(r => r.json())
            .then(d => {
                if (d.status !== 'ok') throw new Error(d.msg || 'Error al actualizar');
                cerrarFormDocumento();
                cargarDocumentos();
                Swal.fire({ icon: 'success', title: 'Documento actualizado', timer: 1200, showConfirmButton: false });
            })
            .catch(e => Swal.fire('Error', e.message, 'error'));
        return;
    }

    // --- Subida ---
    const archivo = document.getElementById('doc_archivo').files[0];
    if (!archivo) {
        Swal.fire('Falta el archivo', 'Seleccione el archivo a subir.', 'warning');
        return;
    }
    if (!validarArchivoDocumento(archivo)) return;

    const fd = new FormData();
    fd.append('tipo_documento', tipo);
    fd.append('fecha_documento', fecha);
    fd.append('fecha_vencimiento', vence);
    fd.append('observaciones', obs);
    fd.append('archivo', archivo);

    const btn = document.getElementById('btnGuardarDocumento');
    const htmlOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = "<span class='spinner-border spinner-border-sm me-1'></span> Subiendo...";

    fetch(`/talento_humano/api/colaboradores/${colaboradorActualId}/documentos`, { method: 'POST', body: fd })
        .then(r => r.json())
        .then(d => {
            if (d.status !== 'ok') throw new Error(d.msg || 'Error al subir');
            cerrarFormDocumento();
            cargarDocumentos();
            Swal.fire({ icon: 'success', title: 'Documento subido', timer: 1200, showConfirmButton: false });
        })
        .catch(e => Swal.fire('Error', e.message, 'error'))
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = htmlOriginal;
        });
}

function eliminarDocumento(id) {
    const d = cacheDocumentos.find(x => x.id === id);
    Swal.fire({
        icon: 'warning',
        title: '¿Eliminar documento?',
        html: `Se eliminará <b>${esc(d ? d.nombre_original : 'el archivo')}</b> de forma permanente.`,
        showCancelButton: true,
        confirmButtonColor: '#97271C',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then(res => {
        if (!res.isConfirmed) return;
        fetch(`/talento_humano/api/documentos/${id}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(dt => {
                if (dt.status !== 'ok') throw new Error(dt.msg || 'Error al eliminar');
                cargarDocumentos();
                Swal.fire({ icon: 'success', title: 'Documento eliminado', timer: 1100, showConfirmButton: false });
            })
            .catch(e => Swal.fire('Error', e.message, 'error'));
    });
}
