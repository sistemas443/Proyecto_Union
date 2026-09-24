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
            # 1. OBTENER PESO H. TABLA BUSCANDO POR sem_prod
            val_peso_h_tabla = None
            try:
                cur.execute("SELECT sv, id_lote, lote FROM clasificacion_produccion WHERE id = %s", (id_reg,))
                r_info = cur.fetchone()
                if r_info:
                    r_sv, r_id_lote, r_lote = r_info
                    try:
                        cur.execute("SELECT peso_huevo_tab FROM bd_vargas WHERE id_lote = %s AND sem_prod = %s", (r_id_lote, r_sv))
                        res_w = cur.fetchone()
                        if res_w: val_peso_h_tabla = res_w[0]
                    except:
                        conn.rollback()
                        cur.execute("SELECT peso_huevo_tab FROM bd_vargas WHERE lote = %s AND sem_prod = %s", (r_lote, r_sv))
                        res_w = cur.fetchone()
                        if res_w: val_peso_h_tabla = res_w[0]
            except:
                conn.rollback()

            # 2. RECALCULAR FILA ACTUAL
            cur.execute("""
                SELECT clas_jum, clas_extra, clas_aa, clas_a, clas_b, clas_c,
                       clas_pipo, clas_sucio, clas_totiao, clas_yema
                FROM clasificacion_produccion WHERE id = %s
            """, (id_reg,))
            row = cur.fetchone()
            
            if row:
                tiene_datos = any(x is not None for x in row)
                
                if tiene_datos:
                    vals = [float(x) if x is not None else 0.0 for x in row]
                    sucio, totiao, yema = vals[7], vals[8], vals[9]
                    
                    val_segundas = int(sucio + totiao + yema)
                    val_ttl = int(sum(vals))
                    
                    if val_ttl > 0:
                        suma_pesos = (
                            vals[0] * 78.0 + vals[1] * 72.5 + vals[2] * 63.5 +
                            vals[3] * 56.5 + vals[4] * 49.5 + vals[5] * 46.0 +
                            vals[6] * 45.0 + val_segundas * 60.0
                        )
                        val_peso_h_prom = round(suma_pesos / val_ttl, 2)
                    else:
                        val_peso_h_prom = 0.00
                    
                    def calc_porc(v, t):
                        if t > 0: return round((v / t) * 100, 2)
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
                    
                    p_h_grande = round(p_jum + p_extra + p_aa, 2)
                else:
                    val_segundas = val_ttl = None
                    p_jum = p_extra = p_aa = p_a = p_b = p_c = p_pipo = p_sucio = p_totiao = p_yema = p_seg = p_h_grande = None
                    val_peso_h_prom = None
                
                cur.execute("""
                    UPDATE clasificacion_produccion 
                    SET clas_segundas = %s, clas_ttl = %s,
                        porc_sem_jum = %s, porc_sem_extra = %s, porc_sem_aa = %s, porc_sem_a = %s, 
                        porc_sem_b = %s, porc_sem_c = %s, porc_sem_pipo = %s, porc_sem_sucio = %s, 
                        porc_sem_totiao = %s, porc_sem_yema = %s, porc_sem_segundas = %s,
                        porc_h_grande = %s, peso_h_prom = %s, peso_h_tabla = %s
                    WHERE id = %s
                """, (
                    val_segundas, val_ttl,
                    p_jum, p_extra, p_aa, p_a, p_b, p_c, p_pipo, p_sucio, p_totiao, p_yema, p_seg,
                    p_h_grande, val_peso_h_prom, val_peso_h_tabla, id_reg
                ))
                
            # 3. RECALCULAR TODOS LOS ACUMULADOS EN CASCADA
            cur.execute("SELECT id_lote FROM clasificacion_produccion WHERE id = %s", (id_reg,))
            id_lote = cur.fetchone()[0]
            
            # PRE-CARGAR PESOS TABLA DE FORMA SEGURA (BUSCANDO sem_prod)
            pesos_vargas = {}
            try:
                cur.execute("SELECT sem_prod, peso_huevo_tab FROM bd_vargas WHERE id_lote = %s", (id_lote,))
                for r in cur.fetchall(): pesos_vargas[r[0]] = r[1]
            except:
                conn.rollback()
                try:
                    cur.execute("SELECT v.sem_prod, v.peso_huevo_tab FROM bd_vargas v JOIN clasificacion_produccion c ON c.lote = v.lote WHERE c.id_lote = %s", (id_lote,))
                    for r in cur.fetchall(): pesos_vargas[r[0]] = r[1]
                except:
                    conn.rollback()

            cur.execute("""
                SELECT id, clas_ttl, clas_jum, clas_extra, clas_aa, clas_a, clas_b, clas_c, 
                       clas_pipo, clas_sucio, clas_totiao, clas_yema, clas_segundas, sv
                FROM clasificacion_produccion 
                WHERE id_lote = %s ORDER BY sv ASC
            """, (id_lote,))
            filas_lote = cur.fetchall()
            
            acum = { 'jum': 0.0, 'extra': 0.0, 'aa': 0.0, 'a': 0.0, 'b': 0.0, 'c': 0.0, 
                     'pipo': 0.0, 'sucio': 0.0, 'totiao': 0.0, 'yema': 0.0, 'segundas': 0.0, 'total': 0.0 }
            
            valores_update = []
            
            for f in filas_lote:
                f_id = f[0]
                c_ttl = f[1]
                val_sv = f[13]
                val_peso_h_tabla = pesos_vargas.get(val_sv)
                
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
                    val_roto = round(pa_totiao + pa_yema, 2)
                else:
                    v_jum = v_extra = v_aa = v_a = v_b = v_c = v_pipo = v_sucio = v_totiao = v_yema = v_segundas = v_total = None
                    pa_jum = pa_extra = pa_aa = pa_a = pa_b = pa_c = pa_pipo = pa_sucio = pa_totiao = pa_yema = pa_segundas = None
                    val_roto = None
                
                valores_update.append((
                    v_jum, v_extra, v_aa, v_a, v_b, v_c, v_pipo, v_sucio, v_totiao, v_yema, v_segundas, v_total,
                    pa_jum, pa_extra, pa_aa, pa_a, pa_b, pa_c, pa_pipo, pa_sucio, pa_totiao, pa_yema, pa_segundas,
                    val_roto, val_peso_h_tabla, f_id
                ))
            
            if valores_update:
                cur.executemany("""
                    UPDATE clasificacion_produccion SET 
                        acum_jum = %s, acum_extra = %s, acum_aa = %s, acum_a = %s, acum_b = %s, acum_c = %s, 
                        acum_pipo = %s, acum_sucio = %s, acum_totiao = %s, acum_yema = %s, acum_segundas = %s, acum_total = %s,
                        porc_acu_jum = %s, porc_acu_extra = %s, porc_acu_aa = %s, porc_acu_a = %s, porc_acu_b = %s, porc_acu_c = %s, 
                        porc_acu_pipo = %s, porc_acu_sucio = %s, porc_acu_totiao = %s, porc_acu_yema = %s, porc_acu_segundas = %s,
                        roto = %s, peso_h_tabla = %s
                    WHERE id = %s
                """, valores_update)
                
        conn.commit()
    except Exception as e:
        print(f"Error recalculando celda: {e}", flush=True)
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

    return True

