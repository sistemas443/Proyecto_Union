from flask import render_template, request, redirect, url_for, flash
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido
from routes.routes import get_todos_los_lotes
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

@planta_bp.route('/planta_alimentos/editar-receta/<int:item_id>/<string:lote_id>', methods=['GET', 'POST'])
@login_requerido
def editar_receta(item_id, lote_id):
    # ==========================================
    # 0. CONSULTAS BASE
    # ==========================================
    lotes = get_todos_los_lotes()
    materias_primas = MateriaPrima.get_all()

    # 1. Obtener la versión seleccionada en la URL (si no viene, será None)
    version_solicitada = request.args.get('version', type=int)
    
    # 2. Consultar las versiones existentes
    info_versiones = FormulaDetalle.obtener_info_versiones(item_id, lote_id)
    lista_versiones = [v['version'] for v in info_versiones]
    ultima_version_existente = max(lista_versiones) if lista_versiones else 1
    
    # 3. Determinar qué versión vamos a mostrar en pantalla
    version_actual = version_solicitada if version_solicitada else ultima_version_existente
    es_ultima_version = (version_actual == ultima_version_existente)
    
    # 4. Obtener la fecha de vencimiento de la versión actual
    fecha_vencimiento = next((v['fecha_vencimiento'] for v in info_versiones if v['version'] == version_actual), '')

    # ==========================================
    # 3. PROCESAMIENTO DE FORMULARIOS (POST)
    # ==========================================
    if request.method == 'POST':
        
        # --- CASO A: GUARDAR PRODUCCIÓN DIARIA (CUADRO VERDE) ---
        if 'guardar_produccion' in request.form:
            fecha = request.form.get('fecha')
            
            # Manejo seguro del número de toneladas
            toneladas_raw = request.form.get('toneladas', '0').strip()
            if ',' in toneladas_raw and '.' in toneladas_raw:
                toneladas_raw = toneladas_raw.replace('.', '').replace(',', '.')
            else:
                toneladas_raw = toneladas_raw.replace(',', '.')
                
            try:
                toneladas = float(toneladas_raw) if toneladas_raw else 0.0
            except ValueError:
                toneladas = 0.0

            novedad = request.form.get('novedad', '')

            if fecha and toneladas > 0:
                # 1. Guardar producción por día
                FormulaProduccion.registrar_produccion(item_id, lote_id, fecha, toneladas, novedad, version_actual)
                
                # 2. DESCUENTO AUTOMÁTICO DE INVENTARIO (KÁRDEX)
                try:
                    receta_base = FormulaDetalle.obtener_receta(item_id, lote_id, version_actual)
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    for insumo in receta_base:
                        item = dict(insumo)
                        mp_id = item.get('materia_prima_id') or item.get('id_materia_prima')
                        cant_kg = float(item.get('cantidad_kg') or 0)
                        
                        if mp_id is not None and cant_kg > 0:
                            gramos_descontar = (toneladas * cant_kg) * 1000
                            
                            cursor.execute("""
                                INSERT INTO movimientos_inventario 
                                (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                                VALUES (%s, 'SALIDA_PRODUCCION', %s, %s, %s);
                            """, (mp_id, gramos_descontar, fecha, f"Producción Dieta {item_id} | Lote {lote_id} | {toneladas} Ton"))
                            
                    conn.commit()
                    cursor.close()
                    conn.close()
                    flash('Producción registrada y descontada del inventario correctamente.', 'success')
                except Exception as e:
                    print(f"Error detallado al descontar Kárdex: {e}")
                    flash(f'Se guardó la producción pero falló el Kárdex: {str(e)}', 'warning')
            else:
                flash('Por favor ingrese una fecha válida y una cantidad de toneladas mayor a 0.', 'warning')

            return redirect(url_for('planta_alimentos.editar_receta', item_id=item_id, lote_id=lote_id, version=version_actual))

        # --- CASO B: AGREGAR INSUMO / MATERIA PRIMA A LA RECETA (MODAL INSUMO +) ---
        materia_prima_id = request.form.get('materia_prima_id') or request.form.get('materia_prima') or request.form.get('insumo_id')
        
        # Limpieza segura de Kg / Bache
        cantidad_raw = request.form.get('cantidad_kg', '0').strip()
        if ',' in cantidad_raw and '.' in cantidad_raw:
            cantidad_raw = cantidad_raw.replace('.', '').replace(',', '.')
        else:
            cantidad_raw = cantidad_raw.replace(',', '.')
            
        try:
            cantidad_kg = float(cantidad_raw) if cantidad_raw else 0.0
        except ValueError:
            cantidad_kg = 0.0

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
    # 4. CARGA DE DATOS PARA UN LOTE ESPECÍFICO (GET)
    # ==========================================
    insumos_receta = FormulaDetalle.obtener_receta(item_id, lote_id, version_actual)
    resumen_totales = FormulaDetalle.obtener_resumen_totales(item_id, lote_id, version_actual)
    registros_produccion = FormulaProduccion.obtener_produccion_por_lote(item_id, lote_id, version_actual)
    total_toneladas_lote = float(sum([r['toneladas'] for r in registros_produccion])) if registros_produccion else 0.0

    receta_calculada = []
    for insumo in insumos_receta:
        cant_kg = float(insumo['cantidad_kg']) if insumo['cantidad_kg'] else 0.0
        consumos_diarios = [cant_kg * float(reg['toneladas']) for reg in registros_produccion]
        
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
        '/planta_alimentos/editar_receta.html',
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
        insumos_nucleo=insumos_nucleo
    )

    # ==========================================
    # 4. CARGA DE DATOS PARA UN LOTE ESPECÍFICO (GET)
    # ==========================================
    
    # [!] MUY IMPORTANTE: Ahora estas funciones reciben version_actual para no mezclar recetas viejas con nuevas
    insumos_receta = FormulaDetalle.obtener_receta(item_id, lote_id, version_actual)
    resumen_totales = FormulaDetalle.obtener_resumen_totales(item_id, lote_id, version_actual)
    
    # Registros de Producción por Día filtrados por versión
    registros_produccion = FormulaProduccion.obtener_produccion_por_lote(item_id, lote_id, version_actual)
    total_toneladas_lote = float(sum([r['toneladas'] for r in registros_produccion])) if registros_produccion else 0.0

    # Cálculo dinámico de Consumo Total por Materia Prima y Núcleos
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

    # ==========================================
    # 5. RETORNO FINAL CON TODAS LAS VARIABLES
    # ==========================================
    return render_template(
        '/planta_alimentos/editar_receta.html',
        item_id=item_id,
        lote_id=lote_id,
        version_actual=version_actual,
        lista_versiones=lista_versiones,
        es_ultima_version=es_ultima_version,
        fecha_vencimiento=fecha_vencimiento,
        
        # Aquí van todas las variables de tu tabla y producción
        insumos_receta=receta_calculada,
        totales=resumen_totales,
        materias_primas=materias_primas,  
        lotes=lotes,                      
        registros_produccion=registros_produccion,
        total_toneladas=total_toneladas_lote,
        insumos_nucleo=insumos_nucleo
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
    toneladas = request.form.get('toneladas')
    novedad = request.form.get('novedad', '')
    FormulaProduccion.actualizar_produccion(id_registro, toneladas, novedad)
    try:
        toneladas = float(toneladas_raw) if toneladas_raw else 0.0
        if toneladas > 0:
            FormulaProduccion.actualizar_produccion(id_registro, toneladas)
            flash('Toneladas actualizadas correctamente.', 'success')
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

