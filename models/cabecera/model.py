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