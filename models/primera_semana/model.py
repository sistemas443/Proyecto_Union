# models/primera_semana/model.py
from models.base import get_db_connection

def get_lote_id_by_primera_semana(id_registro):
    """
    Identifica a qué lote pertenece un registro específico dentro de la tabla primera_semana.
    Es útil para mantener la integridad relacional al momento de realizar consultas cruzadas
    con la tabla principal de cabecera.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id_lote FROM primera_semana WHERE id = %s", (id_registro,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

def get_aves_iniciales_by_lote(lote_nombre):
    """
    Obtiene el número inicial de pollitas recibidas consultando directamente la cabecera del lote.
    Este valor es fundamental como denominador para los cálculos matemáticos de mortalidad y
    supervivencia durante los primeros siete días.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
        row = cur.fetchone()
        return row[0] if row else 0.0
    finally:
        cur.close()
        conn.close()

def guardar_dato_primera_semana(id_registro, columna, valor, cur):
    """
    Actualiza el valor de una columna específica en la tabla primera_semana.
    Recibe un cursor activo como parámetro, lo que permite ejecutar esta actualización
    dentro de un bloque de transacción más grande sin interrumpir la conexión a la base de datos.
    """
    cur.execute(f'UPDATE primera_semana SET "{columna}" = %s WHERE id = %s', (valor, id_registro))

def count_primera_semana(lote_nombre):
    """
    Verifica la cantidad de registros existentes para un lote en la tabla primera_semana.
    Se utiliza como validación previa para asegurar que la estructura inicial (Día 0 al 7)
    no se genere de manera duplicada en el sistema.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM primera_semana WHERE lote = %s", (lote_nombre,))
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        cur.close()
        conn.close()

def fetch_primera_semana_by_lote(lote_nombre):
    """
    Extrae la secuencia completa de registros de la primera semana para un lote específico.
    Utiliza RealDictCursor para retornar los datos estructurados en formato de diccionario,
    ordenados cronológicamente por su identificador para su correcta visualización.
    """
    import psycopg2.extras  
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT * FROM primera_semana WHERE lote = %s ORDER BY id ASC
        """, (lote_nombre,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()