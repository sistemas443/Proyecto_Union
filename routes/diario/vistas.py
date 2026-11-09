from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.diario.services import get_diario_all, generar_estructura_diario
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos
from models.comparador_lotes import construir_paneles, datos_lotes

diario_bp = Blueprint('diario', __name__)


@diario_bp.route('/diario', methods=['GET', 'POST'])
@login_requerido
def diario():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = request.args.get('lote') or session.get('ultimo_lote', '')

    # Modo embebido dentro del comparador: lote por URL, sin escribir en sesión
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
            titulo='Informe diario',
        )

    filas = []
    cabecera = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        cabecera = get_cabecera_info(lote_seleccionado)
        if cabecera and not embed:
            generar_estructura_diario(lote_seleccionado, cabecera.get('id'), cabecera.get('fecha_recepcion'))
        filas = get_diario_all(lote_seleccionado, cabecera)

    return render_template(
        'produccion/diario.html',
        filas=filas,
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera
    )