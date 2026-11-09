from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.semanal.services import get_semanal_all
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos
from models.comparador_lotes import construir_paneles, datos_lotes

semanal_bp = Blueprint('semanal', __name__)


@semanal_bp.route('/semanal', methods=['GET', 'POST'])
@login_requerido
def semanal():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = request.args.get('lote') or session.get('ultimo_lote', '')

    paneles, cantidad = construir_paneles(request)
    if paneles:
        lotes = get_lotes_distintos()
        return render_template(
            'produccion/comparador_modulo.html',
            paneles=paneles,
            cantidad=cantidad,
            lotes=lotes,
            datos_lotes=datos_lotes(lotes),
            endpoint=request.endpoint,
            titulo='Semanal producción',
        )

    cabecera = get_cabecera_info(lote_seleccionado)
    return render_template(
        'produccion/semanal.html',
        filas=get_semanal_all(lote_seleccionado, cabecera),
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera
    )