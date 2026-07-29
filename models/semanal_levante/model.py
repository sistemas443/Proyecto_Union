# models/semanal_levante/model.py
from models.base import get_db_connection

def get_lote_id_by_semanal(id_semanal):
    """ Busca a qué lote pertenece la celda tocada usando la columna 'id' """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id_lote FROM semanal_levante WHERE id = %s", (id_semanal,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

def get_aves_iniciales(id_lote):
    """ Trae las pollitas recibidas de la cabecera """
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
    """ Guarda un dato en crudo traduciendo los nombres del HTML a la BD real de Levante """
    col_db = columna
    
    if columna == 'mort_sem': col_db = 'mort'
    elif columna == 'mort_select_sem': col_db = 'sel'
    elif columna == 'mort_venta': col_db = 'otros'
    elif columna == 'mort_tab': col_db = 'porc_tab'          
    elif columna == 'peso_ave_real': col_db = 'peso_real'
    elif columna == 'peso_ave_tab': col_db = 'peso_tab'
    elif columna == 'cons_agua_real': col_db = 'agua_real'
    elif columna == 'cons_agua_tab': col_db = 'agua_tabla'
    elif columna == 'observaciones_lev': col_db = 'observaciones'
    
    cur.execute(f'UPDATE semanal_levante SET "{col_db}" = %s WHERE id = %s', (valor, id_semanal))

def count_semanal(id_lote):
    """ Cuenta si ya existen registros en semanal_levante """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) AS total FROM semanal_levante WHERE id_lote = %s", (id_lote,))
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        cur.close()
        conn.close()

def insert_estructura_semanal(valores):
    """ Inserción masiva usando las columnas reales 'id_lote' y 'sem' """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for val in valores:
            cur.execute(
                "INSERT INTO semanal_levante (lote, id_lote, fecha_fin_sem, sem) VALUES (%s, %s, %s, %s)",
                val
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def fetch_semanal_levante(id_lote):
    """ Trae los registros mapeando las columnas físicas de tu base de datos al HTML """
    import psycopg2.extras  
    conn = get_db_connection()
    
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT 
                id AS id_semanal,                  
                sem,                    
                fecha_fin_sem,
                cons_tab,                            
                cons_real,     
                cons_kilos_real,
                cons_kilos_ajustado,  /* 🚀 AQUÍ ESTÁ LA NUEVA COLUMNA */
                cons_k_acum,
                cons_gr_ave_tab,
                cons_gr_ave_ao,
                mort AS mort_sem,                      
                sel AS mort_select_sem,        
                otros AS mort_venta,                  
                acu AS salidas_acum,                  
                porc_mort_sem AS percent_mort_sem,    
                porc_mort_acm AS percent_mort_acum,   
                porc_sel_sem AS percent_select_sem,   
                porc_ms_acu AS percent_mort_and_select_acum, 
                porc_tab AS mort_tab,                
                saldo_aves AS saldo_ave,              
                peso_tab AS peso_ave_tab,             
                peso_real AS peso_ave_real,           
                unif_porc_uni,
                unif_10_menos,
                unif_porc_unif,
                unif_10_mas,
                unif_cv,
                t_tarso,
                t_tarso_r,
                agua_real AS cons_agua_real,          
                agua_tabla AS cons_agua_tab,          
                observaciones AS observaciones_lev,   
                marca_tipo_de,
                conv_sem,
                conv_sem_tab,
                ganancia_ave_dia,
                ganancia_ave,
                porc_cumpl_ganan,
                porc_cumpl_cons
            FROM semanal_levante
            WHERE id_lote = %s
            ORDER BY sem ASC
        """, (id_lote,))
        
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()