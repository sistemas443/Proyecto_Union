"""SQL crudo de Consolidados L+P. Lectura solamente."""
from models.base import get_db_connection


def fetch_primer_huevo_por_lote() -> list:
    """Devuelve por lote: nombre, fecha de recepción y fecha del primer
    huevo (primer día con producción > 0 en data_diario)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT c.lote, c.fecha_recepcion, MIN(d.fecha_dia) AS fecha_primer_huevo
            FROM cabecera_lotes c
            JOIN data_diario d ON d.id_lote = c.id
            WHERE c.fecha_recepcion IS NOT NULL
              AND d.produccion IS NOT NULL AND d.produccion > 0
            GROUP BY c.lote, c.fecha_recepcion
            ORDER BY c.lote
        """)
        return [
            {'lote': r[0], 'fecha_recepcion': r[1], 'fecha_primer_huevo': r[2]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_ultimos_indicadores_por_lote() -> list:
    """Devuelve por lote la ultima semana con al menos un indicador valido.

    Usa OR para no saltarse una semana completa cuando solo falta un
    indicador. Los NULL restantes se muestran como vacio en la tabla.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT ON (lote) lote, sem_prod, haa_real, gr_por_huevo,
                   gr_ave_dia_graf, porcentaje_mort_acum_graf
            FROM bd_vargas
            WHERE haa_real IS NOT NULL
               OR gr_por_huevo IS NOT NULL
               OR gr_ave_dia_graf IS NOT NULL
               OR porcentaje_mort_acum_graf IS NOT NULL
            ORDER BY lote, sem_prod DESC
        """)
        return [
            {'lote': r[0], 'sem_prod': r[1], 'haa_real': r[2],
             'gr_por_huevo': r[3], 'gr_ave_dia_graf': r[4],
             'porcentaje_mort_acum_graf': r[5]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_primer_dia_por_lote() -> list:
    """Devuelve por lote el primer dia (columna dias) con produccion > 0."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT lote, MIN(dias) AS dia_primer
            FROM data_diario
            WHERE dias IS NOT NULL
              AND produccion IS NOT NULL AND produccion > 0
            GROUP BY lote
            ORDER BY lote
        """)
        return [{'lote': r[0], 'dia_primer': r[1]} for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def fetch_matriz_dias(dia_min: int, dia_max: int) -> list:
    """Devuelve las filas diarias en el rango para armar la matriz."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT lote, sem, dias, produccion, saldo_aves
            FROM data_diario
            WHERE dias BETWEEN %s AND %s
            ORDER BY dias, lote
        """, (dia_min, dia_max))
        return [
            {'lote': r[0], 'sem': r[1], 'dias': r[2],
             'produccion': r[3], 'saldo_aves': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()
