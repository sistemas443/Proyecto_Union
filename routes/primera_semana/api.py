from flask import request, jsonify
from routes.primera_semana.vistas import primera_semana_bp
from routes.routes import login_requerido, editor_requerido
from models.primera_semana.services import update_primera_semana_field


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
        success, campos_actualizados, msg = update_primera_semana_field(int(id_reg), columna, valor)
        if success:
            return jsonify({'status': 'ok', 'updated_data': campos_actualizados})
        else:
            return jsonify({'status': 'error', 'msg': msg}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO EN API PRIMERA SEMANA]: {e}")
        return jsonify({'status': 'error', 'msg': 'Error interno al procesar los datos. Contacte a soporte.'}), 500