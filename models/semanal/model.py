# models/semanal/model.py
from models.base import get_db_connection

def get_lote_id_by_semanal(id_semanal):
    """ Busca a qué lote pertenece la celda tocada usando la columna 'id_sem_prod' """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id_lote FROM bd_vargas WHERE id_sem_prod = %s", (id_semanal,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

def get_aves_iniciales(id_lote):
    """ Trae las pollitas recibidas de la cabecera para las fórmulas de producción """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE id = %s", (id_lote,))
        row = cur.fetchone()
        return row[0] if row else 0.0
    finally:
        cur.close()
        conn.close()

def guardar_dato_simple(id_semanal, columna, valor, cur):
    """ Guarda un dato en crudo en la tabla bd_vargas """
    cur.execute(f'UPDATE bd_vargas SET "{columna}" = %s WHERE id_sem_prod = %s', (valor, id_semanal))

def count_semanal(id_lote):
    """ Cuenta si ya existen registros del lote en bd_vargas """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) AS total FROM bd_vargas WHERE id_lote = %s", (id_lote,))
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        cur.close()
        conn.close()

def insert_estructura_semanal(valores):
    """ Inserción masiva inicial de las 110 semanas en bd_vargas """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for val in valores:
            cur.execute(
                "INSERT INTO bd_vargas (lote, id_lote, fecha_fin_sem, sem_prod) VALUES (%s, %s, %s, %s)",
                val
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def fetch_semanal_produccion(id_lote):
    """ Trae el historial completo de producción desde bd_vargas """
    import psycopg2.extras  
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT * FROM bd_vargas WHERE id_lote = %s ORDER BY sem_prod ASC
        """, (id_lote,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()