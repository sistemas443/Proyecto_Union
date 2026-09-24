from flask import render_template, request, redirect, url_for, flash
from routes.planta_alimentos.catalogo_a import planta_bp  # O la ruta donde tengas definido el Blueprint
from routes.routes import login_requerido
from models.planta_alimentos.formulas import FormulaDetalle

@planta_bp.route('/resumen-lote-formulas', methods=['GET'])
@login_requerido
def resumen_lote_formulas():
    # Obtener el lote_id del formulario GET. Si no hay, asignamos '0'
    lote_id = request.args.get('lote_id', '0')
    
    lotes = FormulaDetalle.obtener_lotes_disponibles()
    
    if lote_id == '0':
        formulas = []
    else:
        formulas = FormulaDetalle.obtener_formulas_por_lote(lote_id)
        
    return render_template(
        'planta_alimentos/resumen_lote_formulas.html',
        lote_id=lote_id,
        lotes=lotes,
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

@planta_bp.route('/proyeccion-costos')
@login_requerido
def proyeccion_costos():
    return "Módulo de Proyección y Costos en construcción"



