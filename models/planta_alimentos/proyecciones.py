"""
Modelos para Proyecciones de Inventario y Costos
Basado en Excel PROYECCION.xls - Hoja: CONSUMO DE FORMULAS 2026
Usa consultas SQL directas compatibles con el esquema real del proyecto
"""
from models.base import get_db_connection
from datetime import datetime, timedelta
import calendar


class ProyeccionesModel:
    
    @staticmethod
    def get_stock_actual(mes=None, anio=None):
        """
        Obtiene stock actual de cada materia prima replicando la lógica de /inventario/resumen
        """
        if mes is None:
            mes = datetime.now().month
        if anio is None:
            anio = datetime.now().year
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Replica la consulta de resumen_inventario en compras.py
                query = """
                    SELECT 
                        mp.id,
                        mp.nombre AS materia_prima,
                        COALESCE(inv_inicial.cantidad, 0) AS inicial,
                        COALESCE(compras.total_compras, 0) AS compras,
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
                """
                cur.execute(query, (mes, anio, mes, anio, mes, anio))
                columnas = [desc[0] for desc in cur.description]
                inventario = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
                
                resultado = {}
                dias_del_mes = calendar.monthrange(anio, mes)[1]
                
                for item in inventario:
                    row = dict(item)
                    consumo_mes = float(row['consumo_mes'] or 0)
                    inv_final = float(row['inventario_final'] or 0)
                    
                    # Cálculo: Consumo a 7 días (Consumo Mensual / Días del mes * 7)
                    consumo_7_dias = (consumo_mes / dias_del_mes) * 7
                    
                    # Semanas de inventario
                    sem_inv = inv_final / consumo_7_dias if consumo_7_dias > 0 else None
                    
                    mp_id = row['id']
                    resultado[mp_id] = {
                        'id': row['id'],
                        'nombre': row['materia_prima'],
                        'stock_actual': float(row['inventario_final'] or 0),  # En gramos
                        'stock_actual_ton': round(float(row['inventario_final'] or 0) / 1000000, 2),
                        'consumo_mes_gramos': consumo_mes,
                        'consumo_7_dias_gramos': consumo_7_dias,
                        'sem_inv': round(sem_inv, 1) if sem_inv else None,
                        'consumo_mes_gramos': consumo_mes
                    }
                return resultado
        finally:
            conn.close()
    
    @staticmethod
    def get_consumo_historico(dias=30, fecha_fin=None):
        """
        Calcula consumo histórico de cada MP desde formula_produccion_diaria x formula_detalle
        Basado en Excel: CONSUMO SEMANAL (7 DIAS) | CONSUMO * DIA (5 DIAS) | CONSUMO MENSUAL
        """
        if fecha_fin is None:
            fecha_fin = datetime.now().date()
        fecha_ini = fecha_fin - timedelta(days=dias)
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Consumo = SUM(toneladas * cantidad_kg * 1,000,000) por MP
                # Une formula_produccion_diaria con formula_detalle
                query = """
                    SELECT 
                        fd.materia_prima_id,
                        mp.nombre,
                        COALESCE(SUM(fpd.toneladas * fd.cantidad_kg * 1000000), 0) AS consumo_total_gramos,
                        COUNT(DISTINCT fpd.fecha) as dias_con_produccion
                    FROM formula_produccion_diaria fpd
                    JOIN formula_detalle fd 
                        ON fpd.item_id = fd.item_id 
                        AND fpd.lote_id = fd.lote_id 
                        AND fpd.version = fd.version
                    JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE fpd.fecha BETWEEN %s AND %s
                    AND fd.fecha_vencimiento >= %s  -- Solo versiones vigentes
                    GROUP BY fd.materia_prima_id, mp.nombre
                """
                cur.execute(query, (fecha_ini, fecha_fin, fecha_fin))
                rows = cur.fetchall()
                
                resultado = {}
                for row in rows:
                    mp_id, nombre, consumo_total, dias_con_datos = row
                    consumo_diario = float(consumo_total) / max(dias_con_datos, 1) if dias_con_datos > 0 else 0
                    resultado[mp_id] = {
                        'id': mp_id,
                        'nombre': nombre,
                        'consumo_total_gramos': float(consumo_total),
                        'consumo_diario_promedio': consumo_diario,
                        'dias_con_datos': dias_con_datos,
                        'consumo_semanal_proyectado': consumo_diario * 7,
                        'consumo_mensual_proyectado': consumo_diario * 30
                    }
                return resultado
        finally:
            conn.close()

    @staticmethod
    def get_consumo_ultimos_7_dias():
        """
        Calcula el consumo real de cada materia prima en los últimos 7 días calendario
        (HOY - 6 días a HOY inclusive).
        
        Incluye:
        - Todas las producciones (normales + ventas)
        - Todas las dietas, lotes, versiones
        - Receta vigente según version + fecha_vencimiento
        
        Returns:
            dict: {materia_prima_id: {'nombre': str, 'consumo_7_dias_gramos': float, 
                                     'consumo_7_dias_ton': float, 'dias_con_produccion': int}}
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        fd.materia_prima_id,
                        mp.nombre,
                        SUM(fd.cantidad_kg * fpd.toneladas * 1000) AS total_gramos,
                        COUNT(DISTINCT fpd.fecha) AS dias_con_produccion
                    FROM formula_produccion_diaria fpd
                    JOIN formula_detalle fd
                        ON fd.item_id = fpd.item_id
                       AND fd.lote_id = fpd.lote_id
                       AND fd.version = fpd.version
                       AND fd.fecha_vencimiento >= fpd.fecha
                    JOIN materias_primas mp ON mp.id = fd.materia_prima_id
                    WHERE fpd.fecha >= CURRENT_DATE - INTERVAL '6 days'
                      AND fpd.fecha <= CURRENT_DATE
                    GROUP BY fd.materia_prima_id, mp.nombre
                    ORDER BY mp.nombre;
                """
                cur.execute(query)
                rows = cur.fetchall()
                
                resultado = {}
                for row in rows:
                    mp_id, nombre, total_gramos, dias_con_prod = row
                    total_gramos = float(total_gramos or 0)
                    resultado[mp_id] = {
                        'id': mp_id,
                        'nombre': nombre,
                        'consumo_7_dias_gramos': total_gramos,
                        'consumo_7_dias_ton': round(total_gramos / 1_000_000, 3),
                        'dias_con_produccion': int(dias_con_prod or 0)
                    }
                return resultado
        finally:
            conn.close()
    
    @staticmethod
    def calcular_proyecciones():
        """
        Combina stock actual + consumo últimos 7 días → proyecciones + alertas
        Returns: Lista de dicts con estructura estilo Excel + gestión operativa
        Columnas: NÚMERO, MATERIA PRIMA, CONSUMO SEMANAL (7 DÍAS) GR, 
                  CONSUMO DÍA (5 DÍAS) GR, CONSUMO MENSUAL TON, DÍAS STOCK, ALERTAS
        """
        stock = ProyeccionesModel.get_stock_actual()
        consumo_7d = ProyeccionesModel.get_consumo_ultimos_7_dias()
        
        # Unir stock + consumo
        all_mp_ids = set(stock.keys()) | set(consumo_7d.keys())
        resultado = []
        
        for mp_id in all_mp_ids:
            s = stock.get(mp_id, {})
            c = consumo_7d.get(mp_id, {})
            
            stock_actual_gramos = s.get('stock_actual', 0)  # En gramos
            consumo_semanal_gramos = c.get('consumo_7_dias_gramos', 0)  # Total 7 días en gramos
            
            # CONSUMO DÍA (5 DÍAS SEMANAL) = Semanal / 5 (fijo, día laborable)
            consumo_diario_5dias_gramos = consumo_semanal_gramos / 5 if consumo_semanal_gramos > 0 else 0
            
            # CONSUMO MENSUAL = Diario (5 días) × 30 días calendario → en TONELADAS
            consumo_mensual_ton = (consumo_diario_5dias_gramos * 30) / 1_000_000
            
            # DÍAS STOCK = Stock actual / Consumo día laborable (más conservador)
            dias_stock = stock_actual_gramos / consumo_diario_5dias_gramos if consumo_diario_5dias_gramos > 0 else 999
            
            # ALERTAS (basadas en días stock con base día laborable)
            alertas = []
            if dias_stock < 7 and dias_stock > 0:
                alertas.append({'tipo': 'critica', 'mensaje': f'Stock crítico: {dias_stock:.1f} días'})
            elif dias_stock < 15 and dias_stock > 0:
                alertas.append({'tipo': 'advertencia', 'mensaje': f'Stock bajo: {dias_stock:.1f} días'})
            
            stock_minimo_gramos = consumo_diario_5dias_gramos * 30 * 0.2  # 20% consumo mensual en gramos
            if stock_actual_gramos < stock_minimo_gramos and stock_minimo_gramos > 0:
                alertas.append({'tipo': 'advertencia', 'mensaje': f'Stock < 20% consumo mensual'})
            
            tiene_alerta_critica = any(a['tipo'] == 'critica' for a in alertas)
            tiene_alerta = len(alertas) > 0
            
            resultado.append({
                'id': mp_id,
                'nombre': s.get('nombre') or c.get('nombre', f'MP-{mp_id}'),
                # Columnas estilo Excel
                'consumo_semanal_gramos': round(consumo_semanal_gramos),           # GRAMOS enteros
                'consumo_diario_5dias_gramos': round(consumo_diario_5dias_gramos), # GRAMOS/DÍA enteros
                'consumo_mensual_ton': round(consumo_mensual_ton, 3),               # TON 3 decimales
                # Columnas gestión operativa
                'dias_stock': round(dias_stock, 1) if dias_stock < 999 else 'N/A',
                'alertas': alertas,
                'tiene_alerta_critica': tiene_alerta_critica,
                'tiene_alerta': tiene_alerta
            })
        
        # Ordenar: alertas críticas primero, luego por nombre
        resultado.sort(key=lambda x: (not x['tiene_alerta_critica'], not x['tiene_alerta'], x['nombre']))
        
        # Agregar NÚMERO correlativo (1, 2, 3...)
        for idx, item in enumerate(resultado, 1):
            item['numero'] = idx
            
        return resultado
    
    @staticmethod
    def get_alertas_resumen():
        """Solo MPs con alertas para badge/notificaciones"""
        proyecciones = ProyeccionesModel.calcular_proyecciones()
        alertas_criticas = sum(1 for p in proyecciones if p['tiene_alerta_critica'])
        alertas_total = sum(1 for p in proyecciones if p['tiene_alerta'])
        return {
            'criticas': alertas_criticas,
            'total': alertas_total,
            'mps': [p for p in proyecciones if p['tiene_alerta']]
        }
    
    @staticmethod
    def exportar_excel():
        """Genera datos para exportar a Excel (formato estilo Excel solicitado)"""
        import io
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        
        proyecciones = ProyeccionesModel.calcular_proyecciones()
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Proyeccion Inventario"
        
        # Headers - Estructura nueva estilo Excel
        headers = [
            'NÚMERO', 'MATERIA PRIMA', 
            'CONSUMO SEMANAL (7 DÍAS) GR', 
            'CONSUMO DÍA (5 DÍAS) GR', 
            'CONSUMO MENSUAL TON', 
            'DÍAS STOCK', 'ALERTAS'
        ]
        
        # Estilos
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
        alerta_critica_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')
        alerta_adv_fill = PatternFill(start_color='FFA500', end_color='FFA500', fill_type='solid')
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        
        for row_idx, p in enumerate(proyecciones, 2):
            ws.cell(row=row_idx, column=1, value=p['numero'])
            ws.cell(row=row_idx, column=2, value=p['nombre'])
            ws.cell(row=row_idx, column=3, value=p['consumo_semanal_gramos'])
            ws.cell(row=row_idx, column=4, value=p['consumo_diario_5dias_gramos'])
            ws.cell(row=row_idx, column=5, value=p['consumo_mensual_ton'])
            ws.cell(row=row_idx, column=6, value=p['dias_stock'])
            
            alerta_text = '; '.join([a['mensaje'] for a in p['alertas']]) if p['alertas'] else 'OK'
            ws.cell(row=row_idx, column=7, value=alerta_text)
            
            # Colorear filas con alertas
            if p['tiene_alerta_critica']:
                for col in range(1, 8):
                    ws.cell(row=row_idx, column=col).fill = alerta_critica_fill
                    ws.cell(row=row_idx, column=col).font = Font(color='FFFFFF', bold=True)
            elif p['tiene_alerta']:
                for col in range(1, 8):
                    ws.cell(row=row_idx, column=col).fill = alerta_adv_fill
        
        # Ajustar ancho columnas
        for col in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max(max_length + 2, 12)
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output