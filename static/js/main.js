/**
 * main.js
 * Funciones JavaScript para la aplicación Avícola San Martín
 * Manejo de AJAX, validación de datos y feedback visual
 */

// ==================== CONFIGURACIÓN ====================

const CONFIG = {
    apiBaseUrl: '/api',
    saveDelay: 1000, // ms para mostrar feedback de guardado
    debug: true
};

const tsInstances = {}; // Memoria temporal para los selects inteligentes (Tom Select)

// ==================== FUNCIONES GENERALES ====================

function log(message, type = 'info') {
    if (CONFIG.debug) {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container-fluid');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        setTimeout(() => alertDiv.remove(), 5000);
    }
}

// ==================== INICIALIZACIÓN ====================

document.addEventListener('DOMContentLoaded', function() {
    log('Inicializando aplicación');
    
    setupSelectsInteligentes();
    setupBotonesLotes(); // <- Configuramos la delegación de eventos del Modal aquí
    setupPersistenciaLote(); // <- Persistencia del lote seleccionado entre páginas
    
    log('Aplicación lista');
});

// ==================== PERSISTENCIA DEL LOTE SELECCIONADO ====================

/**
 * Guarda el lote en sessionStorage cuando el usuario hace submit,
 * y lo restaura automáticamente al entrar a cualquier página con selector de lote.
 * Si el servidor ya devolvió un lote_seleccionado (POST previo), ese tiene prioridad.
 */
function setupPersistenciaLote() {
    const selectLote = document.getElementById('lote');
    if (!selectLote) return; // Esta página no tiene selector de lote

    const STORAGE_KEY = 'lote_seleccionado';

    // Si el select ya tiene un valor (el servidor lo puso por POST), guardarlo y no hacer nada más
    if (selectLote.value) {
        sessionStorage.setItem(STORAGE_KEY, selectLote.value);
        log(`Lote guardado en sesión: ${selectLote.value}`);
        return;
    }

    // Si el select está vacío, intentar restaurar desde sessionStorage
    const loteGuardado = sessionStorage.getItem(STORAGE_KEY);
    if (loteGuardado) {
        // Verificar que la opción existe en el select actual
        const opcionExiste = Array.from(selectLote.options).some(opt => opt.value === loteGuardado);
        if (opcionExiste) {
            log(`Restaurando lote desde sesión: ${loteGuardado}`);
            selectLote.value = loteGuardado;
            // Enviar el formulario automáticamente para cargar los datos del lote
            const form = selectLote.closest('form');
            if (form) {
                form.submit();
            }
        } else {
            // El lote guardado ya no existe, limpiar
            sessionStorage.removeItem(STORAGE_KEY);
        }
    }

    // Guardar en sessionStorage cada vez que el usuario cambie la selección y haga submit
    const form = selectLote.closest('form');
    if (form) {
        form.addEventListener('submit', function() {
            if (selectLote.value) {
                sessionStorage.setItem(STORAGE_KEY, selectLote.value);
                log(`Lote guardado al submit: ${selectLote.value}`);
            } else {
                sessionStorage.removeItem(STORAGE_KEY);
            }
        });
    }
}

function setupSelectsInteligentes() {
    document.querySelectorAll('.creatable-select').forEach((el) => {
        tsInstances[el.id] = new TomSelect(el, {
            create: true,
            sortField: { field: "text", direction: "asc" },
            placeholder: "Seleccione o escriba..."
        });
    });
}

function setSelectValue(id, value) {
    if (tsInstances[id]) {
        if (value) {
            tsInstances[id].addOption({value: value, text: value});
        }
        tsInstances[id].setValue(value || '');
    } else {
        const el = document.getElementById(id);
        if (el) el.value = value || '';
    }
}

// ==================== CONTROL DEL MODAL (Lotes) ====================

// Convierte cualquier fecha loca de base de datos a formato estricto HTML (YYYY-MM-DD)
function formatFechaParaInput(fechaStr) {
    if (!fechaStr) return '';
    if (fechaStr.length === 10 && fechaStr.includes('-')) return fechaStr;
    try {
        const d = new Date(fechaStr);
        if (isNaN(d.getTime())) return '';
        return d.toISOString().split('T')[0];
    } catch(e) {
        return '';
    }
}

