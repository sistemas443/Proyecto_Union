# models/clasificacion/services.py
from models.base import parse_empty, get_db_connection
from models.clasificacion.schemas import COLUMNAS_PERMITIDAS
from models.clasificacion import model
from models.cabecera.model import fetch_cabecera_by_lote

def generar_estructura_clasificacion(lote_nombre, id_lote):
    if not id_lote or not lote_nombre: return
    if model.count_clasificacion(id_lote) > 0: return

    valores = [(lote_nombre, id_lote, sv) for sv in range(18, 110)]
    model.insert_estructura(valores)

def get_clasificacion_all(lote_nombre: str = ''):
    if not lote_nombre or lote_nombre == 'VACIO': return []
    
    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera: return []
    
    id_lote = cabecera['id']
    rows = model.fetch_clasificacion_all(id_lote)
    
    if len(rows) == 0:
        generar_estructura_clasificacion(lote_nombre, id_lote)
        rows = model.fetch_clasificacion_all(id_lote)
        
    return rows

def update_clasificacion_field(id_reg: int, columna: str, valor: str) -> bool:
    if columna not in COLUMNAS_PERMITIDAS: return False
    
    valor_db = parse_empty(valor)
    
    exito = model.update_columna(id_reg, columna, valor_db)
    if not exito: return False

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        columnas_fila = [
            'clas_jum', 'clas_extra', 'clas_aa', 'clas_a', 'clas_b', 'clas_c',
            'clas_pipo', 'clas_sucio', 'clas_totiao', 'clas_yema', 'clas_segundas', 'clas_ttl'
        ]
        
        if columna in columnas_fila:
            # 2. RECALCULAR FILA ACTUAL
            cur.execute("""
                SELECT clas_jum, clas_extra, clas_aa, clas_a, clas_b, clas_c,
                       clas_pipo, clas_sucio, clas_totiao, clas_yema
                FROM clasificacion_produccion WHERE id = %s
            """, (id_reg,))
            row = cur.fetchone()
            
            if row:
                # Determinamos si la fila tiene al menos un dato (aunque sea 0)
                tiene_datos = any(x is not None for x in row)
                
                if tiene_datos:
                    vals = [float(x) if x is not None else 0.0 for x in row]
                    sucio, totiao, yema = vals[7], vals[8], vals[9]
                    
                    val_segundas = int(sucio + totiao + yema)
                    val_ttl = int(sum(vals))
                    
                    def calc_porc(valor, total):
                        if total > 0: return round((valor / total) * 100, 2)
                        return 0.00

                    p_jum = calc_porc(vals[0], val_ttl)
                    p_extra = calc_porc(vals[1], val_ttl)
                    p_aa = calc_porc(vals[2], val_ttl)
                    p_a = calc_porc(vals[3], val_ttl)
                    p_b = calc_porc(vals[4], val_ttl)
                    p_c = calc_porc(vals[5], val_ttl)
                    p_pipo = calc_porc(vals[6], val_ttl)
                    p_sucio = calc_porc(sucio, val_ttl)
                    p_totiao = calc_porc(totiao, val_ttl)
                    p_yema = calc_porc(yema, val_ttl)
                    p_seg = calc_porc(val_segundas, val_ttl)
                    
                    # NUEVO CÁLCULO: Suma de JUM, Extra y AA
                    p_h_grande = round(p_jum + p_extra + p_aa, 2)
                else:
                    val_segundas = val_ttl = None
                    p_jum = p_extra = p_aa = p_a = p_b = p_c = p_pipo = p_sucio = p_totiao = p_yema = p_seg = p_h_grande = None
                
                cur.execute("""
                    UPDATE clasificacion_produccion 
                    SET clas_segundas = %s, clas_ttl = %s,
                        porc_sem_jum = %s, porc_sem_extra = %s, porc_sem_aa = %s, porc_sem_a = %s, 
                        porc_sem_b = %s, porc_sem_c = %s, porc_sem_pipo = %s, porc_sem_sucio = %s, 
                        porc_sem_totiao = %s, porc_sem_yema = %s, porc_sem_segundas = %s,
                        porc_h_grande = %s
                    WHERE id = %s
                """, (
                    val_segundas, val_ttl,
                    p_jum, p_extra, p_aa, p_a, p_b, p_c, p_pipo, p_sucio, p_totiao, p_yema, p_seg,
                    p_h_grande,
                    id_reg
                ))
                
            # 3. RECALCULAR TODOS LOS ACUMULADOS EN CASCADA
            cur.execute("SELECT id_lote FROM clasificacion_produccion WHERE id = %s", (id_reg,))
            id_lote = cur.fetchone()[0]
            
            cur.execute("""
                SELECT id, clas_ttl, clas_jum, clas_extra, clas_aa, clas_a, clas_b, clas_c, 
                       clas_pipo, clas_sucio, clas_totiao, clas_yema, clas_segundas
                FROM clasificacion_produccion 
                WHERE id_lote = %s ORDER BY sv ASC
            """, (id_lote,))
            filas_lote = cur.fetchall()
            
            acum = { 'jum': 0.0, 'extra': 0.0, 'aa': 0.0, 'a': 0.0, 'b': 0.0, 'c': 0.0, 
                     'pipo': 0.0, 'sucio': 0.0, 'totiao': 0.0, 'yema': 0.0, 'segundas': 0.0, 'total': 0.0 }
            
            valores_update = []
            
            for f in filas_lote:
                f_id = f[0]
                c_ttl = f[1] # Mantenemos el valor original para validar si es None
                
                acum['jum'] += float(f[2] or 0)
                acum['extra'] += float(f[3] or 0)
                acum['aa'] += float(f[4] or 0)
                acum['a'] += float(f[5] or 0)
                acum['b'] += float(f[6] or 0)
                acum['c'] += float(f[7] or 0)
                acum['pipo'] += float(f[8] or 0)
                acum['sucio'] += float(f[9] or 0)
                acum['totiao'] += float(f[10] or 0)
                acum['yema'] += float(f[11] or 0)
                acum['segundas'] += float(f[12] or 0)
                acum['total'] += float(c_ttl or 0)
                
                # Nuevo freno: Guardar el acumulado si la semana tiene datos (aunque sea 0)
                if c_ttl is not None:
                    v_jum = int(acum['jum'])
                    v_extra = int(acum['extra'])
                    v_aa = int(acum['aa'])
                    v_a = int(acum['a'])
                    v_b = int(acum['b'])
                    v_c = int(acum['c'])
                    v_pipo = int(acum['pipo'])
                    v_sucio = int(acum['sucio'])
                    v_totiao = int(acum['totiao'])
                    v_yema = int(acum['yema'])
                    v_segundas = int(acum['segundas'])
                    v_total = int(acum['total'])
                    
                    def calc_p_acu(val_acu):
                        return round((val_acu / v_total) * 100, 2) if c_ttl > 0 and v_total > 0 else 0.00
                        
                    pa_jum = calc_p_acu(v_jum)
                    pa_extra = calc_p_acu(v_extra)
                    pa_aa = calc_p_acu(v_aa)
                    pa_a = calc_p_acu(v_a)
                    pa_b = calc_p_acu(v_b)
                    pa_c = calc_p_acu(v_c)
                    pa_pipo = calc_p_acu(v_pipo)
                    pa_sucio = calc_p_acu(v_sucio)
                    pa_totiao = calc_p_acu(v_totiao)
                    pa_yema = calc_p_acu(v_yema)
                    pa_segundas = calc_p_acu(v_segundas)
                else:
                    v_jum = v_extra = v_aa = v_a = v_b = v_c = v_pipo = v_sucio = v_totiao = v_yema = v_segundas = v_total = None
                    pa_jum = pa_extra = pa_aa = pa_a = pa_b = pa_c = pa_pipo = pa_sucio = pa_totiao = pa_yema = pa_segundas = None
                
                valores_update.append((
                    v_jum, v_extra, v_aa, v_a, v_b, v_c, v_pipo, v_sucio, v_totiao, v_yema, v_segundas, v_total,
                    pa_jum, pa_extra, pa_aa, pa_a, pa_b, pa_c, pa_pipo, pa_sucio, pa_totiao, pa_yema, pa_segundas,
                    f_id
                ))
            
            if valores_update:
                cur.executemany("""
                    UPDATE clasificacion_produccion SET 
                        acum_jum = %s, acum_extra = %s, acum_aa = %s, acum_a = %s, acum_b = %s, acum_c = %s, 
                        acum_pipo = %s, acum_sucio = %s, acum_totiao = %s, acum_yema = %s, acum_segundas = %s, acum_total = %s,
                        porc_acu_jum = %s, porc_acu_extra = %s, porc_acu_aa = %s, porc_acu_a = %s, porc_acu_b = %s, porc_acu_c = %s, 
                        porc_acu_pipo = %s, porc_acu_sucio = %s, porc_acu_totiao = %s, porc_acu_yema = %s, porc_acu_segundas = %s
                    WHERE id = %s
                """, valores_update)
                
        conn.commit()
    except Exception as e:
        print(f"[ERROR CÁLCULO CLASIFICACIÓN]: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    return True

def recalcular_lote_completo_clasificacion(id_lote):
    from models.base import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, clas_jum, clas_extra, clas_aa, clas_a, clas_b, clas_c,
                   clas_pipo, clas_sucio, clas_totiao, clas_yema
            FROM clasificacion_produccion 
            WHERE id_lote = %s ORDER BY sv ASC
        """, (id_lote,))
        filas = cur.fetchall()

        acum = { 'jum': 0.0, 'extra': 0.0, 'aa': 0.0, 'a': 0.0, 'b': 0.0, 'c': 0.0, 
                 'pipo': 0.0, 'sucio': 0.0, 'totiao': 0.0, 'yema': 0.0, 'segundas': 0.0, 'total': 0.0 }
        
        for f in filas:
            id_reg = f[0]
            row = f[1:11]
            tiene_datos = any(x is not None for x in row)
            
            if tiene_datos:
                vals = [float(x) if x is not None else 0.0 for x in row]
                sucio, totiao, yema = vals[7], vals[8], vals[9]
                
                val_segundas = int(sucio + totiao + yema)
                val_ttl = int(sum(vals))
                
                def calc_porc(v, t):
                    return round((v / t) * 100, 2) if t > 0 else 0.00

                p_jum = calc_porc(vals[0], val_ttl)
                p_extra = calc_porc(vals[1], val_ttl)
                p_aa = calc_porc(vals[2], val_ttl)
                p_a = calc_porc(vals[3], val_ttl)
                p_b = calc_porc(vals[4], val_ttl)
                p_c = calc_porc(vals[5], val_ttl)
                p_pipo = calc_porc(vals[6], val_ttl)
                p_sucio = calc_porc(sucio, val_ttl)
                p_totiao = calc_porc(totiao, val_ttl)
                p_yema = calc_porc(yema, val_ttl)
                p_seg = calc_porc(val_segundas, val_ttl)
                
                p_h_grande = round(p_jum + p_extra + p_aa, 2)
                
                acum['jum'] += vals[0]
                acum['extra'] += vals[1]
                acum['aa'] += vals[2]
                acum['a'] += vals[3]
                acum['b'] += vals[4]
                acum['c'] += vals[5]
                acum['pipo'] += vals[6]
                acum['sucio'] += sucio
                acum['totiao'] += totiao
                acum['yema'] += yema
                acum['segundas'] += val_segundas
                acum['total'] += val_ttl
                
                v_jum, v_extra, v_aa = int(acum['jum']), int(acum['extra']), int(acum['aa'])
                v_a, v_b, v_c = int(acum['a']), int(acum['b']), int(acum['c'])
                v_pipo, v_sucio, v_totiao = int(acum['pipo']), int(acum['sucio']), int(acum['totiao'])
                v_yema, v_seg, v_tot = int(acum['yema']), int(acum['segundas']), int(acum['total'])
            else:
                val_segundas = val_ttl = p_jum = p_extra = p_aa = p_a = p_b = p_c = p_pipo = p_sucio = p_totiao = p_yema = p_seg = p_h_grande = None
                v_jum = v_extra = v_aa = v_a = v_b = v_c = v_pipo = v_sucio = v_totiao = v_yema = v_seg = v_tot = None
            
            cur.execute("""
                UPDATE clasificacion_produccion 
                SET clas_segundas = %s, clas_ttl = %s, porc_h_grande = %s,
                    porc_sem_jum = %s, porc_sem_extra = %s, porc_sem_aa = %s, porc_sem_a = %s, 
                    porc_sem_b = %s, porc_sem_c = %s, porc_sem_pipo = %s, porc_sem_sucio = %s, 
                    porc_sem_totiao = %s, porc_sem_yema = %s, porc_sem_segundas = %s,
                    acum_jum = %s, acum_extra = %s, acum_aa = %s, acum_a = %s, acum_b = %s, acum_c = %s, 
                    acum_pipo = %s, acum_sucio = %s, acum_totiao = %s, acum_yema = %s, acum_segundas = %s, acum_total = %s
                WHERE id = %s
            """, (
                val_segundas, val_ttl, p_h_grande,
                p_jum, p_extra, p_aa, p_a, p_b, p_c, p_pipo, p_sucio, p_totiao, p_yema, p_seg,
                v_jum, v_extra, v_aa, v_a, v_b, v_c, v_pipo, v_sucio, v_totiao, v_yema, v_seg, v_tot,
                id_reg
            ))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error recalculando tabla: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()