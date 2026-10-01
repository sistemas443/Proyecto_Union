from flask import render_template, request, redirect, url_for, flash
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido
from models.lotes.services import get_todos_los_lotes
from models.planta_alimentos.maestros import MateriaPrima, CatalogoAlimento, Empresa
from models.planta_alimentos.transacciones import RegistroProduccion
from models.base import get_db_connection
from flask import render_template, request, redirect, url_for, flash, jsonify


@planta_bp.route('/receta/nueva-version/<int:item_id>/<string:lote_id>', methods=['POST'])
@login_requerido
def crear_version_receta(item_id, lote_id):
    nueva_version = FormulaDetalle.crear_nueva_version(item_id, lote_id)
    if nueva_version:
        flash(f'Versión {nueva_version} creada exitosamente. La versión anterior ha sido congelada.', 'success')
    else:
        flash('Error al generar la nueva versión.', 'error')
    
    # Redirigimos a la misma pantalla para ver los cambios
    return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))

@planta_bp.route('/receta/modificar-fecha', methods=['POST'])
@login_requerido
def modificar_fecha_receta():
    item_id = request.form.get('item_id')
    lote_id = request.form.get('lote_id')
    version = request.form.get('version')
    nueva_fecha = request.form.get('nueva_fecha')
    
    if FormulaDetalle.modificar_fecha_vencimiento(item_id, lote_id, version, nueva_fecha):
        flash('Fecha de vencimiento actualizada (Plazo ampliado).', 'success')
    else:
        flash('Error al actualizar la fecha.', 'error')
        
    return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))


from models.planta_alimentos.formulas import FormulaDetalle, FormulaProduccion
# Asegúrate de que MateriaPrima y CatalogoAlimento estén importados arriba

from flask import request, flash, redirect, url_for, render_template

def parse_float(val_str, default=0.0):
    if not val_str:
        return default
    val_str = str(val_str).strip()
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    else:
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return default


