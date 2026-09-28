from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.diario.services import get_diario_all, generar_estructura_diario
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos

diario_bp = Blueprint('diario', __name__)


@diario_bp.route('/diario', methods=['GET', 'POST'])
@login_requerido
def diario():
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
        if cabecera:
            generar_estructura_diario(lote_seleccionado, cabecera.get('id'), cabecera.get('fecha_recepcion'))
        filas = get_diario_all(lote_seleccionado)

    return render_template(
        'produccion/diario.html',
        filas=filas,
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera
    )