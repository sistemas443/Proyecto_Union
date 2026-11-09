from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.clasificacion.services import get_clasificacion_all
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos
from models.comparador_lotes import construir_paneles, datos_lotes

clasificacion_bp = Blueprint('clasificacion', __name__)


@clasificacion_bp.route('/clasificacion-produccion', methods=['GET', 'POST'])
@login_requerido
def clas_prod():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != '':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = request.args.get('lote') or session.get('ultimo_lote', '')

    embed = request.args.get('embed') == '1'
    if embed:
        lote_embed = (request.args.get('lote') or '').strip()
        if lote_embed:
            lote_seleccionado = lote_embed

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
            titulo='Clasificación',
        )

    cabecera = get_cabecera_info(lote_seleccionado)
    return render_template(
        'produccion/clas_prod.html',
        filas=get_clasificacion_all(lote_seleccionado, cabecera),
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera
    )