from flask import render_template, request, redirect, url_for, flash
from datetime import datetime
import psycopg2.extras
from models.base import get_db_connection
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido  # O tu decorador correspondiente

# 1. RUTA PARA MOSTRAR EL FORMULARIO DE INGRESO DIARIO
@planta_bp.route('/compras/ingreso-diario', methods=['GET'])
@login_requerido
def ingreso_diario():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cursor.execute("SELECT id, nombre FROM materias_primas ORDER BY id ASC;")
    materias_primas = cursor.fetchall()
    
    cursor.close()
    conn.close()

    hoy = datetime.now().strftime('%Y-%m-%d')
    return render_template('planta_alimentos/ingreso_diario.html', materias_primas=materias_primas, hoy=hoy)


@planta_bp.route('/compras/guardar-ingreso-diario', methods=['POST'])
@login_requerido
def guardar_ingreso_diario():
    dia_numero = request.form.get('dia_numero')
    fecha_registro = request.form.get('fecha_registro')
    observacion_general = request.form.get('observacion_general') or f'Ingreso Día {dia_numero}'
    
    # Obtener las listas enviadas desde las filas dinámicas
    materias_primas_ids = request.form.getlist('materia_prima_id[]')
    cantidades = request.form.getlist('cantidad[]')
    costos = request.form.getlist('costo[]')
    lotes = request.form.getlist('lote[]')

    conn = get_db_connection()
    cursor = conn.cursor()
    registros_guardados = 0

    try:
        # Recorrer los arreglos sincronizadamente usando su índice
        for i in range(len(materias_primas_ids)):
            mp_id = materias_primas_ids[i]
            if not mp_id:  # Ignorar si dejaron una fila vacía
                continue
                
            cant_str = cantidades[i] if i < len(cantidades) else '0'
            
            if cant_str and float(cant_str) > 0:
                cantidad = float(cant_str)
                costo_str = costos[i] if i < len(costos) else '0'
                costo_unitario = float(costo_str) if costo_str else 0
                
                # Obtener el lote, si está vacío usar valor por defecto
                lote_capturado = lotes[i] if i < len(lotes) else ''
                lote = lote_capturado if lote_capturado else f'DIA-{dia_numero}'

                # 1. Guardar en tabla de compras/recepciones
                cursor.execute("""
                    INSERT INTO recepciones_compra 
                    (fecha_recepcion, materia_prima_id, lote_ingreso, cantidad_ingresada, costo_unitario, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (fecha_registro, mp_id, lote, cantidad, costo_unitario, f'Día {dia_numero} - {observacion_general}'))

                # 2. Registrar el movimiento en Kárdex
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                    VALUES (%s, 'ENTRADA_COMPRA', %s, %s, %s);
                """, (mp_id, cantidad, fecha_registro, f'Factura/Lote: {lote}'))

                registros_guardados += 1

        conn.commit()
        
        if registros_guardados > 0:
            flash(f'Se registraron exitosamente {registros_guardados} ingrediente(s).', 'success')
        else:
            flash('No se guardó nada porque no ingresaste cantidades mayores a cero.', 'warning')

    except Exception as e:
        conn.rollback()
        flash(f'Error al guardar el ingreso: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('planta_alimentos.matriz_mensual_compras'))

# 3. RUTA PARA LA MATRIZ MENSUAL
@planta_bp.route('/compras/matriz-mensual', methods=['GET'])
@login_requerido
def matriz_mensual_compras():
    from datetime import datetime
    anio_actual = datetime.now().year
    mes_actual = datetime.now().month
    
    anio = request.args.get('anio', default=anio_actual, type=int)
    mes = request.args.get('mes', default=mes_actual, type=int)

    # Definir los nombres de los meses en español
    meses_nombres = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    anios_disponibles = []

    try:
        # 1. Obtener los años únicos disponibles en la base de datos
        cursor.execute("""
            SELECT DISTINCT EXTRACT(YEAR FROM fecha_recepcion)::INT as anio 
            FROM recepciones_compra 
            ORDER BY anio DESC;
        """)
        anios_db = cursor.fetchall()
        anios_disponibles = [fila['anio'] for fila in anios_db]
        
        # Si la tabla está vacía, o el año actual no está en la lista, lo agregamos
        if not anios_disponibles:
            anios_disponibles = [anio_actual]
        elif anio_actual not in anios_disponibles:
            anios_disponibles.insert(0, anio_actual)
            anios_disponibles.sort(reverse=True)

        # 2. Obtener todas las materias primas
        cursor.execute("SELECT id, nombre FROM materias_primas ORDER BY id ASC;")
        materias_primas = cursor.fetchall()

        # 3. Consultar todas las recepciones del mes y año seleccionados
        cursor.execute("""
            SELECT 
                EXTRACT(DAY FROM fecha_recepcion)::INT as dia,
                materia_prima_id,
                SUM(cantidad_ingresada) as total_gramos
            FROM recepciones_compra
            WHERE EXTRACT(MONTH FROM fecha_recepcion) = %s 
              AND EXTRACT(YEAR FROM fecha_recepcion) = %s
            GROUP BY dia, materia_prima_id;
        """, (mes, anio))
        
        recepciones = cursor.fetchall()

        # 4. Construir y rellenar la matriz
        matriz = {}
        for dia in range(1, 32):
            matriz[dia] = {}
            for mp in materias_primas:
                matriz[dia][mp['id']] = 0

        for r in recepciones:
            dia = r['dia']
            mp_id = r['materia_prima_id']
            if dia in matriz and mp_id in matriz[dia]:
                matriz[dia][mp_id] = float(r['total_gramos'] or 0)

    except Exception as e:
        flash(f'Error al cargar los datos de la matriz: {str(e)}', 'danger')
        materias_primas = []
        matriz = {dia: {} for dia in range(1, 32)}
        anios_disponibles = [anio_actual]
    finally:
        cursor.close()
        conn.close()

    # Pasar las nuevas variables a la plantilla
    return render_template(
        'planta_alimentos/matriz_compras.html',
        materias_primas=materias_primas,
        matriz=matriz,
        mes=mes,
        anio=anio,
        dias=list(range(1, 32)),
        meses_nombres=meses_nombres,
        anios_disponibles=anios_disponibles
    )
def obtener_consolidado_mensual(mes, anio):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    mp.id AS materia_prima_id,
                    mp.nombre AS materia_prima,
                    COALESCE(inv.cantidad_inicial, 0) AS inicial,
                    COALESCE(compras.total_compras, 0) AS compras,
                    COALESCE(consumos.total_consumo, 0) AS consumo_mes,
                    (COALESCE(inv.cantidad_inicial, 0) + COALESCE(compras.total_compras, 0) - COALESCE(consumos.total_consumo, 0)) AS inventario_final
                FROM materias_primas mp
                LEFT JOIN (
                    SELECT materia_prima_id, SUM(cantidad_inicial) AS cantidad_inicial
                    FROM inventario_inicial
                    WHERE EXTRACT(MONTH FROM fecha_registro) = %s 
                      AND EXTRACT(YEAR FROM fecha_registro) = %s
                    GROUP BY materia_prima_id
                ) inv ON mp.id = inv.materia_prima_id
                LEFT JOIN (
                    SELECT materia_prima_id, SUM(cantidad) AS total_compras
                    FROM movimientos_inventario
                    WHERE tipo_movimiento = 'ENTRADA'
                      AND EXTRACT(MONTH FROM fecha) = %s 
                      AND EXTRACT(YEAR FROM fecha) = %s
                    GROUP BY materia_prima_id
                ) compras ON mp.id = compras.materia_prima_id
                LEFT JOIN (
                    SELECT materia_prima_id, SUM(cantidad) AS total_consumo
                    FROM movimientos_inventario
                    WHERE tipo_movimiento = 'SALIDA_PRODUCCION'
                      AND EXTRACT(MONTH FROM fecha) = %s 
                      AND EXTRACT(YEAR FROM fecha) = %s
                    GROUP BY materia_prima_id
                ) consumos ON mp.id = consumos.materia_prima_id
                ORDER BY mp.nombre ASC;
            """
            cur.execute(query, (mes, anio, mes, anio, mes, anio))
            columnas = [desc[0] for desc in cur.description]
            return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
    finally:
        conn.close()
@planta_bp.route('/inventario/resumen', methods=['GET'])
@login_requerido
def resumen_inventario():
    import calendar
    from datetime import datetime
    import psycopg2.extras
    
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    
    mes = request.args.get('mes', default=mes_actual, type=int)
    anio = request.args.get('anio', default=anio_actual, type=int)
    
    # Determinar cuántos días tiene el mes exacto para la proyección de 7 días
    dias_del_mes = calendar.monthrange(anio, mes)[1]

    meses_nombres = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    inventario_procesado = []
    
    try:
        # 1. Obtener años disponibles
        cursor.execute("SELECT DISTINCT EXTRACT(YEAR FROM fecha_recepcion)::INT as anio FROM recepciones_compra ORDER BY anio DESC;")
        anios_db = cursor.fetchall()
        anios_disponibles = [fila['anio'] for fila in anios_db]
        
        if not anios_disponibles:
            anios_disponibles = [anio_actual]
        elif anio_actual not in anios_disponibles:
            anios_disponibles.insert(0, anio_actual)
            anios_disponibles.sort(reverse=True)

        # 2. Consulta SQL base
        cursor.execute("""
            SELECT 
                mp.id,
                mp.nombre AS materia_prima,
                COALESCE(inv_inicial.cantidad, 0) AS inicial,
                COALESCE(compras.total_compras, 0) AS compras,
                (COALESCE(inv_inicial.cantidad, 0) + COALESCE(compras.total_compras, 0)) AS total_disponible,
                COALESCE(consumos.total_consumo, 0) AS consumo_mes,
                ((COALESCE(inv_inicial.cantidad, 0) + COALESCE(compras.total_compras, 0)) - COALESCE(consumos.total_consumo, 0)) AS inventario_final
            FROM materias_primas mp
            LEFT JOIN (
                SELECT materia_prima_id, SUM(cantidad_inicial) AS cantidad 
                FROM inventario_inicial 
                WHERE EXTRACT(MONTH FROM fecha_registro) = %s AND EXTRACT(YEAR FROM fecha_registro) = %s
                GROUP BY materia_prima_id
            ) inv_inicial ON mp.id = inv_inicial.materia_prima_id
            LEFT JOIN (
                SELECT materia_prima_id, SUM(cantidad_ingresada) AS total_compras 
                FROM recepciones_compra 
                WHERE EXTRACT(MONTH FROM fecha_recepcion) = %s AND EXTRACT(YEAR FROM fecha_recepcion) = %s
                GROUP BY materia_prima_id
            ) compras ON mp.id = compras.materia_prima_id
            LEFT JOIN (
                SELECT materia_prima_id, SUM(cantidad) AS total_consumo 
                FROM movimientos_inventario 
                WHERE tipo_movimiento = 'SALIDA_PRODUCCION' 
                  AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
                GROUP BY materia_prima_id
            ) consumos ON mp.id = consumos.materia_prima_id
            ORDER BY mp.id ASC;
        """, (mes, anio, mes, anio, mes, anio))
        
        inventario = cursor.fetchall()

        # 3. Procesar los cálculos matemáticos idénticos al Excel
        for item in inventario:
            row = dict(item)
            consumo_mes = float(row['consumo_mes'] or 0)
            inv_final = float(row['inventario_final'] or 0)
            
            # Cálculo 1: Consumo a 7 días (Consumo Mensual / Días del mes * 7)
            consumo_7_dias = (consumo_mes / dias_del_mes) * 7
            row['consumo_7_dias'] = consumo_7_dias
            
            # Cálculo 2: Semanas de Inventario (Inventario Final / Consumo a 7 días)
            if consumo_7_dias > 0:
                row['sem_inv'] = inv_final / consumo_7_dias
            else:
                row['sem_inv'] = None  # None servirá para pintar el #DIV/0! en el HTML
                
            inventario_procesado.append(row)

    except Exception as e:
        flash(f"Error al cargar el inventario: {str(e)}", "danger")
        anios_disponibles = [anio_actual]
    finally:
        cursor.close()
        conn.close()

    return render_template('planta_alimentos/resumen_inventario.html', 
                           inventario=inventario_procesado, 
                           mes=mes, 
                           anio=anio, 
                           meses_nombres=meses_nombres, 
                           anios_disponibles=anios_disponibles)

@planta_bp.route('/compras/recepcion', methods=['GET', 'POST'])
@login_requerido
def recepcion_compras():
    # Lógica de recepción individual...
    return render_template('planta_alimentos/recepcion.html')

@planta_bp.route('/compras/guardar-celda', methods=['POST'])
@login_requerido
def guardar_celda_matriz():
    # Recibir datos del modal
    dia = request.form.get('dia')
    mes = request.form.get('mes')
    anio = request.form.get('anio')
    mp_id = request.form.get('materia_prima_id')
    mp_nombre = request.form.get('materia_prima_nombre')
    
    cantidad = float(request.form.get('cantidad') or 0)
    costo = float(request.form.get('costo') or 0)
    lote = request.form.get('lote') or f'DIA-{dia}'

    if cantidad <= 0:
        flash('La cantidad debe ser mayor a cero.', 'warning')
        return redirect(url_for('planta_alimentos.matriz_mensual_compras', mes=mes, anio=anio))

    # Formatear la fecha basada en la celda seleccionada
    fecha_registro = f"{anio}-{int(mes):02d}-{int(dia):02d}"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Guardar Recepción
        cursor.execute("""
            INSERT INTO recepciones_compra 
            (fecha_recepcion, materia_prima_id, lote_ingreso, cantidad_ingresada, costo_unitario, observaciones)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (fecha_registro, mp_id, lote, cantidad, costo, f'Ingreso rápido desde Matriz'))

        # 2. Afectar Kárdex
        cursor.execute("""
            INSERT INTO movimientos_inventario 
            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
            VALUES (%s, 'ENTRADA_COMPRA', %s, %s, %s);
        """, (mp_id, cantidad, fecha_registro, f'Lote: {lote} (Matriz)'))

        conn.commit()
        flash(f'Ingreso de {cantidad}gr de {mp_nombre} guardado correctamente.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al guardar en celda: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()

    # Redirigir de vuelta a la matriz en el mismo mes y año que estaba mirando
    return redirect(url_for('planta_alimentos.matriz_mensual_compras', mes=mes, anio=anio))