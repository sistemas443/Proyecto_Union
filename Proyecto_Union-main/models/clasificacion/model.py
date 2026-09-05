# models/clasificacion/model.py
import psycopg2.extras
from models.base import get_db_connection

def count_clasificacion(id_lote):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) AS total FROM clasificacion_produccion WHERE id_lote = %s", (id_lote,))
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        cur.close()
        conn.close()

def insert_estructura(valores):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        psycopg2.extras.execute_values(
            cur, "INSERT INTO clasificacion_produccion (lote, id_lote, sv) VALUES %s", valores
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def fetch_clasificacion_all(id_lote):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute('SELECT * FROM clasificacion_produccion WHERE id_lote = %s ORDER BY sv ASC', (id_lote,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def update_columna(id_reg, columna, valor_db):
    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        cur.execute(f'UPDATE clasificacion_produccion SET "{columna}" = %s WHERE id = %s', (valor_db, id_reg))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()