@planta_bp.route('/planta_alimentos/editar-receta/<int:item_id>/<string:lote_id>', methods=['GET', 'POST'])
@login_requerido
def editar_receta(item_id, lote_id):
    # ==========================================
    # 0. CONSULTAS BASE
    # ==========================================
    lotes = get_todos_los_lotes()
    materias_primas = MateriaPrima.get_all()

    empresas = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre FROM empresas ORDER BY nombre ASC;")
            empresas = cur.fetchall()
        conn.close()
    except Exception as e:
        print(f"Error al cargar empresas: {e}")

    # Manejo de Versiones
    version_solicitada = request.args.get('version', type=int)
    info_versiones = FormulaDetalle.obtener_info_versiones(item_id, lote_id)
    lista_versiones = [v['version'] for v in info_versiones]
    ultima_version_existente = max(lista_versiones) if lista_versiones else 1
    
    version_actual = version_solicitada if version_solicitada else ultima_version_existente
    es_ultima_version = (version_actual == ultima_version_existente)
    fecha_vencimiento = next((v['fecha_vencimiento'] for v in info_versiones if v['version'] == version_actual), '')

    # ==========================================
    # 1. PROCESAMIENTO DE FORMULARIOS (POST)
    # ==========================================
    if request.method == 'POST':
        print(f"--- DATOS RECIBIDOS EN POST: {request.form} ---")

        # --- CASO A: GUARDAR PRODUCCIÓN DIARIA ---
        if 'guardar_produccion' in request.form or request.form.get('fecha'):
            fecha = request.form.get('fecha')
            toneladas = parse_float(request.form.get('toneladas'))
            novedad = request.form.get('novedad', '')

            es_venta = request.form.get('es_venta') == '1'
            empresa_cliente = request.form.get('empresa_cliente', '').strip() if es_venta else None
            remision = request.form.get('remision', '').strip() if es_venta else None
            cal_kg = parse_float(request.form.get('cal_kg')) if es_venta else 0
            calcio_kg = parse_float(request.form.get('calcio_kg')) if es_venta else 0

            if fecha and toneladas > 0:
                try:
                    # Guardar Producción por Día (incluye descuento de receta base + CAL/CALCIO en modelo)
                    exito = FormulaProduccion.registrar_produccion(
                        item_id, lote_id, fecha, toneladas, novedad, version_actual,
                        es_venta, empresa_cliente, remision, cal_kg, calcio_kg
                    )
                    
                    if exito:
                        flash('Producción registrada y descontada del inventario correctamente.', 'success')
                    else:
                        flash('Error al guardar la producción.', 'danger')
                except Exception as e:
                    print(f"Error al registrar producción/kárdex: {e}")
                    flash(f'Error al guardar la producción: {str(e)}', 'danger')
            else:
                flash('Por favor ingrese una fecha válida y una cantidad de toneladas mayor a 0.', 'warning')

            return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id, version=version_actual))

        # --- CASO B: AGREGAR INSUMO / MATERIA PRIMA ---
        elif 'materia_prima_id' in request.form or 'materia_prima' in request.form or 'insumo_id' in request.form:
            materia_prima_id = request.form.get('materia_prima_id') or request.form.get('materia_prima') or request.form.get('insumo_id')
            cantidad_kg = parse_float(request.form.get('cantidad_kg'))

            if materia_prima_id and cantidad_kg > 0:
                exito = FormulaDetalle.agregar_insumo(item_id, lote_id, materia_prima_id, cantidad_kg, version_actual)
                if exito:
                    flash('Insumo agregado a la receta exitosamente.', 'success')
                else:
                    flash('Error al guardar el insumo en la base de datos.', 'danger')
            else:
                flash('Por favor seleccione una materia prima y especifique una cantidad mayor a 0 Kg.', 'warning')

            return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id, version=version_actual))

    # ==========================================
    # 2. CARGA DE DATOS PARA VISTA (GET)
    # ==========================================
    insumos_receta = FormulaDetalle.obtener_receta(item_id, lote_id, version_actual)
    resumen_totales = FormulaDetalle.obtener_resumen_totales(item_id, lote_id, version_actual)
    registros_produccion = FormulaProduccion.obtener_produccion_por_lote(item_id, lote_id, version_actual)
    total_toneladas_lote = float(sum([r['toneladas'] for r in registros_produccion])) if registros_produccion else 0.0

    receta_calculada = []
    for insumo in insumos_receta:
        cant_kg = float(insumo['cantidad_kg']) if insumo['cantidad_kg'] else 0.0
        
        consumos_diarios = []
        for reg in registros_produccion:
            toneladas_dia = float(reg['toneladas'])
            consumos_diarios.append(cant_kg * toneladas_dia)
        
        receta_calculada.append({
            'id': insumo['id'],
            'insumo': insumo['insumo'],
            'cantidad_kg': cant_kg,
            'consumos_diarios': consumos_diarios,
            'total_consumo_kg': cant_kg * total_toneladas_lote,
            'es_nucleo': insumo.get('es_nucleo', True) if dict(insumo).get('es_nucleo') is not None else True,
            'baches_nucleo': float(insumo.get('baches_nucleo', 6)) if dict(insumo).get('baches_nucleo') is not None else 6.0
        })

    insumos_nucleo = [i for i in receta_calculada if i['es_nucleo']]

    return render_template(
        'planta_alimentos/editar_receta.html',
        item_id=item_id,
        lote_id=lote_id,
        version_actual=version_actual,
        lista_versiones=lista_versiones,
        es_ultima_version=es_ultima_version,
        fecha_vencimiento=fecha_vencimiento,
        insumos_receta=receta_calculada,
        totales=resumen_totales,
        materias_primas=materias_primas,  
        lotes=lotes,                      
        registros_produccion=registros_produccion,
        total_toneladas=total_toneladas_lote,
        insumos_nucleo=insumos_nucleo,
        empresas=empresas
    )
    
    
@planta_bp.route('/receta/nucleo/baches/<int:id_registro>', methods=['POST'])
@login_requerido
def actualizar_baches_nucleo(id_registro):
    item_id = request.form.get('item_id')
    lote_id = request.form.get('lote_id')
    baches_raw = request.form.get('baches_nucleo', '6').replace(',', '.')
    
    try:
        FormulaDetalle.actualizar_baches_nucleo(id_registro, float(baches_raw))
    except Exception as e:
        print(f"Error: {e}")
        
    return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))

