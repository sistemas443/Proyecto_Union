from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.primera_semana.services import get_primera_semana_by_lote, get_data_grafico_primera_semana
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos
from models.catalogos import services as catalogos_services

primera_semana_bp = Blueprint('primera_semana', __name__)

# Interruptor del comparador de lotes (piloto en Primera semana).
# Si se necesita desactivar sin revertir el código, basta con dejarlo en False.
COMPARADOR_LOTES_ACTIVO = True
LETRAS_COMPARADOR = ('A', 'B', 'C', 'D')
COLORES_COMPARADOR = ('#97271C', '#1f4e79', '#2f7d4f', '#a06a00')


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
        filas = get_primera_semana_by_lote(lote_seleccionado, cabecera)

    # --- Comparador de lotes (piloto) ---
    comparar = (
        COMPARADOR_LOTES_ACTIVO
        and request.args.get('comparar') == '1'
        and bool(lote_seleccionado)
        and lote_seleccionado != 'VACIO'
    )
    try:
        cantidad = int(request.args.get('cantidad', 2))
    except (TypeError, ValueError):
        cantidad = 2
    cantidad = max(2, min(4, cantidad))

    lotes_extra = [
        (request.args.get('lote_b') or '').strip(),
        (request.args.get('lote_c') or '').strip(),
        (request.args.get('lote_d') or '').strip(),
    ]

    paneles = []
    if comparar:
        usados = {lote_seleccionado}
        paneles.append({
            'letra': LETRAS_COMPARADOR[0],
            'color': COLORES_COMPARADOR[0],
            'lote': lote_seleccionado,
            'cabecera': cabecera,
            'filas': filas,
        })
        for indice in range(1, cantidad):
            lote_extra = lotes_extra[indice - 1]
            if not lote_extra or lote_extra == 'VACIO' or lote_extra in usados:
                paneles.append({
                    'letra': LETRAS_COMPARADOR[indice],
                    'color': COLORES_COMPARADOR[indice],
                    'lote': '',
                    'cabecera': None,
                    'filas': [],
                })
                continue
            usados.add(lote_extra)
            cab_extra = get_cabecera_info(lote_extra)
            paneles.append({
                'letra': LETRAS_COMPARADOR[indice],
                'color': COLORES_COMPARADOR[indice],
                'lote': lote_extra,
                'cabecera': cab_extra,
                'filas': get_primera_semana_by_lote(lote_extra, cab_extra),
            })

    return render_template(
        'produccion/primera_semana.html',
        filas=filas,
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera,
        comparador_activo=COMPARADOR_LOTES_ACTIVO,
        comparar=comparar,
        cantidad=cantidad,
        paneles=paneles,
        lotes_extra=lotes_extra,
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
    info_lote = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        datos_grafico = get_data_grafico_primera_semana(lote_seleccionado)
        cab = get_cabecera_info(lote_seleccionado) or {}
        info_lote = catalogos_services.info_lote_para_grafico(cab, 'nutricionista', 'Nutricionista Levante')

    return render_template(
        'graficas/grafico_primera_semana.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        datos_grafico=datos_grafico,
        info_lote=info_lote
    )