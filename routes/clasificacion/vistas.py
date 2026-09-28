from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.clasificacion.services import get_clasificacion_all
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos

clasificacion_bp = Blueprint('clasificacion', __name__)


@clasificacion_bp.route('/clasificacion-produccion', methods=['GET', 'POST'])
@login_requerido
def clas_prod():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != '':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    return render_template(
        'produccion/clas_prod.html',
        filas=get_clasificacion_all(lote_seleccionado),
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=get_cabecera_info(lote_seleccionado)
    )