@planta_bp.route('/editar-receta/actualizar-produccion/<int:id_registro>', methods=['POST'])
@login_requerido
def actualizar_produccion_diaria(id_registro):
    item_id = request.form.get('item_id')
    lote_id = request.form.get('lote_id')
    toneladas = parse_float(request.form.get('toneladas'))
    novedad = request.form.get('novedad', '')
    cal_kg = parse_float(request.form.get('cal_kg'))
    calcio_kg = parse_float(request.form.get('calcio_kg'))

    try:
        if toneladas > 0:
            exito = FormulaProduccion.actualizar_produccion(
                id_registro, toneladas, novedad, cal_kg, calcio_kg
            )
            if exito:
                flash('Producción actualizada correctamente.', 'success')
            else:
                flash('Error al actualizar la producción.', 'danger')
        else:
            flash('Las toneladas deben ser mayor a cero.', 'warning')
    except Exception as e:
        print(f"Error al actualizar producción: {e}")
        flash('Error al actualizar las toneladas.', 'danger')

    if item_id and lote_id:
        return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))
    return redirect(url_for('planta_alimentos.catalogo_alimentos'))

@planta_bp.route('/editar-receta/eliminar-produccion/<int:id_registro>', methods=['POST'])
@login_requerido
def eliminar_produccion_diaria(id_registro):
    item_id = request.form.get('item_id')
    lote_id = request.form.get('lote_id')
    
    try:
        FormulaProduccion.eliminar_produccion(id_registro)
        flash('Registro de producción eliminado.', 'warning')
    except Exception as e:
        print(f"Error al eliminar registro de producción: {e}")
        flash('Error al eliminar la fecha de producción.', 'danger')

    if item_id and lote_id:
        return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))
    return redirect(url_for('planta_alimentos.catalogo_alimentos'))

@planta_bp.route('/receta/eliminar-insumo/<int:id_registro>', methods=['POST'])
@login_requerido
def eliminar_insumo_receta(id_registro):
    item_id = request.form.get('item_id')
    lote_id = request.form.get('lote_id')
    
    try:
        FormulaDetalle.eliminar_insumo(id_registro)
    except Exception as e:
        print(f"Error al eliminar insumo: {e}")
        
    return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))

@planta_bp.route('/planta_alimentos/receta/actualizar/<int:id_registro>', methods=['POST'])
@login_requerido
def actualizar_insumo_receta(id_registro):
    item_id = request.form.get('item_id')
    lote_id = request.form.get('lote_id')
    
    # Captura y limpieza del peso enviado desde la tabla
    cantidad_raw = request.form.get('cantidad_kg', '0').replace('.', '').replace(',', '.')
    
    try:
        nueva_cantidad = float(cantidad_raw) if cantidad_raw else 0.0
        if nueva_cantidad > 0:
            FormulaDetalle.actualizar_insumo(id_registro, nueva_cantidad)
            flash('Cantidad actualizada correctamente.', 'success')
        else:
            flash('La cantidad debe ser mayor a cero.', 'warning')
    except Exception as e:
        print(f"Error al actualizar insumo de receta: {e}")
        flash('Error al actualizar la cantidad del insumo.', 'danger')

    # ESENCIAL: Siempre debe retornar una respuesta HTTP
    if item_id and lote_id:
        return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id))
    
    return redirect(url_for('main.catalogo_alimentos'))

