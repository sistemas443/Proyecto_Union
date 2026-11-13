# models/primera_semana/dia2.py
"""Acceso a datos de la tabla visual del Día 2 de Primera Semana."""
import psycopg2.extras
from models.base import get_db_connection


def count_dia2(lote_nombre):
    """Cuenta las filas del Día 2 que existen para un lote."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM primera_semana_dia2 WHERE lote = %s", (lote_nombre,))
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def fetch_dia2_by_lote(lote_nombre):
    """Devuelve las filas del Día 2 con los mismos alias que la tabla oficial."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id AS id_diario, lote, fecha AS fecha_dia, semana AS sem,
                   mortalidad, sel, porc_mort_sem, porc_mort_acum, saldo_aves,
                   peso_tabla, peso_real, unif_10_menos, porc_uniformidad,
                   unif_10_mas, coef_variacion, observaciones,
                   consumo_gr_a_tab, consumo_kg, consumo_gr_a_d,
                   cons_k_acum, cons_gr_ave_tab_acum, cons_gr_ave_ac
            FROM primera_semana_dia2
            WHERE lote = %s
            ORDER BY id ASC
            """,
            (lote_nombre,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def fetch_dia2_para_calculo(lote_nombre, cur):
    """Filas mínimas necesarias para el recálculo, usando el cursor del llamador."""
    cur.execute(
        """
        SELECT id, mortalidad, sel, consumo_kg, consumo_gr_a_tab
        FROM primera_semana_dia2
        WHERE lote = %s
        ORDER BY id ASC
        """,
        (lote_nombre,),
    )
    return cur.fetchall()


def get_lote_id_by_dia2(id_registro):
    """Obtiene el id del lote al que pertenece una fila del Día 2."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id_lote FROM primera_semana_dia2 WHERE id = %s", (id_registro,))
        fila = cur.fetchone()
        return fila[0] if fila else None
    finally:
        cur.close()
        conn.close()


def insertar_estructura_dia2(valores, cur):
    """Inserta las 8 filas del Día 2 en una sola transacción."""
    cur.executemany(
        """
        INSERT INTO primera_semana_dia2 (
            lote, id_lote, fecha, semana,
            mortalidad, sel, porc_mort_sem, porc_mort_acum, saldo_aves,
            peso_tabla, peso_real, unif_10_menos, porc_uniformidad, unif_10_mas,
            coef_variacion, observaciones,
            consumo_gr_a_tab, consumo_kg, consumo_gr_a_d,
            cons_k_acum, cons_gr_ave_tab_acum, cons_gr_ave_ac
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        valores,
    )


def actualizar_campo_dia2(id_registro, columna, valor, cur):
    """Actualiza una columna específica de una fila del Día 2."""
    cur.execute(
        f'UPDATE primera_semana_dia2 SET "{columna}" = %s WHERE id = %s',
        (valor, id_registro),
    )


def eliminar_dia2_por_lote(lote_nombre, cur):
    """Elimina todas las filas del Día 2 de un lote."""
    cur.execute("DELETE FROM primera_semana_dia2 WHERE lote = %s", (lote_nombre,))
    return cur.rowcount
