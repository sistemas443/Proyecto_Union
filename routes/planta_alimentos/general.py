from flask import render_template, request, redirect, url_for, flash, session
from routes.planta_alimentos.catalogo_a import planta_bp  # O la ruta donde tengas definido el Blueprint
from routes.routes import login_requerido
from models.planta_alimentos.formulas import FormulaDetalle
from models.lotes.services import get_lotes_agrupados

@planta_bp.route('/resumen-lote-formulas', methods=['GET'])
@login_requerido
def resumen_lote_formulas():
    # Obtener el lote_id del formulario GET. Si no hay, queda vacio
    lote_id = (request.args.get('lote_id') or '').strip()

    lotes = FormulaDetalle.obtener_lotes_disponibles()

    # Nombres de los lotes que tienen formulas, para el selector agrupado
    nombres_lotes = set()
    for l in lotes:
        try:
            nombres_lotes.add(str(l['lote']))
        except (TypeError, KeyError, IndexError):
            nombres_lotes.add(str(l))

    # Mismo selector de lote que los modulos de produccion (activos / concluidos)
    lotes_agrupados = []
    for g in get_lotes_agrupados(session.get('user_rol')):
        filtrados = [x for x in g['lotes'] if x['nombre'] in nombres_lotes]
        if filtrados:
            grupo = dict(g)
            grupo['lotes'] = filtrados
            lotes_agrupados.append(grupo)

    vistos = {x['nombre'] for g in lotes_agrupados for x in g['lotes']}
    faltantes = sorted(nombres_lotes - vistos)
    if faltantes:
        lotes_agrupados.append({
            'id': 'SIN-CLASIFICAR',
            'titulo': 'SIN CLASIFICAR',
            'estado': 'ACTIVO',
            'prefijo': 'Otros',
            'lotes': [{'nombre': x, 'fecha': '', 'variedad': ''} for x in faltantes],
        })

    if not lote_id or lote_id == '0':
        formulas = []
    else:
        formulas = FormulaDetalle.obtener_formulas_por_lote(lote_id)

    return render_template(
        'planta_alimentos/resumen_lote_formulas.html',
        lote_id=lote_id,
        lotes=lotes,
        lotes_agrupados=lotes_agrupados,
        formulas=formulas
    )
    
    
@planta_bp.route('/kardex-inventario')
@login_requerido
def kardex_inventario():
    return "Módulo de Kardex en construcción"

@planta_bp.route('/control-silos')
@login_requerido
def control_silos():
    return "Módulo de Control de Silos en construcción"



