from flask import render_template, request, session
from routes.semanal.vistas import semanal_bp
from routes.routes import login_requerido
from models.semanal.services import get_data_grafico_general, get_data_grafico_conversion
from models.lotes.services import get_lotes_distintos


@semanal_bp.route('/grafico-general', methods=['GET', 'POST'])
@login_requerido
def grafico_general():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    datos_grafico = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        datos_grafico = get_data_grafico_general(lote_seleccionado)

    return render_template(
        'graficas/grafico_general.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        datos_grafico=datos_grafico
    )


@semanal_bp.route('/grafico-conversion', methods=['GET', 'POST'])
@login_requerido
def grafico_conversion():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    datos_grafico = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        datos_grafico = get_data_grafico_conversion(lote_seleccionado)

    return render_template(
        'graficas/grafico_conversion.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        datos_grafico=datos_grafico
    )