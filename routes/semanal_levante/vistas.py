from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.semanal_levante.services import get_semanal_levante_all
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos

semanal_levante_bp = Blueprint('semanal_levante', __name__)


@semanal_levante_bp.route('/semanal-levante', methods=['GET', 'POST'])
@login_requerido
def semanal_levante():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != '':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    return render_template(
        'produccion/sem_lev.html',
        filas=get_semanal_levante_all(lote_seleccionado),
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=get_cabecera_info(lote_seleccionado)
    )