# models/diario/model.py
import psycopg2.extras
from models.base import get_db_connection

def count_diario_lote(id_lote):
    """Cuenta cuántos registros diarios existen para un lote específico."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM data_diario WHERE id_lote = %s", (id_lote,))
        total = cur.fetchone()[0]
        return total
    except Exception as e:
        print(f"[ERROR count_diario_lote]: {str(e)}")
        return 0
    finally:
        cur.close()
        conn.close()


def fetch_diario_por_lote(id_lote, limite=None):
    """Trae los registros diarios formateados buscando estrictamente por el ID DEL LOTE."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # SE AGREGA LA COLUMNA 'produccion' AL FINAL DEL SELECT PARA SOLUCIONAR EL ERROR DE JINJA2
    query = """
        SELECT id_diario, id_lote, lote, fecha_dia, dias, sem,
               mortalidad, sel, consumo_kg, consumo_gr_a_tab, otros, peso_real, peso_tabla, observaciones,
               saldo_aves, consumo_gr_a_d, percent_diario_prod, prom_ave_dia_cc, consumo_agua,
               porc_mort_sem, porc_mort_acum, cons_k_acum, cons_gr_ave_tab_acum, cons_gr_ave_ac,
               produccion
        FROM data_diario
        WHERE id_lote = %s
        ORDER BY dias ASC
    """
    
    if limite:
        query += f" LIMIT {limite}"
        
    try:
        print(f"\n[MODELO DIARIO] Ejecutando SELECT limpio para id_lote = {id_lote}")
        cur.execute(query, (id_lote,))
        rows = cur.fetchall()
        print(f"[MODELO DIARIO] ¡ÉXITO! Filas encontradas físicamente: {len(rows)}")
        return rows
    except Exception as e:
        print(f"[ERROR fetch_diario_por_lote]: {str(e)}")
        return []
    finally:
        cur.close()
        conn.close()

def insert_estructura_masiva(valores):
    """Inserta las 770 filas consecutivas y limpias para el lote."""
    if not valores:
        return

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.executemany("""
            INSERT INTO data_diario (
                lote, id_lote, fecha, dias, sem, 
                mortalidad, sel, consumo_kg, consumo_gr_a_tab, otros, peso_real
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, valores)
        
        conn.commit()
        print(f"[BD DIARIO] Éxito: Se insertaron {len(valores)} días estructurados en orden.")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR INSERCIÓN DIARIO MASIVO]: {str(e)}")
    finally:
        cur.close()
        conn.close()


def get_lote_id_by_diario(id_reg):
    """Busca el id_lote correspondiente a una fila de la tabla diaria."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT id_lote FROM data_diario WHERE id_diario = %s", (id_reg,))
        row = cur.fetchone()
        return row['id_lote'] if row else None
    except Exception as e:
        print(f"[ERROR get_lote_id_by_diario]: {str(e)}")
        return None
    finally:
        cur.close()
        conn.close()


def get_historial_para_calculo(id_lote, cur):
    """Trae el historial completo bloqueando las filas para evitar colisiones matemáticas."""
    # SE AGREGA 'produccion' AQUÍ TAMBIÉN PARA MANTENER LA INTEGRIDAD DEL CÁLCULO
    query = """
        SELECT id_diario, mortalidad, sel, consumo_kg, consumo_gr_a_tab, otros, peso_real, dias, produccion
        FROM data_diario 
        WHERE id_lote = %s 
        ORDER BY dias ASC 
        FOR UPDATE
    """
    cur.execute(query, (id_lote,))
    return cur.fetchall()


def guardar_dato_simple(id_reg, columna, valor, cur):
    """Guarda una modificación de celda directa e individual."""
    cur.execute(f'UPDATE data_diario SET "{columna}" = %s WHERE id_diario = %s', (valor, id_reg))


def guardar_calculos_masivos(valores_update, cur):
    """Inyecta el recálculo total de la cascada de los 770 días de forma ultra veloz."""
    psycopg2.extras.execute_values(
        cur,
        """
        UPDATE data_diario AS d 
        SET porc_mort_sem = v.porc_mort_sem, 
            porc_mort_acum = v.porc_mort_acum, 
            saldo_aves = v.saldo_aves,
            consumo_gr_a_d = v.real_gr_ave,
            cons_k_acum = v.k_acum,
            cons_gr_ave_tab_acum = v.gr_ave_tab_acum,
            cons_gr_ave_ac = v.gr_ave_real_acum
        FROM (VALUES %s) AS v(
            porc_mort_sem, porc_mort_acum, saldo_aves, 
            real_gr_ave, k_acum, gr_ave_tab_acum, gr_ave_real_acum, id_diario
        ) 
        WHERE d.id_diario = v.id_diario
        """,
        valores_update,
        template="(%s::numeric, %s::numeric, %s::integer, %s::numeric, %s::numeric, %s::numeric, %s::numeric, %s::integer)"
    )