// Llenado Maestro de datos en el Modal
function llenarFormularioLote(lote) {
    document.getElementById('lote_id').value = lote.id || '';
    
    // Inputs Normales Numéricos y de Texto
    document.getElementById('f_lote').value = lote.lote || '';
    document.getElementById('f_pollitas').value = lote.no_pollitas_recibidas || '';
    document.getElementById('f_peso').value = lote.peso || '';
    document.getElementById('f_unidad_peso').value = lote.unidad_peso || ''; 
    document.getElementById('f_uniformidad').value = lote.uniformidad || '';
    document.getElementById('f_coef').value = lote.coeficiente_variacion || '';
    document.getElementById('f_aves_enc').value = lote.no_aves_encasetadas || '';
    document.getElementById('f_unidad_med').value = lote.unidad_medida || '';

    // Fechas Formateadas
    document.getElementById('f_fecha_rec').value = formatFechaParaInput(lote.fecha_recepcion);
    document.getElementById('f_fecha_enc').value = formatFechaParaInput(lote.fecha_encasetamiento);

    // Selects Inteligentes
    setSelectValue('f_cliente', lote.cliente);
    setSelectValue('f_ciudad', lote.ciudad);
    setSelectValue('f_clima', lote.clima);
    setSelectValue('f_responsable', lote.responsable_tecnico);
    setSelectValue('f_nutricionista', lote.nutricionista);
    setSelectValue('f_granja_lev', lote.granja_lev);
    setSelectValue('f_variedad', lote.variedad);
    setSelectValue('f_granja_prod', lote.granja_prod);
    setSelectValue('f_tipo_galpon', lote.tipo_galpon);
    setSelectValue('f_marca_galpon', lote.marca_galpon);
}

// Botón "Nuevo Lote" (Limpiar modal)
function configurarModal(accion) {
    const formLote = document.getElementById('formLote');
    formLote.reset();
    document.getElementById('lote_id').value = '';
    document.getElementById('modalLoteLabel').innerText = 'Nuevo Lote';
    document.getElementById('btnGuardar').style.display = 'block';

    Object.values(tsInstances).forEach(ts => { ts.clear(); ts.enable(); });

    const inputs = formLote.querySelectorAll('input:not(.tomselected)');
    inputs.forEach(input => { input.readOnly = false; input.disabled = false; });
}

function confirmarBorrar(id) {
    if (confirm("¿Estás seguro de que deseas borrar este lote? Esta acción no se puede deshacer.")) {
        fetch('/api/borrar-lote/' + id, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if(data.status === 'ok') location.reload();
            else alert('Error al borrar: ' + data.msg);
        })
        .catch(err => alert("Error de red al intentar borrar el lote."));
    }
}

// Delegación de eventos para Ojo, Lápiz y Basura (Previene atascos en Bootstrap)
function setupBotonesLotes() {
    document.body.addEventListener('click', function(e) {
        
        // BOTÓN OJO (Ver Detalles - Solo Lectura)
        let btnVer = e.target.closest('.btn-ver');
        if (btnVer) {
            e.preventDefault();
            const lote = JSON.parse(btnVer.getAttribute('data-lote'));
            llenarFormularioLote(lote);
            
            document.getElementById('modalLoteLabel').innerText = 'Detalles del Lote';
            document.getElementById('btnGuardar').style.display = 'none';

            Object.values(tsInstances).forEach(ts => ts.disable());

            const formLote = document.getElementById('formLote');
            const inputs = formLote.querySelectorAll('input:not(.tomselected)');
            inputs.forEach(input => { input.readOnly = true; });

            const myModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalLote'));
            myModal.show();
            return;
        }

        // BOTÓN LÁPIZ (Editar Lote)
        let btnEditar = e.target.closest('.btn-editar');
        if (btnEditar) {
            e.preventDefault();
            const lote = JSON.parse(btnEditar.getAttribute('data-lote'));
            llenarFormularioLote(lote);
            
            document.getElementById('modalLoteLabel').innerText = 'Editar Lote';
            document.getElementById('btnGuardar').style.display = 'block';

            Object.values(tsInstances).forEach(ts => ts.enable());

            const formLote = document.getElementById('formLote');
            const inputs = formLote.querySelectorAll('input:not(.tomselected)');
            inputs.forEach(input => { input.readOnly = false; input.disabled = false; });

            // Bloquear el ID del lote para que no rompan la BD
            document.getElementById('f_lote').readOnly = true;

            const myModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalLote'));
            myModal.show();
            return;
        }

        // BOTÓN BASURA (Borrar)
        let btnBorrar = e.target.closest('.btn-borrar');
        if (btnBorrar) {
            e.preventDefault();
            const id = btnBorrar.getAttribute('data-id');
            confirmarBorrar(id);
        }
    });
}