"""
Modelos para Cotizaciones de Productos
Gestión de cotizaciones por mes/año con proveedores y productos (materias_primas)
"""
from models.base import get_db_connection
from datetime import datetime


class CotizacionesModel:
    
    @staticmethod
    def get_cotizaciones_list(anio=None, estado=None):
        """Obtiene lista de cotizaciones agrupadas por mes/año (con filtros opcionales)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                condiciones = []
                parametros = []
                if anio:
                    condiciones.append("c.anio = %s")
                    parametros.append(anio)
                if estado:
                    condiciones.append("c.estado = %s")
                    parametros.append(estado)
                where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

                query = f"""
                    SELECT 
                        c.id, c.mes, c.anio, c.fecha_registro, c.estado,
                        u.nombre_completo as usuario_nombre,
                        COUNT(cd.id) as total_items
                    FROM cotizaciones c
                    LEFT JOIN usuarios u ON c.usuario_id = u.id
                    LEFT JOIN cotizacion_detalle cd ON c.id = cd.cotizacion_id
                    {where}
                    GROUP BY c.id, c.mes, c.anio, c.fecha_registro, c.estado, u.nombre_completo
                    ORDER BY c.anio DESC, c.mes DESC
                """
                cur.execute(query, tuple(parametros))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_anios_registrados():
        """Años con cotizaciones registradas, para el filtro de la lista"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT anio FROM cotizaciones ORDER BY anio DESC")
                return [fila[0] for fila in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_estado(cotizacion_id):
        """Devuelve el estado de una cotización ('ACTIVA', 'CERRADA' o None)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT estado FROM cotizaciones WHERE id = %s", (cotizacion_id,))
                fila = cur.fetchone()
                return fila[0] if fila else None
        finally:
            conn.close()

    @staticmethod
    def cambiar_estado(cotizacion_id, estado):
        """Cambia el estado de la cotización (ACTIVA / CERRADA)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE cotizaciones SET estado = %s WHERE id = %s", (estado, cotizacion_id))
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_cotizacion(cotizacion_id):
        """Elimina la cotización y su detalle (ON DELETE CASCADE)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cotizaciones WHERE id = %s", (cotizacion_id,))
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def get_cotizacion_by_mes_anio(mes, anio):
        """Obtiene cotización por mes y año (una por mes/año)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT id, mes, anio, fecha_registro, estado, usuario_id
                    FROM cotizaciones
                    WHERE mes = %s AND anio = %s
                """
                cur.execute(query, (mes, anio))
                row = cur.fetchone()
                if row:
                    columnas = [desc[0] for desc in cur.description]
                    return dict(zip(columnas, row))
                return None
        finally:
            conn.close()
    
    @staticmethod
    def crear_o_actualizar_cotizacion(mes, anio, usuario_id):
        """Crea o actualiza cotización para mes/año (upsert)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Verificar si existe
                cur.execute("SELECT id FROM cotizaciones WHERE mes = %s AND anio = %s", (mes, anio))
                row = cur.fetchone()
                
                if row:
                    cotizacion_id = row[0]
                    # Actualizar fecha y usuario
                    cur.execute("""
                        UPDATE cotizaciones 
                        SET fecha_registro = CURRENT_TIMESTAMP, usuario_id = %s, estado = 'ACTIVA'
                        WHERE id = %s
                    """, (usuario_id, cotizacion_id))
                else:
                    # Crear nueva
                    cur.execute("""
                        INSERT INTO cotizaciones (mes, anio, fecha_registro, usuario_id, estado)
                        VALUES (%s, %s, CURRENT_TIMESTAMP, %s, 'ACTIVA')
                        RETURNING id
                    """, (mes, anio, usuario_id))
                    cotizacion_id = cur.fetchone()[0]
                
                conn.commit()
                return cotizacion_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def _construir_consolidado(detalles):
        """
        Agrupa los precios por producto y proveedor y calcula:
        - mejor proveedor por promedio
        - precios semanales del mejor proveedor
        - ahorro frente al promedio de todos los proveedores
        """
        agrupado = {}
        for d in detalles:
            producto = d['producto_nombre']
            proveedor = d['proveedor_nombre']
            precio = float(d['precio'] or 0)
            grupo_prov = agrupado.setdefault(producto, {}).setdefault(
                proveedor, {'precios': {}, 'suma': 0.0, 'count': 0}
            )
            grupo_prov['precios'][int(d['semana'])] = precio
            grupo_prov['suma'] += precio
            grupo_prov['count'] += 1

        filas = []
        for producto, proveedores in agrupado.items():
            mejor_proveedor = None
            mejor_promedio = None
            for proveedor, grupo in proveedores.items():
                promedio = grupo['suma'] / grupo['count'] if grupo['count'] else 0
                if mejor_promedio is None or promedio < mejor_promedio:
                    mejor_promedio = promedio
                    mejor_proveedor = proveedor

            suma_todos = sum(g['suma'] for g in proveedores.values())
            count_todos = sum(g['count'] for g in proveedores.values())
            promedio_todos = suma_todos / count_todos if count_todos else 0

            promedio_mejor = mejor_promedio or 0
            ahorro = (promedio_todos - promedio_mejor) if promedio_mejor and promedio_todos else 0

            precios_mejor = proveedores[mejor_proveedor]['precios']
            con_precio = {sem: val for sem, val in precios_mejor.items() if val and val > 0}
            if con_precio:
                # Semana con el precio más bajo del producto (desempate: la semana menor)
                mejor_semana = min(con_precio, key=lambda sem: (con_precio[sem], sem))
                precio_mejor_semana = con_precio[mejor_semana]
            else:
                mejor_semana = None
                precio_mejor_semana = None

            filas.append({
                'producto': producto,
                'mejor_proveedor': mejor_proveedor,
                'precios': precios_mejor,
                'mejor_semana': int(mejor_semana) if mejor_semana else None,
                'precio_mejor_semana': precio_mejor_semana,
                'promedio': promedio_mejor,
                'ahorro': ahorro,
            })

        total_suma = sum(
            g['suma'] for proveedores in agrupado.values() for g in proveedores.values()
        )
        total_count = sum(
            g['count'] for proveedores in agrupado.values() for g in proveedores.values()
        )
        totales = {
            'promedio_general': (total_suma / total_count) if total_count else 0,
            # Se conserva la regla actual: solo ahorros positivos, proyectados a 4 semanas
            'ahorro_total': sum(f['ahorro'] * 4 for f in filas if f['ahorro'] > 0),
        }

        return filas, totales

    @staticmethod
    def get_detalle_cotizacion(cotizacion_id):
        """Obtiene detalle completo de una cotización para editar (grid)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Obtener info de la cotización
                cur.execute("""
                    SELECT id, mes, anio, fecha_registro, estado
                    FROM cotizaciones WHERE id = %s
                """, (cotizacion_id,))
                cot = cur.fetchone()
                if not cot:
                    return None
                cotizacion = dict(zip([desc[0] for desc in cur.description], cot))
                
                # Obtener proveedores (la tabla proveedores no tiene columna activo)
                cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
                proveedores = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
                
                # Obtener materias primas (la tabla no tiene columna activo)
                cur.execute("SELECT id, nombre FROM materias_primas ORDER BY nombre")
                productos = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
                
                # Obtener precios existentes
                cur.execute("""
                    SELECT cd.*, mp.nombre as producto_nombre, p.nombre as proveedor_nombre
                    FROM cotizacion_detalle cd
                    JOIN materias_primas mp ON cd.materia_prima_id = mp.id
                    JOIN proveedores p ON cd.proveedor_id = p.id
                    WHERE cd.cotizacion_id = %s
                    ORDER BY mp.nombre, cd.semana
                """, (cotizacion_id,))
                detalles = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

                consolidado, consolidado_totales = CotizacionesModel._construir_consolidado(detalles)

                return {
                    'cotizacion': dict(zip(['id', 'mes', 'anio', 'fecha_registro', 'estado'], cot)),
                    'proveedores': proveedores,
                    'productos': productos,
                    'detalles': detalles,
                    'consolidado': consolidado,
                    'consolidado_totales': consolidado_totales,
                }
        finally:
            conn.close()
    
    @staticmethod
    def guardar_detalle_masivo(cotizacion_id, items, usuario_id):
        """
        Guarda múltiples items de cotización (upsert masivo).
        items: lista de dicts {materia_prima_id, proveedor_id, semana, precio, observaciones}
        Si el precio llega vacío o en 0, se elimina el registro (permite borrar un precio).
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Catálogos válidos: evita que un id inexistente reviente con el error de FK
                cur.execute("SELECT id FROM materias_primas")
                mp_validos = {fila[0] for fila in cur.fetchall()}
                cur.execute("SELECT id FROM proveedores")
                prov_validos = {fila[0] for fila in cur.fetchall()}

                for item in items:
                    try:
                        mp_id = int(item.get('materia_prima_id'))
                        prov_id = int(item.get('proveedor_id'))
                        semana = int(item.get('semana'))
                    except (TypeError, ValueError):
                        raise ValueError('Datos incompletos en una de las filas enviadas')

                    if semana not in (1, 2, 3, 4):
                        raise ValueError('La semana debe estar entre 1 y 4')
                    if mp_id not in mp_validos:
                        raise ValueError('La materia prima indicada no existe')
                    if prov_id not in prov_validos:
                        raise ValueError('El proveedor indicado no existe')

                    try:
                        precio = float(item.get('precio') or 0)
                    except (TypeError, ValueError):
                        precio = 0.0

                    if precio <= 0:
                        # Sin precio: se borra la celda si existía
                        cur.execute("""
                            DELETE FROM cotizacion_detalle
                            WHERE cotizacion_id = %s AND materia_prima_id = %s
                              AND proveedor_id = %s AND semana = %s
                        """, (cotizacion_id, mp_id, prov_id, semana))
                        continue

                    cur.execute("""
                        SELECT id FROM cotizacion_detalle
                        WHERE cotizacion_id = %s AND materia_prima_id = %s AND proveedor_id = %s AND semana = %s
                    """, (cotizacion_id, mp_id, prov_id, semana))

                    row = cur.fetchone()

                    if row:
                        cur.execute("""
                            UPDATE cotizacion_detalle
                            SET precio = %s, observaciones = %s
                            WHERE id = %s
                        """, (precio, item.get('observaciones', ''), row[0]))
                    else:
                        cur.execute("""
                            INSERT INTO cotizacion_detalle (cotizacion_id, materia_prima_id, proveedor_id, semana, precio, observaciones)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (cotizacion_id, mp_id, prov_id, semana, precio, item.get('observaciones', '')))

                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def get_proveedores_activos():
        """Obtiene lista de proveedores activos"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
                return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
        finally:
            conn.close()
    
    @staticmethod
    def get_productos_activos():
        """Obtiene lista de materias primas (la tabla no tiene columna activo)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre FROM materias_primas ORDER BY nombre")
                return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
        finally:
            conn.close()
    
    @staticmethod
    def get_resumen_por_mes_anio(mes, anio):
        """Obtiene resumen de mejor precio por producto para un mes/año"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        mp.nombre as producto,
                        p.nombre as proveedor,
                        MIN(cd.precio) as mejor_precio,
                        MAX(cd.precio) as peor_precio,
                        AVG(cd.precio) as precio_promedio
                    FROM cotizacion_detalle cd
                    JOIN cotizaciones c ON cd.cotizacion_id = c.id
                    JOIN materias_primas mp ON cd.materia_prima_id = mp.id
                    JOIN proveedores p ON cd.proveedor_id = p.id
                    WHERE c.mes = %s AND c.anio = %s
                    GROUP BY mp.nombre, p.nombre
                    ORDER BY mp.nombre, cd.precio
                """
                cur.execute(query, (mes, anio))
                return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
        finally:
            conn.close()
    
    @staticmethod
    def get_mejor_precio_historico():
        """Obtiene el mejor precio histórico consolidado por producto (todas las cotizaciones, proveedores, semanas)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        mp.nombre as producto,
                        p.nombre as proveedor,
                        MIN(cd.precio) as mejor_precio,
                        MAX(cd.precio) as peor_precio,
                        AVG(cd.precio) as precio_promedio,
                        COUNT(*) as total_cotizaciones
                    FROM cotizacion_detalle cd
                    JOIN cotizaciones c ON cd.cotizacion_id = c.id
                    JOIN materias_primas mp ON cd.materia_prima_id = mp.id
                    JOIN proveedores p ON cd.proveedor_id = p.id
                    WHERE cd.precio > 0
                    GROUP BY mp.nombre, p.nombre
                    ORDER BY mp.nombre, mejor_precio ASC
                """
                cur.execute(query)
                rows = cur.fetchall()
                if not rows:
                    return {}
                
                # Agrupar por producto y tomar el mejor de todos los proveedores
                columnas = [desc[0] for desc in cur.description]
                mejor_por_producto = {}
                
                for row in rows:
                    data = dict(zip(columnas, row))
                    producto = data['producto']
                    if producto not in mejor_por_producto or data['mejor_precio'] < mejor_por_producto[producto]['mejor_precio']:
                        mejor_por_producto[producto] = data
                
                return mejor_por_producto
        finally:
            conn.close()
    
    @staticmethod
    def exportar_excel(mes, anio):
        """Exporta la cotización del mes/año a un libro de Excel con datos reales"""
        import io
        from collections import OrderedDict
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        meses_nombres = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT mp.nombre AS producto,
                           p.nombre AS proveedor,
                           cd.semana,
                           cd.precio
                    FROM cotizacion_detalle cd
                    JOIN cotizaciones c ON c.id = cd.cotizacion_id
                    JOIN materias_primas mp ON mp.id = cd.materia_prima_id
                    JOIN proveedores p ON p.id = cd.proveedor_id
                    WHERE c.mes = %s AND c.anio = %s
                    ORDER BY mp.nombre, p.nombre, cd.semana
                """, (mes, anio))
                filas = cur.fetchall()
        finally:
            conn.close()

        if not filas:
            return None

        # Agrupar por producto + proveedor para pintar una fila por combinación
        datos = OrderedDict()
        for producto, proveedor, semana, precio in filas:
            clave = (producto, proveedor)
            grupo = datos.setdefault(clave, {'semanas': {}, 'suma': 0.0, 'count': 0})
            valor = float(precio or 0)
            grupo['semanas'][int(semana)] = valor
            grupo['suma'] += valor
            grupo['count'] += 1

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Cotizacion_{mes}_{anio}"

        # --- Título ---
        ws.merge_cells('A1:G1')
        titulo = ws['A1']
        titulo.value = f"COTIZACIÓN DE MATERIAS PRIMAS · {meses_nombres[mes]} {anio}".upper()
        titulo.font = Font(bold=True, size=13, color='1A202C')
        titulo.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[1].height = 24

        ws.merge_cells('A2:G2')
        subtitulo = ws['A2']
        subtitulo.value = 'Precios en pesos colombianos (COP). PROMEDIO = media de las semanas con precio registrado.'
        subtitulo.font = Font(size=9, italic=True, color='6C757D')
        subtitulo.alignment = Alignment(horizontal='left')

        # --- Cabecera de tabla ---
        headers = ['PRODUCTO', 'PROVEEDOR', 'SEMANA 1', 'SEMANA 2', 'SEMANA 3', 'SEMANA 4', 'PROMEDIO']
        header_font = Font(bold=True, color='FFFFFF', size=10)
        header_fill = PatternFill(start_color='1A202C', end_color='1A202C', fill_type='solid')
        thin = Side(style='thin', color='DEE2E6')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        fila_actual = 4
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=fila_actual, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        ws.row_dimensions[fila_actual].height = 20
        ws.freeze_panes = f'A{fila_actual + 1}'

        # --- Datos ---
        formatos = ['@', '@', '#,##0.00', '#,##0.00', '#,##0.00', '#,##0.00', '#,##0.00']
        fila_actual += 1
        producto_anterior = None

        for (producto, proveedor), grupo in datos.items():
            promedio = (grupo['suma'] / grupo['count']) if grupo['count'] else 0
            valores = [
                producto if producto != producto_anterior else '',
                proveedor,
                grupo['semanas'].get(1),
                grupo['semanas'].get(2),
                grupo['semanas'].get(3),
                grupo['semanas'].get(4),
                promedio,
            ]
            producto_anterior = producto

            for col, valor in enumerate(valores, 1):
                cell = ws.cell(row=fila_actual, column=col, value=valor)
                cell.border = border
                cell.number_format = formatos[col - 1]
                if col <= 2:
                    cell.alignment = Alignment(horizontal='left', vertical='center')
                else:
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                if col == 1:
                    cell.font = Font(bold=True, size=10)
                elif col == 7:
                    cell.font = Font(bold=True, size=10, color='2C3E50')
            fila_actual += 1

        # --- Fila resumen ---
        total_promedios = sum(
            (g['suma'] / g['count']) for g in datos.values() if g['count']
        )
        promedio_general = (total_promedios / len(datos)) if datos else 0

        resumen = ws.cell(row=fila_actual, column=1, value='PROMEDIO GENERAL')
        resumen.font = Font(bold=True, size=10)
        resumen.fill = PatternFill(start_color='F1F3F5', end_color='F1F3F5', fill_type='solid')
        for col in range(1, 8):
            cell = ws.cell(row=fila_actual, column=col)
            cell.border = border
            cell.fill = PatternFill(start_color='F1F3F5', end_color='F1F3F5', fill_type='solid')
            if col > 2:
                cell.number_format = '#,##0.00'
        prom_cell = ws.cell(row=fila_actual, column=7, value=promedio_general)
        prom_cell.font = Font(bold=True, size=10, color='2C3E50')
        prom_cell.alignment = Alignment(horizontal='right')

        # --- Anchos ---
        anchos = [34, 28, 15, 15, 15, 15, 16]
        for col, ancho in enumerate(anchos, 1):
            ws.column_dimensions[get_column_letter(col)].width = ancho

        # --- Autofiltro ---
        ws.auto_filter.ref = f'A4:G{fila_actual - 1}'

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output