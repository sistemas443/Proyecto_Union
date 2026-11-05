# routes/calificacion_lotes/vistas.py
from flask import Blueprint, jsonify, render_template, request

from routes.routes import login_requerido
from models.calificacion import services

calificacion_bp = Blueprint('calificacion_lotes', __name__)


@calificacion_bp.route('/calificacion-lotes')
@login_requerido
def vista_calificacion():
    """Pantalla de calificación: el lote y la semana se eligen aquí."""
    lotes = services.listar_lotes()

    lote_inicial = lotes[0] if lotes else None
    semanas = services.listar_semanas(lote_inicial['id']) if lote_inicial else []

    return render_template(
        'produccion/calificacion_lotes.html',
        lotes=lotes,
        semanas=semanas,
        lote_inicial=lote_inicial,
        semana_inicial=semanas[-1] if semanas else None,
        escala=services.escala_visible(),
        fuente_guia=services.FUENTE_GUIA,
    )


@calificacion_bp.route('/calificacion-lotes/semanas/<int:lote_id>')
@login_requerido
def api_semanas(lote_id):
    """Semanas con datos para el lote elegido."""
    return jsonify({'status': 'ok', 'semanas': services.listar_semanas(lote_id)})


@calificacion_bp.route('/calificacion-lotes/serie/<int:lote_id>')
@login_requerido
def api_serie(lote_id):
    """Serie del gráfico general del lote (para la vista previa)."""
    try:
        datos = services.serie_general(lote_id)
    except Exception as e:
        print(f"[ERROR SERIE CALIFICACION]: {e}")
        return jsonify({
            'status': 'error',
            'mensaje': 'No se pudo cargar el gráfico del lote.',
        }), 500

    if not datos['semanas']:
        return jsonify({
            'status': 'sin_datos',
            'mensaje': 'El lote no tiene datos para el gráfico general.',
        })

    return jsonify({'status': 'ok', **datos})


@calificacion_bp.route('/calificacion-lotes/evaluar')
@login_requerido
def api_evaluar():
    """Calcula la calificación de un lote en una semana."""
    lote_id = request.args.get('lote_id', type=int)
    semana = request.args.get('semana', type=int)

    if not lote_id or not semana:
        return jsonify({'status': 'error', 'mensaje': 'Seleccione lote y semana.'}), 400

    lote = services.buscar_lote(services.listar_lotes(), lote_id)
    if not lote:
        return jsonify({
            'status': 'error',
            'mensaje': 'El lote no tiene semanas con datos para calificar.',
        }), 404

    try:
        resultado = services.evaluar(lote_id, semana, lote=lote)
    except Exception as e:
        print(f"[ERROR CALIFICACION LOTE]: {e}")
        return jsonify({
            'status': 'error',
            'mensaje': 'No se pudo calcular la calificación.',
        }), 500

    return jsonify(resultado)
