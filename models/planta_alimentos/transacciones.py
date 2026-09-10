from models.base import get_db_connection
import psycopg2.extras

class RegistroProduccion:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                consulta = """
                    SELECT rp.id, rp.fecha, rp.lote_id, e.nombre AS empresa, ca.nombre AS dieta, 
                           rp.cantidad_baches, rp.toneladas_producidas
                    FROM registro_produccion rp
                    JOIN empresas e ON rp.empresa_id = e.id
                    JOIN catalogo_alimentos ca ON rp.item_id = ca.item_id
                    ORDER BY rp.fecha DESC, rp.id DESC;
                """
                cur.execute(consulta)
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(fecha, lote_id, empresa_id, item_id, cantidad_baches, toneladas_producidas):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO registro_produccion 
                       (fecha, lote_id, empresa_id, item_id, cantidad_baches, toneladas_producidas) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (fecha, lote_id, empresa_id, item_id, cantidad_baches, toneladas_producidas)
                )
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_lotes():
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT lote, COALESCE(tipo_lote, 'PROPIO') AS tipo_lote 
                    FROM cabecera_lotes 
                    ORDER BY tipo_lote ASC, lote DESC;
                """)
                return cur.fetchall()
        finally:
            conn.close()