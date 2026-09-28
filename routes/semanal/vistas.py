from flask import Blueprint, render_template, request
from routes.routes import login_requerido
from models.semanal.services import get_semanal_all
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos

semanal_bp = Blueprint('semanal', __name__)


@semanal_bp.route('/semanal', methods=['GET', 'POST'])
@login_requerido
def semanal():
    lote_seleccionado = request.form.get('lote', '') if request.method == 'POST' else ''
    return render_template(
        'produccion/semanal.html',
        filas=get_semanal_all(lote_seleccionado),
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=get_cabecera_info(lote_seleccionado)
    )