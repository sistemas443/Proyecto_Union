from flask import request, jsonify
from routes.clasificacion.vistas import clasificacion_bp
from routes.routes import login_requerido, editor_requerido, superadmin_requerido
from models.clasificacion.services import update_clasificacion_field, recalcular_lote_completo_clasificacion
from models.cabecera.services import get_cabecera_info


@clasificacion_bp.route('/api/clasificacion/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_clasificacion():
    data = request.get_json(silent=True) or {}
    id_reg, columna, valor = data.get('id'), data.get('columna', '').strip(), data.get('valor', '')
    if not id_reg or not columna:
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
    try:
        ok = update_clasificacion_field(int(id_reg), columna, valor)
        return jsonify({'status': 'ok'}) if ok else jsonify({'status': 'error', 'msg': 'Error de integridad SQL'}), 400
    except Exception as e:
        print(f"[ERROR CRÍTICO EN API CLASIFICACIÓN]: {e}")
        return jsonify({'status': 'error', 'msg': 'Error interno de red.'}), 500


@clasificacion_bp.route('/api/clasificacion/recalcular', methods=['POST'])
@login_requerido
@superadmin_requerido
def recalcular_clas_lote():
    data = request.get_json(silent=True) or {}
    lote = data.get('lote')

    cabecera = get_cabecera_info(lote)
    if not cabecera:
        return jsonify({'status': 'error', 'msg': 'Lote no encontrado'}), 404

    exito = recalcular_lote_completo_clasificacion(cabecera['id'])
    if exito:
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'msg': 'Error en el servidor al recalcular'}), 500