from flask import render_template, request, redirect, url_for, flash
from routes.planta_alimentos.catalogo_a import planta_bp  # O la ruta donde tengas definido el Blueprint
from routes.routes import login_requerido
from models.planta_alimentos.maestros import MateriaPrima
from models.planta_alimentos.formulas import FormulaDetalle

@planta_bp.route('/revision-costos/<int:item_id>/<string:lote_id>', methods=['GET'])
@login_requerido
def revision_costos(item_id, lote_id):
    insumos = FormulaDetalle.obtener_costos_detallados(item_id, lote_id)
    
    # Variables para los totales
    nombre_dieta = insumos[0]['nombre_dieta'] if insumos else f"Dieta {item_id}"
    totales = {'cantidad': 0, 'c_iva': 0, 'c_flete': 0, 'c_iva_flete': 0}
    totales_sin_maquila = {'c_iva': 0, 'c_flete': 0, 'c_iva_flete': 0}

    for fila in insumos:
        cant = float(fila['cantidad'])
        precio = float(fila['precio'])
        iva_mult = float(fila['iva']) # Asumiendo que 1.00 es sin IVA extra
        flete = float(fila['flete'])

        # Cálculos por insumo
        costo_iva = cant * (precio * iva_mult)
        costo_flete = cant * (precio + flete)
        costo_iva_flete = cant * ((precio * iva_mult) + flete)

        # Guardamos en la fila para mostrarlos en la tabla
        fila['costo_iva'] = costo_iva
        fila['costo_flete'] = costo_flete
        fila['costo_iva_flete'] = costo_iva_flete

        # Sumamos a los totales generales
        totales['cantidad'] += cant
        totales['c_iva'] += costo_iva
        totales['c_flete'] += costo_flete
        totales['c_iva_flete'] += costo_iva_flete

        # Sumamos a los totales sin maquila si corresponde
        if not fila['es_maquila']:
            totales_sin_maquila['c_iva'] += costo_iva
            totales_sin_maquila['c_flete'] += costo_flete
            totales_sin_maquila['c_iva_flete'] += costo_iva_flete

    return render_template(
        'planta_alimentos/revision_costos.html',
        item_id=item_id,
        lote_id=lote_id,
        nombre_dieta=nombre_dieta,
        insumos=insumos,
        totales=totales,
        totales_sin_maquila=totales_sin_maquila
    )
    
    
@planta_bp.route('/consolidado-precios')
@login_requerido
def consolidado_precios():
    # 1. Obtenemos las materias primas para la tabla izquierda
    precios_mp = MateriaPrima.get_all() 
    
    # 2. Obtenemos toda la matemática procesada
    costos_dietas = FormulaDetalle.obtener_consolidado_costos()
    
    # 3. Agrupamos por empresa (San Martín, Country, etc.)
    costos_agrupados = {}
    for dieta in costos_dietas:
        empresa = dieta['nombre_empresa']
        if empresa not in costos_agrupados:
            costos_agrupados[empresa] = []
        costos_agrupados[empresa].append(dieta)

    return render_template(
        '/planta_alimentos/consolidado_precios.html',
        precios_mp=precios_mp,
        costos_agrupados=costos_agrupados
    )