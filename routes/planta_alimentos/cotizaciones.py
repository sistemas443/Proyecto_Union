"""
Rutas para Cotizaciones de Productos
"""
from datetime import datetime

from flask import Blueprint, render_template, jsonify, request, send_file, redirect, url_for, flash, session
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido
from models.planta_alimentos.cotizaciones import CotizacionesModel

cotizaciones_bp = Blueprint('cotizaciones', __name__, url_prefix='/cotizaciones')


@cotizaciones_bp.route('/', methods=['GET'])
@login_requerido
def cotizaciones_list():
    """Vista principal: Lista de cotizaciones por mes/año"""
    anio = request.args.get('anio', type=int)
    estado = request.args.get('estado') or None

    cotizaciones = CotizacionesModel.get_cotizaciones_list(anio=anio, estado=estado)
    return render_template(
        'planta_alimentos/cotizaciones.html',
        cotizaciones=cotizaciones,
        anios=CotizacionesModel.get_anios_registrados(),
        filtro_anio=anio,
        filtro_estado=estado
    )


def _contexto_formulario():
    """Datos que necesita el formulario de nueva cotización"""
    existentes = CotizacionesModel.get_cotizaciones_list()
    return {
        'existentes': [{'mes': c['mes'], 'anio': c['anio'], 'estado': c['estado']} for c in existentes],
        'anio_actual': datetime.now().year,
    }


@cotizaciones_bp.route('/nueva', methods=['GET', 'POST'])
@login_requerido
def cotizacion_nueva():
    """Crear o editar cotización para un mes/año"""
    contexto = _contexto_formulario()

    if request.method == 'POST':
        try:
            mes = int(request.form.get('mes'))
            anio = int(request.form.get('anio'))
            if not 1 <= mes <= 12 or anio < 2020:
                raise ValueError('Mes o año fuera de rango')
        except (TypeError, ValueError):
            flash('Selecciona un mes y un año válidos.', 'danger')
            return render_template('planta_alimentos/cotizaciones_form.html', **contexto)

        try:
            existente = next(
                (e for e in contexto['existentes'] if e['mes'] == mes and e['anio'] == anio),
                None
            )
            cotizacion_id = CotizacionesModel.crear_o_actualizar_cotizacion(mes, anio, session.get('user_id'))
            if existente:
                flash('Ya existía una cotización para ese mes/año: se abrió para editarla.', 'warning')
            else:
                flash('Cotización creada correctamente.', 'success')
            return redirect(url_for('planta_alimentos.cotizaciones.cotizacion_detalle', cotizacion_id=cotizacion_id))
        except Exception as e:
            flash(f'Error al crear cotización: {str(e)}', 'danger')

    # GET: mostrar formulario para crear nueva
    return render_template('planta_alimentos/cotizaciones_form.html', **contexto)


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
        data = request.get_json() or {}
        cotizacion_id = data.get('cotizacion_id')
        items = data.get('items', [])

        if not cotizacion_id or not items:
            return jsonify({'success': False, 'msg': 'Datos incompletos'}), 400

        estado = CotizacionesModel.get_estado(cotizacion_id)
        if estado is None:
            return jsonify({'success': False, 'msg': 'La cotización no existe'}), 404
        if estado != 'ACTIVA':
            return jsonify({'success': False, 'msg': 'La cotización está cerrada y no admite cambios'}), 403

        CotizacionesModel.guardar_detalle_masivo(cotizacion_id, items, session.get('user_id'))
        return jsonify({'success': True, 'msg': 'Guardado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


@cotizaciones_bp.route('/<int:cotizacion_id>/estado', methods=['POST'])
@login_requerido
def cambiar_estado_cotizacion(cotizacion_id):
    """Cierra o reabre una cotización (ACTIVA / CERRADA)"""
    estado = (request.form.get('estado') or '').upper()
    if estado not in ('ACTIVA', 'CERRADA'):
        flash('El estado enviado no es válido.', 'danger')
        return redirect(url_for('planta_alimentos.cotizaciones.cotizaciones_list'))

    if CotizacionesModel.cambiar_estado(cotizacion_id, estado):
        flash('Cotización cerrada. Ya no admite cambios.' if estado == 'CERRADA'
              else 'Cotización reabierta. Ya se puede editar.', 'success')
    else:
        flash('La cotización no existe.', 'danger')

    return redirect(request.referrer or url_for('planta_alimentos.cotizaciones.cotizaciones_list'))


@cotizaciones_bp.route('/<int:cotizacion_id>/eliminar', methods=['POST'])
@login_requerido
def eliminar_cotizacion(cotizacion_id):
    """Elimina una cotización y todo su detalle"""
    try:
        if CotizacionesModel.eliminar_cotizacion(cotizacion_id):
            flash('Cotización eliminada.', 'success')
        else:
            flash('La cotización no existe.', 'danger')
    except Exception as e:
        flash(f'Error al eliminar la cotización: {str(e)}', 'danger')

    return redirect(url_for('planta_alimentos.cotizaciones.cotizaciones_list'))


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