from flask import request, jsonify, session
from routes.diario.vistas import diario_bp
from routes.routes import login_requerido, editor_requerido
from models.diario.services import update_registro_diario_field


@diario_bp.route('/api/diario/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_diario():
    data = request.get_json(silent=True) or {}
    id_reg = data.get('id')
    columna = data.get('columna', '').strip()
    valor = data.get('valor', '')
    if not id_reg or not columna:
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
    try:
        resultado = update_registro_diario_field(int(id_reg), columna, valor)
        if isinstance(resultado, tuple) and len(resultado) == 3:
            success, campos_on_time, msg = resultado
        elif isinstance(resultado, tuple) and len(resultado) == 2:
            success, campos_on_time = resultado
            msg = "El dato fue rechazado por la base de datos."
        else:
            success = resultado
            campos_on_time = {}
            msg = "Error desconocido al procesar el guardado."

        if success:
            return jsonify({'status': 'ok', 'updated_data': campos_on_time})
        else:
            from models.auditoria.services import registrar_error
            registrar_error(
                tabla='data_diario',
                contexto='Guardar dato en línea',
                mensaje=f'{columna}: {msg}',
                id_fila=id_reg,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido'),
            )
            return jsonify({'status': 'error', 'msg': msg}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO EN API DIARIO]: {e}")
        from models.auditoria.services import registrar_error
        registrar_error(
            tabla='data_diario',
            contexto='Guardar dato en línea',
            mensaje=f'{columna}: {type(e).__name__}: {e}',
            id_fila=id_reg,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
        )
        return jsonify({'status': 'error', 'msg': 'Error interno en conexión.'}), 500