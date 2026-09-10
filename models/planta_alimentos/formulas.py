from models.base import get_db_connection
import psycopg2.extras

class FormulaDetalle:
    @staticmethod
    def obtener_receta(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                consulta = """
                    SELECT 
                        fd.id, 
                        mp.nombre AS insumo, 
                        fd.cantidad_kg, 
                        mp.precio_actual_kg,
                        (fd.cantidad_kg * mp.precio_actual_kg) AS costo_total_insumo
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
    def agregar_insumo(item_id, lote_id, materia_prima_id, cantidad_kg):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO formula_detalle (item_id, lote_id, materia_prima_id, cantidad_kg) 
                       VALUES (%s, %s, %s, %s)""",
                    (item_id, lote_id, materia_prima_id, cantidad_kg)
                )
                conn.commit()
        finally:
            conn.close()