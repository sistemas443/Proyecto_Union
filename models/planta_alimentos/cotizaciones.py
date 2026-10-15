"""
Modelos para Cotizaciones de Productos
Gestión de cotizaciones por mes/año con proveedores y productos (materias_primas)
"""
from models.base import get_db_connection
from datetime import datetime


class CotizacionesModel:
    
    @staticmethod
    def get_cotizaciones_list():
        """Obtiene lista de cotizaciones agrupadas por mes/año"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        c.id, c.mes, c.anio, c.fecha_registro, c.estado,
                        u.nombre_completo as usuario_nombre,
                        COUNT(cd.id) as total_items
                    FROM cotizaciones c
                    LEFT JOIN usuarios u ON c.usuario_id = u.id
                    LEFT JOIN cotizacion_detalle cd ON c.id = cd.cotizacion_id
                    GROUP BY c.id, c.mes, c.anio, c.fecha_registro, c.estado, u.nombre_completo
                    ORDER BY c.anio DESC, c.mes DESC
                """
                cur.execute(query)
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
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
                
                return {
                    'cotizacion': dict(zip(['id', 'mes', 'anio', 'fecha_registro', 'estado'], cot)),
                    'proveedores': proveedores,
                    'productos': productos,
                    'detalles': detalles
                }
        finally:
            conn.close()
    
    @staticmethod
    def guardar_detalle_masivo(cotizacion_id, items, usuario_id):
        """
        Guarda múltiples items de cotización (upsert masivo)
        items: lista de dicts {materia_prima_id, proveedor_id, semana, precio, observaciones}
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for item in items:
                    if not item.get('precio') or float(item['precio']) <= 0:
                        print(f'[DEBUG MODELO] Saltando item sin precio válido: {item}')
                        continue
                    
                    print(f'[DEBUG MODELO] Procesando item: {item}')
                    
                    # Verificar si existe registro
                    cur.execute("""
                        SELECT id FROM cotizacion_detalle 
                        WHERE cotizacion_id = %s AND materia_prima_id = %s AND proveedor_id = %s AND semana = %s
                    """, (cotizacion_id, item['materia_prima_id'], item['proveedor_id'], item['semana']))
                    
                    row = cur.fetchone()
                    
                    if row:
                        # Actualizar
                        print(f'[DEBUG MODELO] Actualizando registro id={row[0]}')
                        cur.execute("""
                            UPDATE cotizacion_detalle 
                            SET precio = %s, observaciones = %s
                            WHERE id = %s
                        """, (item['precio'], item.get('observaciones', ''), row[0]))
                    else:
                        # Insertar
                        print(f'[DEBUG MODELO] Insertando nuevo registro')
                        cur.execute("""
                            INSERT INTO cotizacion_detalle (cotizacion_id, materia_prima_id, proveedor_id, semana, precio, observaciones)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (cotizacion_id, item['materia_prima_id'], item['proveedor_id'], item['semana'], item['precio'], item.get('observaciones', '')))
                
                print('[DEBUG MODELO] Commit ejecutado')
                conn.commit()
                return True
        except Exception as e:
            print(f'[ERROR MODELO] {e}')
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
        """Obtiene lista de materias primas activas"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre FROM materias_primas WHERE activo = TRUE ORDER BY nombre")
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
        """Exporta cotización a Excel"""
        import io
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Obtener cotización
                cur.execute("SELECT id FROM cotizaciones WHERE mes = %s AND anio = %s", (mes, anio))
                row = cur.fetchone()
                if not row:
                    return None
                cotizacion_id = row[0]
                
                # Obtener detalles
                cur.execute("""
                    SELECT cd.*, mp.nombre as producto, p.nombre as proveedor
                    FROM cotizacion_detalle cd
                    JOIN materias_primas mp ON cd.materia_prima_id = mp.id
                    JOIN proveedores p ON cd.proveedor_id = p.id
                    WHERE cd.cotizacion_id = %s
                    ORDER BY mp.nombre, cd.semana, p.nombre
                """, (cotizacion_id,))
                
                rows = cur.fetchall()
        finally:
            conn.close()
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Cotizacion_{mes}_{anio}"
        
        # Headers
        headers = ['PRODUCTO', 'PROVEEDOR', 'SEMANA 1', 'SEMANA 2', 'SEMANA 3', 'SEMANA 4', 'PROMEDIO']
        
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        
        # Agrupar por producto
        from collections import defaultdict
        datos_agrupados = defaultdict(lambda: defaultdict(lambda: {'precios': {}, 'sum': 0, 'count': 0}))
        
        # ... lógica de llenado Excel ...
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output