def recalcular_lote_completo_clasificacion(id_lote):
    from models.base import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # PRE-CARGAR PESOS TABLA DE FORMA SEGURA (BUSCANDO sem_prod)
        pesos_vargas = {}
        try:
            cur.execute("SELECT sem_prod, peso_huevo_tab FROM bd_vargas WHERE id_lote = %s", (id_lote,))
            for r in cur.fetchall(): pesos_vargas[r[0]] = r[1]
        except:
            conn.rollback()
            try:
                cur.execute("SELECT v.sem_prod, v.peso_huevo_tab FROM bd_vargas v JOIN clasificacion_produccion c ON c.lote = v.lote WHERE c.id_lote = %s", (id_lote,))
                for r in cur.fetchall(): pesos_vargas[r[0]] = r[1]
            except:
                conn.rollback()

        # CONSULTA PRINCIPAL INTACTA (Segura)
        cur.execute("""
            SELECT id, clas_jum, clas_extra, clas_aa, clas_a, clas_b, clas_c,
                   clas_pipo, clas_sucio, clas_totiao, clas_yema, sv
            FROM clasificacion_produccion 
            WHERE id_lote = %s ORDER BY sv ASC
        """, (id_lote,))
        filas = cur.fetchall()

        acum = { 'jum': 0.0, 'extra': 0.0, 'aa': 0.0, 'a': 0.0, 'b': 0.0, 'c': 0.0, 
                 'pipo': 0.0, 'sucio': 0.0, 'totiao': 0.0, 'yema': 0.0, 'segundas': 0.0, 'total': 0.0 }
        
        for f in filas:
            id_reg = f[0]
            row_vals = f[1:11]
            val_sv = f[11]
            val_peso_h_tabla = pesos_vargas.get(val_sv)
            
            tiene_datos = any(x is not None for x in row_vals)
            
            if tiene_datos:
                vals = [float(x) if x is not None else 0.0 for x in row_vals]
                sucio, totiao, yema = vals[7], vals[8], vals[9]
                
                val_segundas = int(sucio + totiao + yema)
                val_ttl = int(sum(vals))
                
                if val_ttl > 0:
                    suma_pesos = (
                        vals[0] * 78.0 + vals[1] * 72.5 + vals[2] * 63.5 +
                        vals[3] * 56.5 + vals[4] * 49.5 + vals[5] * 46.0 +
                        vals[6] * 45.0 + val_segundas * 60.0
                    )
                    val_peso_h_prom = round(suma_pesos / val_ttl, 2)
                else:
                    val_peso_h_prom = 0.00
                
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
                v_yema, v_segundas, v_total = int(acum['yema']), int(acum['segundas']), int(acum['total'])

                def calc_p_acu(val_acu):
                    return round((val_acu / v_total) * 100, 2) if val_ttl > 0 and v_total > 0 else 0.00
                    
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
                val_roto = round(pa_totiao + pa_yema, 2)
            else:
                val_segundas = val_ttl = p_jum = p_extra = p_aa = p_a = p_b = p_c = p_pipo = p_sucio = p_totiao = p_yema = p_seg = p_h_grande = None
                v_jum = v_extra = v_aa = v_a = v_b = v_c = v_pipo = v_sucio = v_totiao = v_yema = v_segundas = v_total = None
                val_roto = None
                val_peso_h_prom = None
                pa_jum = pa_extra = pa_aa = pa_a = pa_b = pa_c = pa_pipo = pa_sucio = pa_totiao = pa_yema = pa_segundas = None
            
            cur.execute("""
                UPDATE clasificacion_produccion 
                SET clas_segundas = %s, clas_ttl = %s, porc_h_grande = %s,
                    porc_sem_jum = %s, porc_sem_extra = %s, porc_sem_aa = %s, porc_sem_a = %s, 
                    porc_sem_b = %s, porc_sem_c = %s, porc_sem_pipo = %s, porc_sem_sucio = %s, 
                    porc_sem_totiao = %s, porc_sem_yema = %s, porc_sem_segundas = %s,
                    acum_jum = %s, acum_extra = %s, acum_aa = %s, acum_a = %s, acum_b = %s, acum_c = %s, 
                    acum_pipo = %s, acum_sucio = %s, acum_totiao = %s, acum_yema = %s, acum_segundas = %s, acum_total = %s,
                    porc_acu_jum = %s, porc_acu_extra = %s, porc_acu_aa = %s, porc_acu_a = %s, porc_acu_b = %s, porc_acu_c = %s, 
                    porc_acu_pipo = %s, porc_acu_sucio = %s, porc_acu_totiao = %s, porc_acu_yema = %s, porc_acu_segundas = %s,
                    roto = %s, peso_h_prom = %s, peso_h_tabla = %s
                WHERE id = %s
            """, (
                val_segundas, val_ttl, p_h_grande,
                p_jum, p_extra, p_aa, p_a, p_b, p_c, p_pipo, p_sucio, p_totiao, p_yema, p_seg,
                v_jum, v_extra, v_aa, v_a, v_b, v_c, v_pipo, v_sucio, v_totiao, v_yema, v_segundas, v_total,
                pa_jum, pa_extra, pa_aa, pa_a, pa_b, pa_c, pa_pipo, pa_sucio, pa_totiao, pa_yema, pa_segundas,
                val_roto, val_peso_h_prom, val_peso_h_tabla,
                id_reg
            ))
        conn.commit()
        return True
    except Exception as e:
        import traceback
        print(f"\n=== ERROR SQL ===\n{e}\n{traceback.format_exc()}\n=================", flush=True)
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()
        
