from flask import render_template, request, redirect, url_for, flash
from datetime import datetime
from collections import Counter
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

# Capacidad de silos por dieta (ton). Aun no existe en la base de datos:
# se deja como punto de configuracion hasta definir su origen.
CAPACIDAD_SILOS_POR_ITEM = {}


@planta_bp.route('/inventario/dietas', methods=['GET'])
@login_requerido
def inventario_dietas():
    """Inventario de dietas: una fila por dieta (item) y lote.

    Las filas salen de las recetas registradas en el modulo Editar Receta
    (formula_detalle). La produccion es el total fabricado por dieta y lote,
    expresado en kilogramos (la BD lo guarda en toneladas). El inventario
    inicial tambien se registra en kilogramos; el consumo, la venta y el
    inventario real se manejan en toneladas y corresponden al mes elegido.
    """
    import calendar

    mes_actual = datetime.now().month
    anio_actual = datetime.now().year

    mes = request.args.get('mes', default=mes_actual, type=int)
    anio = request.args.get('anio', default=anio_actual, type=int)

    # Validar rango del mes (evita IndexError al indexar meses_nombres)
    if mes < 1 or mes > 12:
        mes = mes_actual
    if anio < 2000 or anio > anio_actual:
        anio = anio_actual

    meses_nombres = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    dias_del_mes = calendar.monthrange(anio, mes)[1]
    semanas_del_mes = dias_del_mes / 7.0

    dietas = []
    anios_disponibles = [anio_actual]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # 1. Anios con informacion en las tablas de dietas
        cursor.execute("""
            SELECT DISTINCT anio FROM (
                SELECT EXTRACT(YEAR FROM fecha)::INT AS anio FROM formula_produccion_diaria
                UNION
                SELECT EXTRACT(YEAR FROM fecha)::INT AS anio FROM despachos_dieta
                UNION
                SELECT EXTRACT(YEAR FROM fecha)::INT AS anio FROM ventas_dieta
                UNION
                SELECT anio FROM inventario_dieta_inicial
            ) AS anios
            WHERE anio IS NOT NULL
            ORDER BY anio DESC;
        """)
        anios_disponibles = [fila['anio'] for fila in cursor.fetchall()]
        if not anios_disponibles:
            anios_disponibles = [anio_actual]
        elif anio_actual not in anios_disponibles:
            anios_disponibles.insert(0, anio_actual)
            anios_disponibles.sort(reverse=True)

        # El anio consultado debe existir en el selector aunque no tenga datos
        if anio not in anios_disponibles:
            anios_disponibles.append(anio)
            anios_disponibles.sort(reverse=True)

        # Rango del mes seleccionado (para el consumo del registro diario)
        fecha_ini = datetime(anio, mes, 1).date()
        fecha_fin = datetime(anio + 1, 1, 1).date() if mes == 12 else datetime(anio, mes + 1, 1).date()

        # 2. Una fila por dieta (item) + lote con receta registrada
        cursor.execute("""
            WITH pares AS (
                SELECT DISTINCT item_id, lote_id
                FROM formula_detalle
            ),
            inicial AS (
                SELECT item_id, lote_id, SUM(cantidad_inicial_ton) AS ton
                FROM inventario_dieta_inicial
                WHERE mes = %s AND anio = %s
                GROUP BY item_id, lote_id
            ),
            produccion AS (
                -- Total de toneladas fabricadas de la dieta en el lote
                SELECT item_id, lote_id, SUM(toneladas) AS ton
                FROM formula_produccion_diaria
                GROUP BY item_id, lote_id
            ),
            consumo_diario AS (
                -- Consumo real del mes segun el registro diario del lote.
                -- data_diario.consumo_kg ya viene en kilogramos totales del lote por dia.
                SELECT lote, SUM(consumo_kg) AS kg
                FROM data_diario
                WHERE fecha_dia ~ '^\\d{4}-\\d{2}-\\d{2}$'
                  AND fecha_dia::date >= %s::date
                  AND fecha_dia::date <  %s::date
                GROUP BY lote
            ),
            ventas AS (
                -- Toneladas vendidas de la dieta en el lote (venta externa registrada
                -- en Editar Receta: formula_produccion_diaria.es_venta = TRUE)
                SELECT item_id, lote_id, SUM(toneladas) AS ton
                FROM formula_produccion_diaria
                WHERE es_venta IS TRUE
                GROUP BY item_id, lote_id
            )
            SELECT
                ca.item_id,
                ca.nombre AS alimento,
                p.lote_id AS lote,
                i.ton IS NOT NULL AS inicial_registrada,
                COALESCE(i.ton, 0) AS inventario_inicial,
                COALESCE(pr.ton, 0) AS produccion,
                COALESCE(cd.kg, 0) AS consumo_kg,
                COALESCE(v.ton, 0) AS venta
            FROM pares p
            JOIN catalogo_alimentos ca ON ca.item_id = p.item_id
            LEFT JOIN inicial i ON i.item_id = p.item_id AND i.lote_id = p.lote_id
            LEFT JOIN produccion pr ON pr.item_id = p.item_id AND pr.lote_id = p.lote_id
            LEFT JOIN consumo_diario cd ON cd.lote = p.lote_id
            LEFT JOIN ventas v ON v.item_id = p.item_id AND v.lote_id = p.lote_id
            ORDER BY ca.item_id ASC, p.lote_id ASC;
        """, (mes, anio, fecha_ini, fecha_fin))

        filas = cursor.fetchall()

        # Dieta activa por lote: la que se produjo dentro del mes; si no hubo
        # produccion, la ultima dieta producida historicamente para ese lote.
        cursor.execute("""
            SELECT DISTINCT ON (lote_id) lote_id, item_id
            FROM formula_produccion_diaria
            WHERE fecha >= %s AND fecha < %s
            ORDER BY lote_id, fecha DESC, toneladas DESC
        """, (fecha_ini, fecha_fin))
        activo_mes = {f['lote_id']: f['item_id'] for f in cursor.fetchall()}

        cursor.execute("""
            SELECT DISTINCT ON (lote_id) lote_id, item_id
            FROM formula_produccion_diaria
            ORDER BY lote_id, fecha DESC, toneladas DESC
        """)
        activo_historico = {f['lote_id']: f['item_id'] for f in cursor.fetchall()}

        for fila in filas:
            item_id = fila['item_id']
            inicial = float(fila['inventario_inicial'] or 0)          # kilogramos
            produccion_ton = float(fila['produccion'] or 0)           # toneladas en BD
            produccion = produccion_ton * 1000.0                      # kilogramos
            venta_ton = float(fila['venta'] or 0)                     # toneladas en BD
            venta = venta_ton * 1000.0                                # kilogramos

            dietas.append({
                'item_id': item_id,
                'alimento': fila['alimento'],
                'lote': fila['lote'],
                'inicial_registrada': bool(fila['inicial_registrada']),
                'inventario_inicial': inicial,
                'produccion': produccion,
                'consumo_lote': float(fila['consumo_kg'] or 0),        # kilogramos del lote
                'venta': venta,
                'capacidad_silos': CAPACIDAD_SILOS_POR_ITEM.get(item_id),
            })

        # El diario registra el consumo por lote, no por dieta: si un lote tiene
        # varias dietas, el consumo se asigna solo a la dieta activa para no duplicarlo.
        dietas_por_lote = Counter(d['lote'] for d in dietas)
        for dieta in dietas:
            lote = dieta['lote']
            consumo_lote = dieta['consumo_lote']
            if dietas_por_lote[lote] == 1:
                consumo = consumo_lote
            else:
                activo = activo_mes.get(lote) or activo_historico.get(lote)
                consumo = consumo_lote if dieta['item_id'] == activo else 0.0

            consumo_ton = consumo / 1000.0
            total = dieta['inventario_inicial'] + dieta['produccion']
            inventario_real = total - consumo - dieta['venta']

            # Ritmo semanal de salida en toneladas (columna rotulada en TON)
            toneladas_semanal = consumo_ton / semanas_del_mes if semanas_del_mes else 0.0
            consumo_dia = (consumo / dias_del_mes) if dias_del_mes else 0.0
            alimento_dias = (inventario_real / consumo_dia) if consumo_dia > 0 else None

            dieta.update({
                'total': total,
                'consumo': consumo,
                'inventario_real': inventario_real,
                'alimento_dias': alimento_dias,
                'toneladas_semanal': toneladas_semanal,
            })

    except Exception as e:
        conn.rollback()
        flash(f"Error al cargar el inventario de dietas: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    # Marcar el inicio de cada dieta que tiene varios lotes, para separar
    # visualmente el grupo sin repetir la linea en dietas de un solo lote.
    lotes_por_item = Counter(d['item_id'] for d in dietas)
    item_anterior = None
    for dieta in dietas:
        dieta['group_start'] = (
            dieta['item_id'] != item_anterior
            and lotes_por_item[dieta['item_id']] > 1
            and item_anterior is not None
        )
        item_anterior = dieta['item_id']

    # Fila TOTAL: los dias de cobertura no se suman (se calculan por dieta y lote)
    capacidades = [d['capacidad_silos'] for d in dietas if d['capacidad_silos'] is not None]
    totales = {
        'inventario_inicial': round(sum(d['inventario_inicial'] for d in dietas), 2),
        'produccion': round(sum(d['produccion'] for d in dietas), 2),
        'total': round(sum(d['total'] for d in dietas), 2),
        'consumo': round(sum(d['consumo'] for d in dietas), 2),
        'venta': round(sum(d['venta'] for d in dietas), 2),
        'inventario_real': round(sum(d['inventario_real'] for d in dietas), 2),
        'alimento_dias': None,
        'capacidad_silos': round(sum(capacidades), 2) if capacidades else None,
        'toneladas_semanal': round(sum(d['toneladas_semanal'] for d in dietas), 2),
    }

    return render_template(
        'planta_alimentos/inventario_dietas.html',
        dietas=dietas,
        totales=totales,
        mes=mes,
        anio=anio,
        meses_nombres=meses_nombres,
        anios_disponibles=anios_disponibles
    )


@planta_bp.route('/inventario/dietas/inventario-inicial', methods=['POST'])
@login_requerido
def registrar_inventario_inicial_dieta():
    """Registra el inventario inicial (kilogramos) por dieta y lote."""
    mes = request.form.get('mes', type=int)
    anio = request.form.get('anio', type=int)
    anio_actual = datetime.now().year

    if not mes or mes < 1 or mes > 12 or not anio or anio < 2000 or anio > anio_actual:
        flash('El mes o el año enviado no es válido.', 'danger')
        return redirect(url_for('planta_alimentos.inventario_dietas'))

    item_ids = request.form.getlist('item_id')
    lote_ids = request.form.getlist('lote_id')
    cantidades = request.form.getlist('cantidad')

    if not (len(item_ids) == len(lote_ids) == len(cantidades)):
        flash('Los datos enviados no son válidos. Vuelve a intentarlo.', 'danger')
        return redirect(url_for('planta_alimentos.inventario_dietas', mes=mes, anio=anio))

    errores = []
    registros = []

    for item_raw, lote, cantidad_raw in zip(item_ids, lote_ids, cantidades):
        try:
            item_id = int(item_raw)
        except (TypeError, ValueError):
            errores.append('Hay una dieta con un ítem inválido.')
            continue

        texto = (cantidad_raw or '').strip().replace(',', '.')
        if texto == '':
            # Las filas vacias se dejan como estan (sirve para no registrar aun)
            continue

        try:
            cantidad = float(texto)
        except ValueError:
            errores.append(f'La cantidad de la dieta {item_id} / lote {lote} no es un número válido.')
            continue

        if cantidad < 0:
            errores.append(f'La cantidad de la dieta {item_id} / lote {lote} no puede ser negativa.')
            continue

        registros.append((item_id, lote, round(cantidad, 3)))

    if errores:
        flash(' '.join(errores[:3]), 'danger')
        return redirect(url_for('planta_alimentos.inventario_dietas', mes=mes, anio=anio))

    if not registros:
        flash('No se registró inventario inicial: todas las filas estaban vacías.', 'warning')
        return redirect(url_for('planta_alimentos.inventario_dietas', mes=mes, anio=anio))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Solo se aceptan dietas y lotes que existen en el recetario
        cursor.execute("""
            SELECT ca.item_id, fd.lote_id
            FROM catalogo_alimentos ca
            JOIN (SELECT DISTINCT item_id, lote_id FROM formula_detalle) fd
              ON fd.item_id = ca.item_id;
        """)
        pares_validos = {(fila['item_id'], fila['lote_id']) for fila in cursor.fetchall()}

        guardados = 0
        for item_id, lote, cantidad in registros:
            if (item_id, lote) not in pares_validos:
                continue

            cursor.execute("""
                INSERT INTO inventario_dieta_inicial
                    (item_id, lote_id, cantidad_inicial_ton, fecha_registro, mes, anio)
                VALUES (%s, %s, %s, CURRENT_DATE, %s, %s)
                ON CONFLICT (item_id, lote_id, mes, anio)
                DO UPDATE SET
                    cantidad_inicial_ton = EXCLUDED.cantidad_inicial_ton,
                    fecha_registro = CASE
                        WHEN inventario_dieta_inicial.cantidad_inicial_ton IS DISTINCT FROM EXCLUDED.cantidad_inicial_ton
                        THEN EXCLUDED.fecha_registro
                        ELSE inventario_dieta_inicial.fecha_registro
                    END;
            """, (item_id, lote, cantidad, mes, anio))
            guardados += 1

        conn.commit()
        flash(f'Inventario inicial registrado ({guardados} registros).', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Error al registrar el inventario inicial: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('planta_alimentos.inventario_dietas', mes=mes, anio=anio))


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