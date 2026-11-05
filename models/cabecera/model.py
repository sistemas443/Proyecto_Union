# models/cabecera/model.py
import psycopg2.extras
from models.base import get_db_connection

def insert_lote_if_not_exists(lote: str):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO cabecera_lotes (lote) VALUES (%s) ON CONFLICT (lote) DO NOTHING", (lote,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def insert_y_obtener_cabecera(lote: str):
    """
    Crea el lote si no existe y devuelve su cabecera en UNA sola sentencia.

    Hace lo mismo que insert_lote_if_not_exists + fetch_cabecera_by_lote,
    pero con un solo viaje a la base de datos.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            WITH insertado AS (
                INSERT INTO cabecera_lotes (lote) VALUES (%s)
                ON CONFLICT (lote) DO NOTHING
                RETURNING *
            )
            SELECT * FROM insertado
            UNION ALL
            SELECT * FROM cabecera_lotes WHERE lote = %s
            LIMIT 1
        """, (lote, lote))
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else {}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def fetch_cabecera_by_lote(lote: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT * FROM cabecera_lotes WHERE lote = %s", (lote,))
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        cur.close()
        conn.close()

def update_cabecera_column(lote: str, columna: str, valor_db):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Nota: La validación de seguridad de la columna se hará en services.py
        cur.execute(f'UPDATE cabecera_lotes SET "{columna}" = %s WHERE lote = %s', (valor_db, lote))
        conn.commit()
        return True, "Ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cur.close()
        conn.close()