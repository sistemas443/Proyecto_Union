from flask import request, jsonify
from routes.semanal.vistas import semanal_bp
from routes.routes import login_requerido, editor_requerido
from models.semanal.services import update_semanal_field as update_produccion_field
from models.semanal_levante.services import update_semanal_field as update_levante_field


@semanal_bp.route('/api/semanal/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_semanal():
    # End-point compartido. Usa una bandera ('pantalla') en el JSON para desviar el dato al servicio correspondiente
    data = request.get_json(silent=True) or {}
    id_reg, columna, valor = data.get('id'), data.get('columna', '').strip(), data.get('valor', '')
    pantalla = data.get('pantalla', 'produccion')

    if not id_reg or not columna:
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
    try:
        if pantalla == 'levante':
            ok, campos_actualizados, msg = update_levante_field(int(id_reg), columna, valor)
        else:
            ok, campos_actualizados, msg = update_produccion_field(int(id_reg), columna, valor)

        if ok:
            return jsonify({'status': 'ok', 'updated_data': campos_actualizados})
        else:
            return jsonify({'status': 'error', 'msg': f"Rechazado por Base de Datos: {msg}"}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO EN API SEMANAL]: {e}")
        return jsonify({'status': 'error', 'msg': 'Error interno en conexión.'}), 500