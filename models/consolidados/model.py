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


def fetch_variedades_por_lote(lotes: list) -> dict:
    """Devuelve {lote: variedad} consultando la cabecera de lotes."""
    if not lotes:
        return {}
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT lote, variedad FROM cabecera_lotes WHERE lote = ANY(%s)", (lotes,))
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        cur.close()
        conn.close()


def fetch_huevos_semanal() -> list:
    """Devuelve sem_prod, lote y prod_huevo_sem ordenado por semana y lote."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT sem_prod, lote, prod_huevo_sem
            FROM bd_vargas
            ORDER BY sem_prod, lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'prod_huevo_sem': r[2]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_huevos_semanal_detalle() -> list:
    """Devuelve la matriz con metadata de cabecera (fecha y aves encasetadas)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.prod_huevo_sem,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'prod_huevo_sem': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_kilos_semanal_detalle() -> list:
    """Devuelve sem_prod, lote, kg_sem y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.kg_sem,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'kg_sem': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_mortalidad_semanal_detalle() -> list:
    """Devuelve sem_prod, lote, mort_sem y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.mort_sem,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'mort_sem': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_peso_aves() -> list:
    """Devuelve sem_prod, lote, peso_ave_real y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.peso_ave_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'peso_ave_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_saldo_aves() -> list:
    """Devuelve sem_prod, lote, saldo_ave y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.saldo_ave,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'saldo_ave': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_porc_produccion() -> list:
    """Devuelve sem_prod, lote, porcentaje_prod_real y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.porcentaje_prod_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'porcentaje_prod_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_consumo_agua() -> list:
    """Devuelve sem_prod, lote, cons_agua_real y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.cons_agua_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'cons_agua_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_mort_acumulada() -> list:
    """Devuelve sem_prod, lote, percent_mort_acum y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.percent_mort_acum,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'percent_mort_acum': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_mort_semanal() -> list:
    """Devuelve sem_prod, lote, percent_mort_sem y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.percent_mort_sem,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'percent_mort_sem': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_haa() -> list:
    """Devuelve sem_prod, lote, h_av_aloj_real y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.h_av_aloj_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'h_av_aloj_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_gramos_aves() -> list:
    """Devuelve sem_prod, lote, kg_sem, saldo_ave y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.kg_sem, b.saldo_ave,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'kg_sem': r[2], 'saldo_ave': r[3],
             'fecha_recepcion': r[4], 'aves_enc': r[5]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_conv_semanal() -> list:
    """Devuelve sem_prod, lote, conv_sem_real y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.conv_sem_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'conv_sem_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_conversion_acumulada() -> list:
    """Devuelve sem_prod, lote, conv_acum_real y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.conv_acum_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'conv_acum_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_masa_semanal() -> list:
    """Devuelve sem_prod, lote, prod_huevo_real, huevo_acum y metadata.
    
    Para calcular Masa Huevo Semanal segun Excel H16:
    - Semana 18: masa = produccion * huevo_acum (de esa misma semana)
    - Semana n > 18: si produccion=0 -> "" ; si no: masa = produccion * (huevo_acum_n - huevo_acum_{n-1})
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.prod_huevo_real, b.huevo_acum,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'prod_huevo_real': r[2],
             'huevo_acum': r[3], 'fecha_recepcion': r[4], 'aves_enc': r[5]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_masa_acumulada() -> list:
    """Devuelve sem_prod, lote, masa_huevo_real_acum y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.masa_huevo_real_acum,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'masa_huevo_real_acum': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_primera_semana_levante() -> list:
    """Devuelve dia (0-7), lote, peso, uniformidad, consumo, mortalidad diaria y metadata.

    Dia = fecha - fecha_recepcion. Solo dias 0 a 7. Mortalidad desde diario.
    Uniformidad: se toma de semanal_levante.unif_porc_unif (columna %Unif real),
    asignando una semana por dia: dia 0 -> sem 1, dia 1 -> sem 2, ..., dia 7 -> sem 8.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT (p.fecha - c.fecha_recepcion) AS dia, p.lote,
                   p.peso_real,
                   sl.unif_porc_unif AS porc_uniformidad,
                   p.consumo_gr_a_d, d.mortalidad,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM primera_semana p
            LEFT JOIN cabecera_lotes c ON c.id = p.id_lote
            LEFT JOIN data_diario d ON d.id_lote = p.id_lote AND d.fecha_dia = p.fecha::text
            LEFT JOIN (
                SELECT id_lote, sem, MAX(unif_porc_unif) AS unif_porc_unif
                FROM semanal_levante
                GROUP BY id_lote, sem
            ) sl ON sl.id_lote = p.id_lote
                AND sl.sem = (p.fecha - c.fecha_recepcion) + 1
            WHERE c.fecha_recepcion IS NOT NULL
              AND (p.fecha - c.fecha_recepcion) BETWEEN 0 AND 7
            ORDER BY dia, p.lote
        """)
        return [
            {'dia': r[0], 'lote': r[1], 'peso_real': r[2],
             'porc_uniformidad': r[3],
             'consumo_gr_a_d': r[4], 'mortalidad': r[5],
             'fecha_recepcion': r[6], 'aves_enc': r[7]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_levante_lotes() -> list:
    """Devuelve los lotes con datos en semanal_levante y su metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT s.lote, c.fecha_recepcion, c.no_pollitas_recibidas
            FROM semanal_levante s
            LEFT JOIN cabecera_lotes c ON c.id = s.id_lote
            ORDER BY s.lote
        """)
        return [
            {'lote': r[0], 'fecha_recepcion': r[1], 'aves_enc': r[2]}
            for r in cur.fetchall() if r[0]
        ]
    finally:
        cur.close()
        conn.close()


def fetch_aves_enc_semana17(lotes: list) -> dict:
    """Devuelve {lote: saldo_aves} de data_diario donde sem = '17' (semana 17).
    
    Se usa para el encabezado AVES ENC en todas las vistas de consolidados.
    Toma el último registro de la semana 17 para cada lote.
    """
    if not lotes:
        return {}
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT d.lote, d.saldo_aves
            FROM data_diario d
            WHERE d.lote = ANY(%s) AND d.sem = '17'
            ORDER BY d.lote, d.dias DESC
        """, (lotes,))
        resultado = {}
        for r in cur.fetchall():
            if r[0] not in resultado:
                resultado[r[0]] = r[1]
        return resultado
    finally:
        cur.close()
        conn.close()


def fetch_levante_consolidado(lotes: list) -> list:
    """Promedios/sumas semanales de levante para los lotes dados."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT sem,
                   AVG(peso_real),
                   AVG(ganancia_ave),
                   AVG(unif_porc_unif),
                   AVG(cons_gr_ave_ao),
                   AVG(cons_k_acum),
                   AVG(conv_sem),
                   SUM(mort), SUM(saldo_aves), COUNT(DISTINCT lote),
                   AVG(porc_mort_acm)
            FROM semanal_levante
            WHERE lote = ANY(%s)
            GROUP BY sem
            ORDER BY sem
        """, (lotes,))
        cols = ['sem', 'peso_real', 'ganancia_ave',
                'unif', 'grad_real', 'cons_acum',
                'conv_real', 'mort', 'saldo', 'nro', 'mort_acum']
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def fetch_levante_consumo(lotes: list) -> list:
    """Devuelve sem, lote y consumo g/ave/dia para la matriz de consumo."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT sem, lote, cons_gr_ave_ao
            FROM semanal_levante
            WHERE lote = ANY(%s)
            ORDER BY sem, lote
        """, (lotes,))
        return [
            {'sem': r[0], 'lote': r[1], 'consumo': r[2]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_peso_huevo() -> list:
    """Devuelve sem_prod, lote, peso_huevo_real y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.peso_huevo_real,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'peso_huevo_real': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_rotura_huevo() -> list:
    """Devuelve sv (semana), lote, roto (% rotura) y metadata."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT c.sv, c.lote, c.roto,
                   cab.fecha_recepcion, cab.no_pollitas_recibidas
            FROM clasificacion_produccion c
            LEFT JOIN cabecera_lotes cab ON cab.id = c.id_lote
            ORDER BY c.sv, c.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'roto': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


CATEGORIAS_CLASIFICACION = {
    'JUM': 'porc_sem_jum',
    'EXTRA': 'porc_sem_extra',
    'AA': 'porc_sem_aa',
    'A': 'porc_sem_a',
    'B': 'porc_sem_b',
    'C': 'porc_sem_c',
    'SUCIO': 'porc_sem_sucio',
    'YEMA': 'porc_sem_yema',
    'ROTURA': 'roto',
    'SEGUNDAS': 'porc_sem_segundas',
}


def fetch_acumulados_clasificadora(categoria: str) -> list:
    """Devuelve sv, lote y % de la categoria (whitelist validada)."""
    columna = CATEGORIAS_CLASIFICACION.get(categoria)
    if not columna:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT c.sv, c.lote, c.{columna},
                   cab.fecha_recepcion, cab.no_pollitas_recibidas
            FROM clasificacion_produccion c
            LEFT JOIN cabecera_lotes cab ON cab.id = c.id_lote
            ORDER BY c.sv, c.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'valor': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def fetch_uniformidad() -> list:
    """Devuelve sem_prod, lote, unif y metadata de cabecera."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.sem_prod, b.lote, b.unif,
                   c.fecha_recepcion, c.no_pollitas_recibidas
            FROM bd_vargas b
            LEFT JOIN cabecera_lotes c ON c.id = b.id_lote
            ORDER BY b.sem_prod, b.lote
        """)
        return [
            {'sem_prod': r[0], 'lote': r[1], 'unif': r[2],
             'fecha_recepcion': r[3], 'aves_enc': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()
