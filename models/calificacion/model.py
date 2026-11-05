# models/calificacion/model.py
"""Consultas de solo lectura para la calificación de lotes.

Los valores reales salen de bd_vargas (registro semanal de producción);
los de referencia genética, de models.consolidados.guias.
"""

import psycopg2.extras

from models.base import get_db_connection


def fetch_lotes_evaluables():
    """Lotes con al menos una semana que tenga algún dato de producción."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT c.id,
                       c.lote,
                       c.variedad,
                       c.fecha_encasetamiento,
                       c.no_aves_encasetadas,
                       MIN(v.sem_prod) AS primera_semana,
                       MAX(v.sem_prod) AS ultima_semana,
                       COUNT(DISTINCT v.sem_prod) AS semanas
                FROM cabecera_lotes c
                JOIN bd_vargas v ON v.id_lote = c.id
                WHERE v.haa_real IS NOT NULL AND v.haa_real > 0
                GROUP BY c.id, c.lote, c.variedad, c.fecha_encasetamiento, c.no_aves_encasetadas
                ORDER BY c.lote
            """)
            return [dict(fila) for fila in cur.fetchall()]
    finally:
        conn.close()


def fetch_semanas_lote(lote_id):
    """Semanas del lote con HAA registrado (sin HAA no hay calificación)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT sem_prod
                FROM bd_vargas
                WHERE id_lote = %s
                  AND haa_real IS NOT NULL
                  AND haa_real > 0
                ORDER BY sem_prod
            """, (lote_id,))
            return [fila[0] for fila in cur.fetchall()]
    finally:
        conn.close()


def fetch_nombre_lote(lote_id):
    """Nombre del lote a partir de su id."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT lote FROM cabecera_lotes WHERE id = %s", (lote_id,))
            fila = cur.fetchone()
            return fila[0] if fila else None
    finally:
        conn.close()


def fetch_fila_lote_semana(lote_id, semana):
    """Fila de producción del lote en la semana indicada (real + columnas _tab)."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT sem_prod,
                       haa_real,
                       h_av_aloj_tab,
                       conv_acum_real,
                       conv_acum_tab,
                       percent_mort_acum,
                       mort_tab,
                       saldo_ave
                FROM bd_vargas
                WHERE id_lote = %s AND sem_prod = %s
                LIMIT 1
            """, (lote_id, semana))
            fila = cur.fetchone()
            return dict(fila) if fila else None
    finally:
        conn.close()
