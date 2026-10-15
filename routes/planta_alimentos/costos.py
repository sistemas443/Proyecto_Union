from flask import render_template, request, redirect, url_for, flash, jsonify, session
from models.base import get_db_connection
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
    # 1. Precios materias primas - separar destacadas vs otras
    precios_mp_todas = MateriaPrima.get_all()
    materias_destacadas = [mp for mp in precios_mp_todas if mp.get('destacada_en_consolidado')]
    materias_otras = [mp for mp in precios_mp_todas if not mp.get('destacada_en_consolidado')]
    
    # 2. Costos consolidados ya calculados (modelo)
    costos_dietas = FormulaDetalle.obtener_consolidado_costos()
    
    # 3. Filtrar en 3 grupos fijos por empresa
    dietas_san_martin = [d for d in costos_dietas if d['nombre_empresa'] == 'SAN MARTIN']
    dietas_country = [d for d in costos_dietas if d['nombre_empresa'] == 'COUNTRY']
    dietas_dos_crestas = [d for d in costos_dietas if d['nombre_empresa'] == 'DOS CRESTAS SANTUARIO']
    
    return render_template(
        'planta_alimentos/consolidado_precios.html',
        materias_destacadas=materias_destacadas,
        materias_otras=materias_otras,
        dietas_san_martin=dietas_san_martin,
        dietas_country=dietas_country,
        dietas_dos_crestas=dietas_dos_crestas
    )


@planta_bp.route('/materia-prima/<int:mp_id>/toggle-destacada', methods=['POST'])
@login_requerido
def toggle_materia_destacada(mp_id):
    """Toggle materia prima como destacada en consolidado"""
    data = request.get_json(silent=True) or {}
    destacada = data.get('destacada', False)
    
    print(f"[DEBUG toggle] mp_id={mp_id}, destacada={destacada}, session_user={session.get('user_id')}")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE materias_primas SET destacada_en_consolidado = %s WHERE id = %s",
                (destacada, mp_id)
            )
            conn.commit()
        print(f"[DEBUG toggle] OK mp_id={mp_id}")
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error toggle destacada: {e}")
        return jsonify({'success': False, 'msg': str(e)}), 500
    finally:
        conn.close()