def procesar_excel_clasificacion(archivo_excel, lote_nombre):
    """
    Procesa el Excel de Clasificación de Producción.
    Extrae únicamente las columnas crudas digitadas por el usuario (las que NO tienen fórmula),
    y dispara el recálculo completo en cascada (porcentajes, acumulados, promedios).
    """
    import pandas as pd
    import unicodedata
    import re
    from models.base import get_db_connection, to_float_safe
    from models.cabecera.model import fetch_cabecera_by_lote
    from models.clasificacion import model

    if not lote_nombre or lote_nombre == 'VACIO':
        return False, "Debes seleccionar un lote válido de destino."

    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera:
        return False, f"El lote '{lote_nombre}' no existe en el sistema."

    id_lote = cabecera.get('id')

    try:
        # 1. Garantizar que la estructura de semanas (18 a 109) exista en la BD
        if model.count_clasificacion(id_lote) == 0:
            generar_estructura_clasificacion(lote_nombre, id_lote)

        # 2. Leer TODAS las hojas del Excel sin encabezados
        hojas = pd.read_excel(archivo_excel, sheet_name=None, header=None)
        df = None
        header_idx = -1

        def normalizar(texto):
            texto = str(texto).lower().strip()
            texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
            return ' '.join(texto.replace('\n', ' ').split())

        # 3. Escáner: buscar la fila con los sub-encabezados reales
        for nombre_hoja, hoja_df in hojas.items():
            for i, row in hoja_df.iterrows():
                fila_texto = " ".join([normalizar(x) for x in row.values])

                tiene_jum = 'jum' in fila_texto
                tiene_extra = 'extra' in fila_texto
                tiene_pipo = 'pipo' in fila_texto
                tiene_sv = 'sv' in fila_texto

                # Requerir al menos 3 de estas 4 palabras clave
                if sum([tiene_jum, tiene_extra, tiene_pipo, tiene_sv]) >= 3:
                    df = hoja_df
                    header_idx = i
                    break
            if df is not None:
                break

        if df is None:
            return False, "No se encontró la tabla de Clasificación."

        # 4. Combinar las DOS filas de encabezados:
        #    - Fila superior (header_idx - 1): contiene títulos generales y 'sv' fusionado
        #    - Fila inferior (header_idx): contiene los sub-encabezados (jum, extra, a a, etc.)
        fila_superior = [normalizar(x) for x in df.iloc[header_idx - 1].values] if header_idx > 0 else [''] * len(df.columns)
        fila_inferior = [normalizar(x) for x in df.iloc[header_idx].values]

        nuevas_columnas = []
        for col_idx in range(len(fila_inferior)):
            val_sup = fila_superior[col_idx] if col_idx < len(fila_superior) else ''
            val_inf = fila_inferior[col_idx] if col_idx < len(fila_inferior) else ''

            val_sup = val_sup if val_sup not in ['nan', 'none'] else ''
            val_inf = val_inf if val_inf not in ['nan', 'none'] else ''

            # Preferir el valor inferior (sub-encabezado), si está vacío usar el superior
            if val_inf:
                nombre_col = val_inf
            elif val_sup:
                nombre_col = val_sup
            else:
                nombre_col = ''

            nuevas_columnas.append(nombre_col)

        df.columns = nuevas_columnas

        # --- DESDUPLICAR NOMBRES DE COLUMNAS ---
        cols_unicas = []
        contador = {}
        for c in df.columns:
            if c in contador:
                contador[c] += 1
                cols_unicas.append(f"{c}__dup{contador[c]}")
            else:
                contador[c] = 0
                cols_unicas.append(c)
        df.columns = cols_unicas

        # Los datos empiezan en la fila SIGUIENTE al header_idx
        df = df.iloc[header_idx + 1:].reset_index(drop=True)

        # 5. Ubicar la columna "SV"
        col_sv = None
        for col in df.columns:
            c = str(col).lower().strip()
            if c == 'sv':
                valores_prueba = []
                for v in df[col].dropna().tolist():
                    try:
                        v_str = str(v).strip().replace('.0', '')
                        if v_str.isdigit():
                            valores_prueba.append(int(v_str))
                    except:
                        continue

                if len(valores_prueba) > 0:
                    nums = pd.Series(valores_prueba)
                    if ((nums >= 18) & (nums <= 110)).sum() > 0:
                        col_sv = col
                        break

        if not col_sv:
            return False, "Error interno: No se ubicó la columna 'SV' con valores válidos (18-110)."

        # 6. MAPEO de columnas
        mapeo_columnas = {
            'jum':   'clas_jum',
            'extra': 'clas_extra',
            'aa':    'clas_aa',
            'a a':   'clas_aa',
            'pipo':  'clas_pipo',
            'sucio': 'clas_sucio',
            'totia': 'clas_totiao',
            'yema':  'clas_yema',
        }

        conn = get_db_connection()
        cur = conn.cursor()
        filas_actualizadas = 0

        def extraer_valor(v):
            if pd.isna(v): return None
            v_str = str(v).strip().lower()
            if v_str in ['', 'nan', '-', 'none']: return None
            return v

        # 7. Iterar sobre las filas
        for _, row in df.iterrows():
            val_sv_raw = row[col_sv]
            if pd.isna(val_sv_raw):
                continue

            val_sv_str = str(val_sv_raw).strip().replace(',', '.').replace(' ', '')
            if '.' in val_sv_str:
                val_sv_str = val_sv_str.split('.')[0]

            if not val_sv_str.isdigit():
                continue
            num_sv = int(val_sv_str)
            if not (18 <= num_sv <= 110):
                continue

            campos_a_actualizar = []
            valores = []
            columnas_ya_procesadas = set()

            # A. Columnas compuestas (jum, extra, aa, pipo, sucio, totiao, yema)
            for palabra_clave, col_db in mapeo_columnas.items():
                if col_db in columnas_ya_procesadas:
                    continue
                col_encontrada = None
                for c in df.columns:
                    c_lower = str(c).lower().strip()
                    if '__dup' in c_lower:
                        continue
                    palabras = c_lower.split()
                    if palabra_clave in palabras or c_lower == palabra_clave:
                        col_encontrada = c
                        break

                if col_encontrada:
                    v = extraer_valor(row[col_encontrada])
                    if v is not None:
                        try:
                            campos_a_actualizar.append(f'"{col_db}" = %s')
                            valores.append(to_float_safe(v) or 0.0)
                            columnas_ya_procesadas.add(col_db)
                        except: pass

            # B. Columnas de una sola letra (A, B, C) con coincidencia ESTRICTA
            mapeo_letras = {
                'a': 'clas_a',
                'b': 'clas_b',
                'c': 'clas_c',
            }

            for letra, col_db in mapeo_letras.items():
                if col_db in columnas_ya_procesadas:
                    continue

                col_encontrada = None
                for c in df.columns:
                    c_lower = str(c).lower().strip()

                    # Ignorar duplicados
                    if '__dup' in c_lower:
                        continue

                    # Ignorar 'a a' o 'aa' (doble A)
                    if c_lower == 'a a' or c_lower == 'aa':
                        continue

                    # Coincidencia por palabra completa
                    palabras = c_lower.split()

                    # Debe contener EXACTAMENTE la letra como palabra completa
                    if letra in palabras:
                        # Descartar si también contiene otra letra del mismo set
                        letras_presentes = [l for l in ['a', 'b', 'c'] if l in palabras]
                        if len(letras_presentes) == 1 and letras_presentes[0] == letra:
                            col_encontrada = c
                            break

                if col_encontrada:
                    v = extraer_valor(row[col_encontrada])
                    if v is not None:
                        try:
                            campos_a_actualizar.append(f'"{col_db}" = %s')
                            valores.append(to_float_safe(v) or 0.0)
                            columnas_ya_procesadas.add(col_db)
                        except: pass

            if campos_a_actualizar:
                valores.extend([id_lote, num_sv])
                query = f"UPDATE clasificacion_produccion SET {', '.join(campos_a_actualizar)} WHERE id_lote = %s AND sv = %s"
                cur.execute(query, valores)
                filas_actualizadas += 1

        conn.commit()
        cur.close()
        conn.close()

        # 8. Recalcular toda la cascada
        recalcular_lote_completo_clasificacion(id_lote)

        if filas_actualizadas > 0:
            return True, f"¡Éxito! Se cargaron datos puros de {filas_actualizadas} semanas de clasificación."
        else:
            return False, "La tabla fue detectada, pero las filas de SV (18-110) estaban vacías."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error al procesar el archivo Excel: {str(e)}"