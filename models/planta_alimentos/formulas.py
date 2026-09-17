import psycopg2
from psycopg2.extras import DictCursor  
from models.base import get_db_connection


class FormulaDetalle:
    @staticmethod
    def obtener_costos_detallados(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    SELECT 
                        mp.nombre AS insumo,
                        fd.cantidad_kg AS cantidad,
                        mp.precio_actual_kg AS precio,
                        COALESCE(mp.iva, 1.00) AS iva,
                        COALESCE(mp.flete, 0) AS flete,
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
    def obtener_receta(item_id, lote_id):
        """Retorna la lista de insumos y cantidades en Kg para la dieta y lote seleccionados."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                consulta = """
                    SELECT 
                        formula_detalle.id, 
                        materias_primas.nombre AS insumo, 
                        formula_detalle.cantidad_kg,
                        formula_detalle.es_nucleo,
                        formula_detalle.baches_nucleo
                    FROM formula_detalle
                    JOIN materias_primas ON formula_detalle.materia_prima_id = materias_primas.id
                    WHERE formula_detalle.item_id = %s AND formula_detalle.lote_id = %s;
                """
                cur.execute(consulta, (item_id, lote_id))
                return cur.fetchall()
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
    def obtener_resumen_totales(item_id, lote_id):
        """Calcula únicamente el total de kilos del bache base (generalmente 1.000 Kg)."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                consulta = """
                    SELECT COALESCE(SUM(cantidad_kg), 0) AS total_kg
                    FROM formula_detalle
                    WHERE item_id = %s AND lote_id = %s;
                """
                cur.execute(consulta, (item_id, lote_id))
                return cur.fetchone()
        finally:
            conn.close()

    @staticmethod
    def agregar_insumo(item_id, lote_id, materia_prima_id, cantidad_kg):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO formula_detalle (item_id, lote_id, materia_prima_id, cantidad_kg) 
                       VALUES (%s, %s, %s, %s)""",
                    (item_id, lote_id, materia_prima_id, cantidad_kg),
                )
                conn.commit()
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
    def eliminar_insumo(id_registro):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_detalle WHERE id = %s", (id_registro,))
                conn.commit()
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
                    SELECT 
                        ca.item_id AS item_id, 
                        ca.nombre AS nombre_dieta, 
                        COUNT(fd.id) AS num_insumos, 
                        COALESCE(SUM(fd.cantidad_kg), 0) AS total_peso,
                        COALESCE(SUM(fd.cantidad_kg * mp.precio_actual_kg), 0) AS costo_bache
                    FROM 
                        catalogo_alimentos ca
                    JOIN 
                        formula_detalle fd ON ca.item_id = fd.item_id
                    JOIN 
                        materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE 
                        fd.lote_id = %s
                    GROUP BY 
                        ca.item_id, ca.nombre
                    ORDER BY 
                        ca.item_id;
                """
                cur.execute(consulta, (lote_id,))
                
                columnas = [desc[0] for desc in cur.description]
                resultados = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
                
                return resultados
        except Exception as e:
            print(f"Error al obtener fórmulas consolidadas por lote: {e}")
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
    def obtener_produccion_por_lote(item_id, lote_id):
        conn = get_db_connection()
        try:
            # Usamos DictCursor directamente
            with conn.cursor(cursor_factory=DictCursor) as cur:
                consulta = """
                    SELECT id, fecha, toneladas, novedad 
                    FROM formula_produccion_diaria 
                    WHERE item_id = %s AND lote_id = %s 
                    ORDER BY fecha ASC;
                    """
                cur.execute(consulta, (item_id, lote_id))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def registrar_produccion(item_id, lote_id, fecha, toneladas, novedad=''):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    INSERT INTO formula_produccion_diaria (item_id, lote_id, fecha, toneladas, novedad)
                    VALUES (%s, %s, %s, %s, %s);
                """
                cur.execute(consulta, (item_id, lote_id, fecha, toneladas, novedad))
                conn.commit()
                return True  # <--- AGREGA ESTO AQUÍ TAMBIÉN
        except Exception as e:
            print(f"Error al insertar en BD: {e}")
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