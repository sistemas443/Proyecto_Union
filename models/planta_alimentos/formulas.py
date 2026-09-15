import psycopg2
from psycopg2.extras import DictCursor  
from models.base import get_db_connection


class FormulaDetalle:

    @staticmethod
    def obtener_receta(item_id, lote_id):
        """Retorna la lista de insumos y cantidades en Kg para la dieta y lote seleccionados."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                consulta = """
                    SELECT 
                        fd.id, 
                        mp.nombre AS insumo, 
                        fd.cantidad_kg
                    FROM formula_detalle fd
                    JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE fd.item_id = %s AND fd.lote_id = %s
                    ORDER BY fd.cantidad_kg DESC;
                """
                cur.execute(consulta, (item_id, lote_id))
                return cur.fetchall()
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
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT lote_id AS lote 
                    FROM formula_detalle 
                    WHERE lote_id IS NOT NULL AND lote_id != ''
                    ORDER BY lote_id ASC;
                """)
                lotes = cur.fetchall()
                return lotes if lotes else [{'lote': '69-7'}, {'lote': '69-10'}, {'lote': '72-11'}]
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
                    SELECT id, fecha, toneladas 
                    FROM formula_produccion_diaria
                    WHERE item_id = %s AND lote_id = %s
                    ORDER BY fecha ASC;
                """
                cur.execute(consulta, (item_id, lote_id))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def registrar_produccion(item_id, lote_id, fecha, toneladas):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO formula_produccion_diaria (item_id, lote_id, fecha, toneladas)
                    VALUES (%s, %s, %s, %s);
                """, (item_id, lote_id, fecha, toneladas))
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
    def eliminar_produccion(id_registro):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()
    @staticmethod
    def actualizar_produccion(id_registro, toneladas):
        """Actualiza la cantidad de toneladas producidas de un registro."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE formula_produccion_diaria SET toneladas = %s WHERE id = %s;",
                    (toneladas, id_registro)
                )
                conn.commit()
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