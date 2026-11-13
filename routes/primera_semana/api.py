from flask import request, jsonify, session
from routes.primera_semana.vistas import primera_semana_bp
from routes.routes import login_requerido, editor_requerido
from models.base import traducir_error
from models.primera_semana.services import update_primera_semana_field
from models.primera_semana.activa import set_tabla_activa
from models.primera_semana.dia2_services import (
    generar_estructura_dia2,
    get_dia2_by_lote,
    update_dia2_field,
    actualizar_fecha_inicio_dia2,
    eliminar_dia2 as eliminar_dia2_servicio,
    roles_pueden_dia2,
)


@primera_semana_bp.route('/api/primera-semana/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_primera_semana():
    # End-point receptor de guardados asíncronos para la tabla de primera semana
    data = request.get_json(silent=True) or {}
    id_reg = data.get('id')
    columna = data.get('columna', '').strip()
    valor = data.get('valor', '')
    if not id_reg or not columna:
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
    try:
        success, campos_actualizados, msg = update_primera_semana_field(
            int(id_reg), columna, valor,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido')
        )
        if success:
            return jsonify({'status': 'ok', 'updated_data': campos_actualizados})
        else:
            from models.auditoria.services import registrar_error
            registrar_error(
                tabla='primera_semana',
                contexto='Guardar dato en línea',
                mensaje=f'{columna}: {msg}',
                id_fila=id_reg,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido'),
            )
            return jsonify({'status': 'error', 'msg': traducir_error(msg)}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO EN API PRIMERA SEMANA]: {e}")
        from models.auditoria.services import registrar_error
        registrar_error(
            tabla='primera_semana',
            contexto='Guardar dato en línea',
            mensaje=f'{columna}: {type(e).__name__}: {e}',
            id_fila=id_reg,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        return jsonify({'status': 'error', 'msg': 'Error interno al procesar los datos. Contacte a soporte.'}), 500


# ==================== TABLA ACTIVA ====================

@primera_semana_bp.route('/api/primera-semana/activa', methods=['POST'])
@login_requerido
@editor_requerido
def seleccionar_tabla_activa():
    """Guarda si el sistema debe usar el Día 1 o el Día 2 para el lote."""
    data = request.get_json(silent=True) or {}
    lote = (data.get('lote') or '').strip()
    tabla = (data.get('tabla') or '').strip()
    if not lote or tabla not in ('dia1', 'dia2'):
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos.'}), 400

    ok, msg = set_tabla_activa(
        lote, tabla,
        usuario_id=session.get('user_id'),
        usuario_nombre=session.get('user_nombre', 'Desconocido'),
    )
    if ok:
        return jsonify({'status': 'ok', 'msg': msg, 'tabla': tabla})
    return jsonify({'status': 'error', 'msg': traducir_error(msg)}), 400


# ==================== DÍA 2 (TABLA INDEPENDIENTE) ====================

@primera_semana_bp.route('/api/primera-semana/dia2/generar', methods=['POST'])
@login_requerido
@editor_requerido
def generar_dia2():
    """Crea la tabla visual del Día 2 para el lote indicado."""
    if not roles_pueden_dia2(session.get('user_rol')):
        return jsonify({
            'status': 'error',
            'msg': 'No tienes permisos para generar la tabla del Día 2.',
        }), 403

    data = request.get_json(silent=True) or {}
    lote = (data.get('lote') or '').strip()
    if not lote:
        return jsonify({'status': 'error', 'msg': 'Debes indicar el lote.'}), 400

    try:
        ok, msg = generar_estructura_dia2(
            lote,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        if ok:
            return jsonify({'status': 'ok', 'msg': msg})
        return jsonify({'status': 'error', 'msg': traducir_error(msg)}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO GENERAR DÍA 2]: {e}")
        from models.auditoria.services import registrar_error
        registrar_error(
            tabla='primera_semana_dia2',
            contexto='Generar tabla Día 2',
            mensaje=f'{type(e).__name__}: {e}',
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        return jsonify({
            'status': 'error',
            'msg': 'Error interno al generar la tabla del Día 2.',
        }), 500


@primera_semana_bp.route('/api/primera-semana/dia2/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_dia2():
    """Guarda una edición en línea de la tabla del Día 2."""
    data = request.get_json(silent=True) or {}
    id_reg = data.get('id')
    columna = (data.get('columna') or '').strip()
    valor = data.get('valor', '')
    if not id_reg or not columna:
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400

    try:
        success, campos_actualizados, msg = update_dia2_field(
            int(id_reg), columna, valor,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        if success:
            lote_actualizado = campos_actualizados.pop('_lote', '')
            filas = get_dia2_by_lote(lote_actualizado) if lote_actualizado else []
            return jsonify({
                'status': 'ok',
                'updated_data': campos_actualizados,
                'filas': filas,
            })

        from models.auditoria.services import registrar_error
        registrar_error(
            tabla='primera_semana_dia2',
            contexto='Guardar dato en línea Día 2',
            mensaje=f'{columna}: {msg}',
            id_fila=id_reg,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        return jsonify({'status': 'error', 'msg': traducir_error(msg)}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO EN API DÍA 2]: {e}")
        from models.auditoria.services import registrar_error
        registrar_error(
            tabla='primera_semana_dia2',
            contexto='Guardar dato en línea Día 2',
            mensaje=f'{columna}: {type(e).__name__}: {e}',
            id_fila=id_reg,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        return jsonify({
            'status': 'error',
            'msg': 'Error interno al procesar los datos. Contacte a soporte.',
        }), 500


@primera_semana_bp.route('/api/primera-semana/dia2/fecha', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_fecha_dia2():
    """Cambia la fecha del Día 0 y desplaza toda la columna del Día 2."""
    data = request.get_json(silent=True) or {}
    lote = (data.get('lote') or '').strip()
    fecha = (data.get('fecha') or '').strip()
    if not lote or not fecha:
        return jsonify({'status': 'error', 'msg': 'Lote y fecha son obligatorios.'}), 400

    try:
        ok, msg = actualizar_fecha_inicio_dia2(
            lote, fecha,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        if ok:
            return jsonify({
                'status': 'ok',
                'msg': msg,
                'filas': get_dia2_by_lote(lote),
            })
        return jsonify({'status': 'error', 'msg': traducir_error(msg)}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO FECHA DÍA 2]: {e}")
        from models.auditoria.services import registrar_error
        registrar_error(
            tabla='primera_semana_dia2',
            contexto='Actualizar fecha Día 2',
            mensaje=f'{type(e).__name__}: {e}',
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        return jsonify({
            'status': 'error',
            'msg': 'Error interno al actualizar la fecha del Día 2.',
        }), 500


@primera_semana_bp.route('/api/primera-semana/dia2/eliminar', methods=['POST'])
@login_requerido
@editor_requerido
def eliminar_dia2():
    """Elimina la tabla del Día 2 de un lote."""
    if not roles_pueden_dia2(session.get('user_rol')):
        return jsonify({
            'status': 'error',
            'msg': 'No tienes permisos para eliminar la tabla del Día 2.',
        }), 403

    data = request.get_json(silent=True) or {}
    lote = (data.get('lote') or '').strip()
    if not lote:
        return jsonify({'status': 'error', 'msg': 'Debes indicar el lote.'}), 400

    try:
        ok, msg = eliminar_dia2_servicio(lote)
        if ok:
            return jsonify({'status': 'ok', 'msg': msg})
        return jsonify({'status': 'error', 'msg': traducir_error(msg)}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO ELIMINAR DÍA 2]: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Error interno al eliminar la tabla del Día 2.',
        }), 500
