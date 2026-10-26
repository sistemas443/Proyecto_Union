// static/js/talento_humano/documentos.js
// Página global: Documentos por Colaborador

let DOCS = [];
let modalSubirUI = null;
let modalEditarUI = null;

function initDocumentosPagina() {
    try {
        DOCS = JSON.parse(document.getElementById('datosDocumentos').textContent || '[]');
    } catch (e) {
        DOCS = [];
    }

    if (window.bootstrap) {
        modalSubirUI = new bootstrap.Modal(document.getElementById('modalSubirDocumento'));
        modalEditarUI = new bootstrap.Modal(document.getElementById('modalEditarDocumento'));
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDocumentosPagina);
} else {
    initDocumentosPagina();
}

function esc(v) {
    if (v === null || v === undefined) return '';
    return String(v)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ============================================================
// SUBIR
// ============================================================
function abrirModalSubir() {
    document.getElementById('subir_tipo').value = '';
    document.getElementById('subir_archivo').value = '';
    document.getElementById('subir_fecha').value = '';
    document.getElementById('subir_vencimiento').value = '';
    document.getElementById('subir_observaciones').value = '';

    // Preseleccionar el colaborador del filtro activo
    const filtro = document.querySelector('select[name="colaborador_id"]');
    const select = document.getElementById('subir_colaborador');
    select.value = (filtro && filtro.value) ? filtro.value : '';

    if (modalSubirUI) modalSubirUI.show();
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

function subirDocumento() {
    const colaboradorId = document.getElementById('subir_colaborador').value;
    const tipo = document.getElementById('subir_tipo').value;
    const archivo = document.getElementById('subir_archivo').files[0];

    if (!colaboradorId) {
        Swal.fire('Falta el colaborador', 'Seleccione el colaborador al que pertenece el documento.', 'warning');
        return;
    }
    if (!tipo) {
        Swal.fire('Falta el tipo', 'Seleccione el tipo de documento.', 'warning');
        return;
    }
    if (!archivo) {
        Swal.fire('Falta el archivo', 'Seleccione el archivo a subir.', 'warning');
        return;
    }
    if (!validarArchivoDocumento(archivo)) return;

    const fd = new FormData();
    fd.append('tipo_documento', tipo);
    fd.append('fecha_documento', document.getElementById('subir_fecha').value);
    fd.append('fecha_vencimiento', document.getElementById('subir_vencimiento').value);
    fd.append('observaciones', document.getElementById('subir_observaciones').value.trim());
    fd.append('archivo', archivo);

    const btn = document.getElementById('btnSubirDocumento');
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = "<span class='spinner-border spinner-border-sm me-1'></span> Subiendo...";

    fetch(`/talento_humano/api/colaboradores/${colaboradorId}/documentos`, { method: 'POST', body: fd })
        .then(r => r.json())
        .then(d => {
            if (d.status !== 'ok') throw new Error(d.msg || 'Error al subir el documento');
            if (modalSubirUI) modalSubirUI.hide();
            Swal.fire({
                icon: 'success',
                title: 'Documento subido',
                timer: 1100,
                showConfirmButton: false
            }).then(() => location.reload());
        })
        .catch(e => Swal.fire('Error', e.message, 'error'))
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = html;
        });
}

// ============================================================
// EDITAR
// ============================================================
function abrirModalEditar(id) {
    const d = DOCS.find(x => Number(x.id) === Number(id));
    if (!d) {
        Swal.fire('No encontrado', 'No se pudo cargar la información del documento.', 'error');
        return;
    }

    document.getElementById('edit_id').value = d.id;
    document.getElementById('edit_archivo').textContent = d.nombre_original || '—';
    document.getElementById('edit_tipo').value = d.tipo_documento || '';
    document.getElementById('edit_fecha').value = (d.fecha_documento || '').substring(0, 10);
    document.getElementById('edit_vencimiento').value = (d.fecha_vencimiento || '').substring(0, 10);
    document.getElementById('edit_observaciones').value = d.observaciones || '';

    if (modalEditarUI) modalEditarUI.show();
}

function guardarEdicionDocumento() {
    const id = document.getElementById('edit_id').value;
    const tipo = document.getElementById('edit_tipo').value;

    if (!tipo) {
        Swal.fire('Falta el tipo', 'Seleccione el tipo de documento.', 'warning');
        return;
    }

    const btn = document.getElementById('btnGuardarDocumento');
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = "<span class='spinner-border spinner-border-sm me-1'></span> Guardando...";

    fetch(`/talento_humano/api/documentos/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            tipo_documento: tipo,
            fecha_documento: document.getElementById('edit_fecha').value,
            fecha_vencimiento: document.getElementById('edit_vencimiento').value,
            observaciones: document.getElementById('edit_observaciones').value.trim()
        })
    })
        .then(r => r.json())
        .then(d => {
            if (d.status !== 'ok') throw new Error(d.msg || 'Error al actualizar');
            if (modalEditarUI) modalEditarUI.hide();
            Swal.fire({
                icon: 'success',
                title: 'Documento actualizado',
                timer: 1000,
                showConfirmButton: false
            }).then(() => location.reload());
        })
        .catch(e => Swal.fire('Error', e.message, 'error'))
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = html;
        });
}

// ============================================================
// ELIMINAR
// ============================================================
function eliminarDocumento(id) {
    const d = DOCS.find(x => Number(x.id) === Number(id));

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
                Swal.fire({
                    icon: 'success',
                    title: 'Documento eliminado',
                    timer: 1000,
                    showConfirmButton: false
                }).then(() => location.reload());
            })
            .catch(e => Swal.fire('Error', e.message, 'error'));
    });
}
