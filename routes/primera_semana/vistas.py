from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.primera_semana.services import get_primera_semana_by_lote, get_data_grafico_primera_semana
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos

primera_semana_bp = Blueprint('primera_semana', __name__)


@primera_semana_bp.route('/primera-semana', methods=['GET', 'POST'])
@login_requerido
def primera_semana():
    # Tabla exclusiva para seguimiento estricto del arranque en granja de los primeros 7 días
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    filas = []
    cabecera = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        cabecera = get_cabecera_info(lote_seleccionado)
        filas = get_primera_semana_by_lote(lote_seleccionado)

    return render_template(
        'produccion/primera_semana.html',
        filas=filas,
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera
    )


@primera_semana_bp.route('/grafico-primera-semana', methods=['GET', 'POST'])
@login_requerido
def grafico_primera_semana():
    # Sistema de memoria para recordar el lote seleccionado
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    datos_grafico = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        datos_grafico = get_data_grafico_primera_semana(lote_seleccionado)

    return render_template(
        'produccion/grafico_primera_semana.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        datos_grafico=datos_grafico
    )