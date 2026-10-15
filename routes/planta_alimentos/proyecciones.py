"""
Rutas para Proyecciones de Inventario y Costos
"""
from flask import Blueprint, render_template, jsonify, request, send_file
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido
from models.planta_alimentos.proyecciones import ProyeccionesModel

proyecciones_bp = Blueprint('proyecciones', __name__, url_prefix='/proyeccion')


@proyecciones_bp.route('/costos', methods=['GET'])
@login_requerido
def proyeccion_costos():
    """Vista principal: Proyección de Costos e Inventario"""
    return render_template('planta_alimentos/proyeccion.html')


@proyecciones_bp.route('/api/stock', methods=['GET'])
@login_requerido
def api_stock_proyeccion():
    """API: Datos completos de proyección para tabla principal"""
    try:
        dias = request.args.get('dias', 30, type=int)
        solo_alertas = request.args.get('alertas', 'false').lower() == 'true'
        
        if solo_alertas:
            data = ProyeccionesModel.get_alertas_resumen()
        else:
            data = ProyeccionesModel.calcular_proyecciones(dias_ventana=dias)
        
        return jsonify({
            'success': True,
            'data': data,
            'total': len(data) if isinstance(data, list) else data.get('total', 0)
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


@proyecciones_bp.route('/api/alertas', methods=['GET'])
@login_requerido
def api_alertas_proyeccion():
    """API: Solo alertas para badge/notificaciones"""
    try:
        data = ProyeccionesModel.get_alertas_resumen()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


@proyecciones_bp.route('/costos/exportar', methods=['GET'])
@login_requerido
def exportar_proyeccion_excel():
    """Exportar proyección a Excel"""
    try:
        output = ProyeccionesModel.exportar_excel()
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='proyeccion_inventario.xlsx'
        )
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


# Registrar blueprint en planta_bp
from routes.planta_alimentos.catalogo_a import planta_bp
planta_bp.register_blueprint(proyecciones_bp)