@planta_bp.route('/receta/nucleo/toggle/<int:id_registro>/<int:estado>', methods=['POST'])
@login_requerido
def toggle_nucleo(id_registro, estado):
    es_nucleo = True if estado == 1 else False
    try:
        FormulaDetalle.alternar_nucleo(id_registro, es_nucleo)
        return jsonify({'success': True, 'estado': estado})
    except Exception as e:
        print(f"Error al alternar núcleo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@planta_bp.route('/receta/eliminar-formula/<int:item_id>/<string:lote_id>', methods=['POST'])
@login_requerido
def eliminar_formula_lote(item_id, lote_id):
    try:
        FormulaDetalle.eliminar_formula_lote(item_id, lote_id)
    except Exception as e:
        print(f"Error al eliminar la fórmula: {e}")
        
    return redirect(url_for('main.resumen_lote_formulas', lote_id=lote_id))

@planta_bp.route('/registro-baches', methods=['GET', 'POST'])
@login_requerido
def registro_baches():
    if request.method == 'POST':
        fecha = request.form.get('fecha')
        lote_id = request.form.get('lote_id')
        empresa_id = request.form.get('empresa_id')
        item_id = request.form.get('item_id')
        cantidad_baches = request.form.get('cantidad_baches', 0)
        toneladas_raw = request.form.get('toneladas_producidas', 0)
        
        try:
            # 1. Asegurar que las toneladas sean un valor numérico (float)
            toneladas = float(toneladas_raw) if toneladas_raw else 0.0
            
            # 2. Guardar el registro de producción original
            RegistroProduccion.create(fecha, lote_id, empresa_id, item_id, cantidad_baches, toneladas)
            
            # 3. DESCARGA AUTOMÁTICA DE INVENTARIO (KÁRDEX)
            if toneladas > 0:
                # Buscamos la última versión de la fórmula para saber qué descontar
                info_versiones = FormulaDetalle.obtener_info_versiones(item_id, lote_id)
                
                if info_versiones:
                    ultima_version = max([v['version'] for v in info_versiones])
                    insumos_receta = FormulaDetalle.obtener_receta(item_id, lote_id, ultima_version)
                    
                    # Conectar a la base de datos
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    for insumo in insumos_receta:
                        # Extraer ID y cantidad
                        mp_id = insumo.get('materia_prima_id') or insumo.get('id_materia_prima')
                        kg_por_tonelada = float(insumo['cantidad_kg'])
                        
                        # Calcular gramos a descontar: (Toneladas * Kg/Ton) * 1000
                        consumo_gramos = (toneladas * kg_por_tonelada) * 1000
                        
                        # Insertar salida en la tabla de movimientos
                        cursor.execute("""
                            INSERT INTO movimientos_inventario 
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, 'SALIDA_PRODUCCION', %s, %s, %s);
                        """, (mp_id, consumo_gramos, fecha, f"Registro Baches | Dieta {item_id} | Lote {lote_id} | {toneladas} Ton"))
                        
                    conn.commit()
                    cursor.close()
                    conn.close()
            
            flash('Producción guardada e inventario actualizado correctamente.', 'success')
            
        except Exception as e:
            print(f"Error al descontar Kárdex: {e}")
            flash(f'Se guardó la producción pero hubo un error: {str(e)}', 'danger')
            
        return redirect(url_for('main.registro_baches'))
        
    historial = RegistroProduccion.get_all()
    empresas = Empresa.get_all()
    alimentos = CatalogoAlimento.get_all()
    lotes = RegistroProduccion.get_lotes() 
    
    return render_template('/planta_alimentos/registro_baches.html', 
                           historial=historial, 
                           empresas=empresas, 
                           alimentos=alimentos,
                           lotes=lotes)
    
@planta_bp.route('/planta_alimentos/cierre-mes', methods=['POST'])
@login_requerido
def realizar_cierre_mes():
    mes_origen = request.form.get('mes', type=int)
    anio_origen = request.form.get('anio', type=int)
    
    if not mes_origen or not anio_origen:
        flash('Debe seleccionar un mes y año válidos para realizar el cierre.', 'warning')
        return redirect(url_for('planta_alimentos.ver_consolidado'))

    # Ejecutar el traslado de saldos finales -> iniciales del mes siguiente
    exito, mensaje = Inventario.ejecutar_cierre_mes(mes_origen, anio_origen)
    
    if exito:
        flash(f'¡Éxito! {mensaje}', 'success')
    else:
        flash(f'Error al procesar el cierre de mes: {mensaje}', 'danger')
        
    return redirect(url_for('planta_alimentos.ver_consolidado', mes=mes_origen, anio=anio_origen))

@planta_bp.route('/planta_alimentos/reabrir-mes', methods=['POST'])
@login_requerido
def reabrir_mes():
    mes = request.form.get('mes', type=int)
    anio = request.form.get('anio', type=int)

    if mes and anio:
        exito, mensaje = Inventario.reabrir_mes(mes, anio)
        if exito:
            flash(mensaje, 'info')
        else:
            flash(f'Error al reabrir el mes: {mensaje}', 'danger')
            
    return redirect(url_for('planta_alimentos.resumen_inventario', mes=mes, anio=anio))




