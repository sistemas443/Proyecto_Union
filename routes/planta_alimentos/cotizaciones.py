"""
Rutas para Cotizaciones de Productos
"""
from flask import Blueprint, render_template, jsonify, request, send_file, redirect, url_for, flash, session
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido
from models.planta_alimentos.cotizaciones import CotizacionesModel

cotizaciones_bp = Blueprint('cotizaciones', __name__, url_prefix='/cotizaciones')


@cotizaciones_bp.route('/', methods=['GET'])
@login_requerido
def cotizaciones_list():
    """Vista principal: Lista de cotizaciones por mes/año"""
    cotizaciones = CotizacionesModel.get_cotizaciones_list()
    return render_template('planta_alimentos/cotizaciones.html', cotizaciones=cotizaciones)


@cotizaciones_bp.route('/nueva', methods=['GET', 'POST'])
@login_requerido
def cotizacion_nueva():
    """Crear o editar cotización para un mes/año"""
    if request.method == 'POST':
        mes = int(request.form.get('mes'))
        anio = int(request.form.get('anio'))
        
        try:
            cotizacion_id = CotizacionesModel.crear_o_actualizar_cotizacion(mes, anio, session.get('user_id'))
            return redirect(url_for('planta_alimentos.cotizaciones.cotizacion_detalle', cotizacion_id=cotizacion_id))
        except Exception as e:
            flash(f'Error al crear cotización: {str(e)}', 'danger')
    
    # GET: mostrar formulario para crear nueva
    return render_template('planta_alimentos/cotizaciones_form.html')


@cotizaciones_bp.route('/<int:cotizacion_id>', methods=['GET'])
@login_requerido
def cotizacion_detalle(cotizacion_id):
    """Vista para editar cotización (grid editable tipo Excel)"""
    data = CotizacionesModel.get_detalle_cotizacion(cotizacion_id)
    if not data:
        flash('Cotización no encontrada', 'danger')
        return redirect(url_for('planta_alimentos.cotizaciones.cotizaciones_list'))
    
    # Obtener mes/año para el título
    cotizacion = data['cotizacion']
    mes_nombres = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    mes_nombre = mes_nombres[cotizacion['mes']] if cotizacion['mes'] else ''
    
    return render_template('planta_alimentos/cotizaciones_detalle.html',
                           data=data,
                           mes_nombre=mes_nombre,
                           mes_nombres=mes_nombres,
                           cotizacion=cotizacion)


@cotizaciones_bp.route('/api/guardar', methods=['POST'])
@login_requerido
def api_guardar_cotizacion():
    """API: Guardar múltiples celdas de cotización (AJAX)"""
    try:
        data = request.get_json()
        cotizacion_id = data.get('cotizacion_id')
        items = data.get('items', [])
        
        print(f'[DEBUG COTIZACIONES] Recibido: cotizacion_id={cotizacion_id}, items={items}')
        
        if not cotizacion_id or not items:
            return jsonify({'success': False, 'msg': 'Datos incompletos'}), 400
        
        CotizacionesModel.guardar_detalle_masivo(cotizacion_id, items, session.get('user_id'))
        return jsonify({'success': True, 'msg': 'Guardado correctamente'})
    except Exception as e:
        print(f'[ERROR COTIZACIONES] {e}')
        return jsonify({'success': False, 'msg': str(e)}), 500


@cotizaciones_bp.route('/api/productos', methods=['GET'])
@login_requerido
def api_productos():
    """API: Lista de productos (materias primas)"""
    productos = CotizacionesModel.get_productos_activos()
    return jsonify({'success': True, 'data': productos})


@cotizaciones_bp.route('/api/proveedores', methods=['GET'])
@login_requerido
def api_proveedores():
    """API: Lista de proveedores activos"""
    proveedores = CotizacionesModel.get_proveedores_activos()
    return jsonify({'success': True, 'data': proveedores})


@cotizaciones_bp.route('/api/mejor-precio-historico', methods=['GET'])
@login_requerido
def api_mejor_precio_historico():
    """API: Mejor precio histórico consolidado por producto (todas las cotizaciones)"""
    try:
        mejor_precios = CotizacionesModel.get_mejor_precio_historico()
        return jsonify({'success': True, 'data': mejor_precios})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


@cotizaciones_bp.route('/exportar/<int:mes>/<int:anio>', methods=['GET'])
@login_requerido
def exportar_cotizacion(mes, anio):
    """Exportar cotización a Excel"""
    try:
        output = CotizacionesModel.exportar_excel(mes, anio)
        if output is None:
            flash('No hay cotización para ese mes/año', 'warning')
            return redirect(url_for('planta_alimentos.cotizaciones.cotizaciones_list'))
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'cotizacion_{mes}_{anio}.xlsx'
        )
    except Exception as e:
        flash(f'Error al exportar: {str(e)}', 'danger')
        return redirect(url_for('planta_alimentos.cotizaciones.cotizaciones_list'))


# Registrar blueprint en planta_bp
from routes.planta_alimentos.catalogo_a import planta_bp
planta_bp.register_blueprint(cotizaciones_bp)