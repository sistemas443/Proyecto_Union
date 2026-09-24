import psycopg2
from psycopg2.extras import DictCursor  
from models.base import get_db_connection


class FormulaDetalle:
    
    @staticmethod
    def obtener_consolidado_costos():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    WITH UltimasVersiones AS (
                        -- 1. Buscamos la última versión real de cada receta, sin excepciones
                        SELECT item_id, lote_id, MAX(version) as max_version
                        FROM formula_detalle
                        GROUP BY item_id, lote_id
                    ),
                    CostosBase AS (
                        SELECT 
                            fd.item_id,
                            fd.lote_id,
                            SUM(fd.cantidad_kg * mp.precio_actual_kg) AS total_precio_base,
                            SUM(fd.cantidad_kg * mp.flete) AS total_flete,
                            SUM(fd.cantidad_kg * (mp.precio_actual_kg * COALESCE(mp.iva, 1))) AS total_con_iva
                        FROM formula_detalle fd
                        JOIN UltimasVersiones uv 
                            ON fd.item_id = uv.item_id AND fd.lote_id = uv.lote_id AND fd.version = uv.max_version
                        JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                        
                        -- 2. EL CAMBIO VA AQUÍ: Validamos que ESA ÚLTIMA VERSIÓN no esté vencida
                        WHERE fd.fecha_vencimiento >= CURRENT_DATE
                        
                        GROUP BY fd.item_id, fd.lote_id
                    )
                    SELECT 
                        cb.lote_id AS lote,
                        ca.nombre AS etapa, 
                        e.nombre AS nombre_empresa,
                        e.costo_maquila,
                        
                        (cb.total_precio_base + cb.total_flete + e.costo_maquila) AS precio_flete_maquila,
                        (cb.total_con_iva + e.costo_maquila) AS precio_iva_maquila,
                        (cb.total_con_iva + cb.total_flete + e.costo_maquila) AS precio_flete_iva_maquila

                    FROM CostosBase cb
                    JOIN catalogo_alimentos ca ON cb.item_id = ca.item_id 
                    JOIN cabecera_lotes cl ON cb.lote_id = cl.lote 
                    JOIN empresas e ON cl.empresa_id = e.id
                    ORDER BY e.nombre, cb.lote_id;
                """
                cur.execute(consulta)
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al generar consolidado de costos: {e}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    def crear_nueva_version(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(MAX(version), 1) 
                    FROM formula_detalle 
                    WHERE item_id = %s AND lote_id = %s;
                """, (item_id, lote_id))
                version_actual = cur.fetchone()[0]
                nueva_version = version_actual + 1

                cur.execute("""
                    UPDATE formula_detalle 
                    SET fecha_vencimiento = CURRENT_DATE 
                    WHERE item_id = %s AND lote_id = %s AND version = %s;
                """, (item_id, lote_id, version_actual))

                cur.execute("""
                    INSERT INTO formula_detalle 
                    (item_id, lote_id, materia_prima_id, cantidad_kg, precio_guardado, iva_guardado, flete_guardado, fecha_creacion, fecha_vencimiento, version)
                    SELECT 
                        item_id, lote_id, materia_prima_id, cantidad_kg, precio_guardado, iva_guardado, flete_guardado, 
                        CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days', %s
                    FROM formula_detalle
                    WHERE item_id = %s AND lote_id = %s AND version = %s;
                """, (nueva_version, item_id, lote_id, version_actual))
                
            conn.commit()
            return nueva_version
        except Exception as e:
            print(f"Error al crear nueva versión de dieta: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    @staticmethod
    def modificar_fecha_vencimiento(item_id, lote_id, version, nueva_fecha):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    UPDATE formula_detalle 
                    SET fecha_vencimiento = %s 
                    WHERE item_id = %s AND lote_id = %s AND version = %s;
                """
                cur.execute(consulta, (nueva_fecha, item_id, lote_id, version))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al modificar fecha de vencimiento: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    @staticmethod
    def obtener_info_versiones(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Obtenemos la lista de versiones y sus fechas
                consulta = """
                    SELECT version, MAX(fecha_vencimiento) as fecha_vencimiento 
                    FROM formula_detalle 
                    WHERE item_id = %s AND lote_id = %s
                    GROUP BY version
                    ORDER BY version ASC;
                """
                cur.execute(consulta, (item_id, lote_id))
                resultados = cur.fetchall()
                
                versiones = []
                # Si no hay registros aún, asumimos la versión 1
                if not resultados:
                    return [{'version': 1, 'fecha_vencimiento': None}]
                    
                columnas = [desc[0] for desc in cur.description]
                for fila in resultados:
                    versiones.append(dict(zip(columnas, fila)))
                return versiones
        except Exception as e:
            print(f"Error al obtener versiones: {e}")
            return [{'version': 1, 'fecha_vencimiento': None}]
        finally:
            conn.close()
    @staticmethod
    def obtener_costos_detallados(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    SELECT 
                        mp.nombre AS insumo,
                        fd.cantidad_kg AS cantidad,
                        COALESCE(fd.precio_guardado, mp.precio_actual_kg) AS precio,
                        COALESCE(fd.iva_guardado, mp.iva, 1.00) AS iva,
                        COALESCE(fd.flete_guardado, mp.flete, 0) AS flete,
                        COALESCE(mp.es_maquila, false) AS es_maquila,
                        ca.nombre AS nombre_dieta
                    FROM 
                        formula_detalle fd
                    JOIN 
                        materias_primas mp ON fd.materia_prima_id = mp.id
                    JOIN 
                        catalogo_alimentos ca ON fd.item_id = ca.item_id
                    WHERE 
                        fd.item_id = %s AND fd.lote_id = %s
                    ORDER BY 
                        mp.nombre;
                """
                cur.execute(consulta, (item_id, lote_id))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener detalle de costos: {e}")
            return []
        finally:
            conn.close()
            
    @staticmethod
    def eliminar_formula_lote(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Borramos todos los registros que coincidan con el item y el lote
                consulta = """
                    DELETE FROM formula_detalle 
                    WHERE item_id = %s AND lote_id = %s;
                """
                cur.execute(consulta, (item_id, lote_id))
            
            # ¡Muy importante hacer commit cuando modificamos/borramos datos!
            conn.commit() 
            return True
            
        except Exception as e:
            print(f"Error al eliminar la fórmula del lote: {e}")
            conn.rollback()  # Revertir cambios si algo sale mal
            return False
            
        finally:
            conn.close()
    
    @staticmethod
    def obtener_receta(item_id, lote_id, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Incluimos fd.materia_prima_id explícitamente
                consulta = """
                    SELECT 
                        fd.id, 
                        fd.materia_prima_id,
                        mp.nombre AS insumo, 
                        fd.cantidad_kg, 
                        COALESCE(fd.es_nucleo, true) AS es_nucleo,
                        COALESCE(fd.baches_nucleo, 6.0) AS baches_nucleo
                    FROM formula_detalle fd
                    JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE fd.item_id = %s AND fd.lote_id = %s AND fd.version = %s
                    ORDER BY mp.nombre ASC;
                """
                cur.execute(consulta, (item_id, lote_id, version))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener receta: {e}")
            return []
        finally:
            conn.close()
    @staticmethod
    def alternar_nucleo(id_registro, estado_nucleo):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE formula_detalle SET es_nucleo = %s WHERE id = %s;", (estado_nucleo, id_registro))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def actualizar_baches_nucleo(id_registro, baches):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE formula_detalle SET baches_nucleo = %s WHERE id = %s;", (baches, id_registro))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def obtener_resumen_totales(item_id, lote_id, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Se agregó: AND fd.version = %s
                consulta = """
                    SELECT 
                        COALESCE(SUM(fd.cantidad_kg), 0) AS total_kg,
                        COALESCE(SUM(fd.cantidad_kg * COALESCE(fd.precio_guardado, mp.precio_actual_kg)), 0) AS total_costo
                    FROM formula_detalle fd
                    JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE fd.item_id = %s AND fd.lote_id = %s AND fd.version = %s;
                """
                cur.execute(consulta, (item_id, lote_id, version))
                columnas = [desc[0] for desc in cur.description]
                resultado = cur.fetchone()
                return dict(zip(columnas, resultado)) if resultado else {'total_kg': 0, 'total_costo': 0}
        except Exception as e:
            print(f"Error al obtener resumen de totales: {e}")
            return {'total_kg': 0, 'total_costo': 0}
        finally:
            conn.close()

    @staticmethod
    def agregar_insumo(item_id, lote_id, materia_prima_id, cantidad_kg, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Agregamos la columna version al INSERT y al SELECT
                consulta = """
                    INSERT INTO formula_detalle 
                        (item_id, lote_id, materia_prima_id, cantidad_kg, precio_guardado, iva_guardado, flete_guardado, version) 
                    SELECT 
                        %s, %s, %s, %s, precio_actual_kg, iva, flete, %s
                    FROM 
                        materias_primas
                    WHERE 
                        id = %s;
                """
                # Pasamos 'version' en el orden correcto
                cur.execute(consulta, (item_id, lote_id, materia_prima_id, cantidad_kg, version, materia_prima_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al agregar insumo con precios congelados: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def actualizar_insumo(id_registro, nueva_cantidad_kg):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE formula_detalle SET cantidad_kg = %s WHERE id = %s",
                    (nueva_cantidad_kg, id_registro),
                )
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def eliminar_insumo(detalle_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_detalle WHERE id = %s;", (detalle_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al eliminar insumo: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def obtener_lotes_disponibles():
        """Obtiene todos los lotes de la tabla maestra para el selector."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Consulta directa a la tabla maestra de lotes
                cur.execute("""
                    SELECT lote 
                    FROM cabecera_lotes 
                    WHERE lote IS NOT NULL 
                    ORDER BY lote ASC;
                """)
                lotes_db = cur.fetchall()
                
                # Agregamos 'LOTE GENERAL' como primera opción y luego todos los lotes de la BD
                lotes_lista = [{'lote': 'LOTE GENERAL'}] + [dict(l) for l in lotes_db]
                
                return lotes_lista
        finally:
            conn.close()
            
    @staticmethod
    def obtener_formulas_por_lote(lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    WITH ResumenVersiones AS (
                        SELECT 
                            fd.item_id,
                            fd.version,
                            COUNT(fd.materia_prima_id) AS num_insumos,
                            SUM(fd.cantidad_kg) AS peso_version,
                            SUM(fd.cantidad_kg * mp.precio_actual_kg) AS costo_version
                        FROM formula_detalle fd
                        JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                        WHERE fd.lote_id = %s
                        GROUP BY fd.item_id, fd.version
                    ),
                    UltimaVersion AS (
                        SELECT item_id, MAX(version) AS max_version
                        FROM ResumenVersiones
                        GROUP BY item_id
                    )
                    SELECT 
                        rv.item_id,
                        uv.max_version AS ultima_version,
                        ca.nombre AS nombre_dieta,
                        
                        STRING_AGG(
                            '<span class="badge bg-primary me-1">V-' || rv.version || '</span>' ||
                            '<span class="badge bg-secondary me-2">' || rv.num_insumos || ' insumos</span>',
                            ' ' ORDER BY rv.version ASC
                        ) AS resumen_insumos_html,
                        
                        MAX(CASE WHEN rv.version = uv.max_version THEN rv.peso_version ELSE 0 END) AS total_peso,
                        MAX(CASE WHEN rv.version = uv.max_version THEN rv.costo_version ELSE 0 END) AS costo_bache

                    FROM ResumenVersiones rv
                    JOIN UltimaVersion uv ON rv.item_id = uv.item_id
                    JOIN catalogo_alimentos ca ON rv.item_id = ca.item_id
                    GROUP BY rv.item_id, uv.max_version, ca.nombre;
                """
                cur.execute(consulta, (lote_id,))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener resumen de fórmulas por lote: {e}")
            return []
        finally:
            conn.close()
    @staticmethod
    def actualizar_dieta(item_id, nombre, rango_semanas):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Usamos item_id porque vimos antes que así se llama tu llave primaria en esta tabla
                consulta = """
                    UPDATE catalogo_alimentos 
                    SET nombre = %s, rango_semanas = %s 
                    WHERE item_id = %s;
                """
                cur.execute(consulta, (nombre, rango_semanas, item_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al actualizar dieta: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def eliminar_dieta(item_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = "DELETE FROM catalogo_alimentos WHERE item_id = %s;"
                cur.execute(consulta, (item_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al eliminar dieta: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            
class FormulaProduccion:

    @staticmethod
    def obtener_produccion_por_lote(item_id, lote_id, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Filtramos por versión
                consulta = """
                    SELECT id, fecha, toneladas, novedad 
                    FROM formula_produccion_diaria 
                    WHERE item_id = %s AND lote_id = %s AND version = %s
                    ORDER BY fecha ASC;
                """
                cur.execute(consulta, (item_id, lote_id, version))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener registros de producción: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def registrar_produccion(item_id, lote_id, fecha, toneladas, novedad, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Se agregó 'version' al insert
                cur.execute(
                    """INSERT INTO formula_produccion_diaria 
                       (item_id, lote_id, fecha, toneladas, novedad, version) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (item_id, lote_id, fecha, toneladas, novedad, version)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al registrar producción diaria: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def eliminar_produccion(id_registro):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def eliminar_produccion(id_registro):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()
    @staticmethod
    def actualizar_produccion(id_registro, toneladas, novedad=''):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    UPDATE formula_produccion_diaria 
                    SET toneladas = %s, novedad = %s 
                    WHERE id = %s;
                """
                cur.execute(consulta, (toneladas, novedad, id_registro))
                conn.commit()
                return True  # <--- ESTA ES LA CLAVE PARA EL MENSAJE DE ÉXITO
        except Exception as e:
            print(f"Error al actualizar BD: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def eliminar_produccion(id_registro):
        """Elimina un registro de producción por su ID."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()
    
    

    
    