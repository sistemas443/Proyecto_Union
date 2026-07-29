# models/semanal_levante/services.py
from datetime import datetime, timedelta
from models.base import get_db_connection, parse_empty, to_float_safe
from models.semanal_levante.schemas import COLUMNAS_PERMITIDAS
from models.semanal_levante import model
from models.cabecera.model import fetch_cabecera_by_lote

def generar_estructura_semanal_levante(lote_nombre, fecha_recepcion, id_lote):
    """
    Inicializa la estructura matriz para la fase de Levante, la cual comprende exactamente 18 semanas.
    Proyecta las fechas de finalización de cada semana basándose en la fecha de recepción e inyecta
    los valores estandarizados de consumo teórico (guía TAB) definidos para esta línea genética.
    """
    if not id_lote or not lote_nombre:
        return

    # Validación de control para evitar la sobreescritura o duplicación de la estructura base
    if model.count_semanal(id_lote) > 0:
        return

    # Normalización del parámetro de fecha de recepción a objeto datetime
    fecha_base = None
    if fecha_recepcion and str(fecha_recepcion).strip() != '':
        try:
            fecha_base = datetime.strptime(str(fecha_recepcion), '%Y-%m-%d')
        except ValueError:
            pass

    valores = []
    # Generación secuencial de las 18 semanas de la etapa de Levante
    for i in range(18):
        semana_vida = i + 1
        fecha_str = None
        if fecha_base:
            fecha_str = (fecha_base + timedelta(days=(semana_vida * 7) - 1)).strftime('%Y-%m-%d')
        valores.append((lote_nombre, id_lote, fecha_str, semana_vida))

    try:
        model.insert_estructura_semanal(valores)
    except Exception as e:
        print(f"[ERROR INSERT ORIGINAL LEVANTE]: {e}")
        return

    # Arreglo estático de la guía teórica de consumo en gramos por semana para Levante
    guia_tab = [14, 21, 25, 30, 36, 44, 49, 56, 61, 64, 69, 72, 74, 77, 79, 82, 85, 0]
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Inserción de los valores teóricos en las celdas pre-creadas
        for i in range(18):
            v_tab = guia_tab[i]
            semana_vida = i + 1
            cur.execute("""
                UPDATE semanal_levante 
                SET cons_tab = %s 
                WHERE id_lote = %s AND sem = %s
            """, (v_tab, id_lote, semana_vida))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR INYECTANDO TAB LEVANTE]: {e}")
    finally:
        cur.close()
        conn.close()

def get_semanal_levante_all(lote_nombre: str = ''):
    """
    Extrae la totalidad de los registros de la fase de Levante para un lote determinado.
    Aplica una rutina de sincronización forzada con los registros diarios antes de la lectura
    para asegurar que la información presentada en la interfaz esté estrictamente actualizada.
    """
    if not lote_nombre or lote_nombre == 'VACIO':
        return []

    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera:
        return []

    id_lote = cabecera['id']

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Detonación del motor de recálculo y sincronización previo a la extracción
        recalcular_lote_semanal_levante_directo(id_lote, cur)
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    rows = model.fetch_semanal_levante(id_lote)

    # Autogeneración: Si la tabla fue consultada y no tiene registros, inicializa la estructura
    if len(rows) == 0:
        generar_estructura_semanal_levante(lote_nombre, cabecera.get('fecha_recepcion'), id_lote)
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            recalcular_lote_semanal_levante_directo(id_lote, cur)
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
            
        rows = model.fetch_semanal_levante(id_lote)

    return rows

def update_semanal_field(id_semanal: int, columna: str, valor: str) -> tuple[bool, dict, str]:
    """
    Procesa y persiste las actualizaciones de campos individuales remitidas desde la vista.
    Aplica conversiones de tipos y, si el campo modificado impacta la lógica matemática,
    dispara un procesamiento en cascada a través de las 18 semanas asegurando la consistencia
    de los indicadores de desempeño (acumulados, saldos y conversiones).
    """
    if columna not in COLUMNAS_PERMITIDAS:
        return False, {}, f"Columna '{columna}' no permitida"

    valor_db = parse_empty(valor)
    campos_actualizados = {}
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        id_lote = model.get_lote_id_by_semanal(id_semanal)
        if not id_lote:
            return False, {}, "No se encontró el ID del lote"

        # Listado de atributos que al modificarse requieren recálculo integral del módulo
        columnas_matematicas = [
            'cons_tab', 'cons_kilos_real', 'mort_sem', 
            'mort_select_sem', 'mort_venta', 'peso_ave_real', 'peso_real',
            'peso_ave_tab', 'peso_tab'
        ]

        if id_lote and (columna in columnas_matematicas):
            # Obtención de parámetros críticos de la cabecera del lote
            res_aves = model.get_aves_iniciales(id_lote)
            if res_aves is None: aves_iniciales = 10000.0
            elif isinstance(res_aves, (int, float)): aves_iniciales = float(res_aves)
            else:
                try: aves_iniciales = to_float_safe(res_aves[0] if isinstance(res_aves, tuple) else res_aves.get('no_pollitas_recibidas', 10000.0))
                except Exception: aves_iniciales = 10000.0

            if aves_iniciales <= 0: aves_iniciales = 1.0

            cur.execute("SELECT peso, COALESCE(unidad_peso, 1.0) FROM cabecera_lotes WHERE id = %s", (id_lote,))
            cab_info = cur.fetchone()
            peso_recep = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 0.0
            u_peso = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 1.0

            # Normalización de los identificadores de columnas para la actualización directa
            col_db = columna
            if columna == 'mort_sem': col_db = 'mort'
            elif columna == 'mort_select_sem': col_db = 'sel'
            elif columna == 'mort_venta': col_db = 'otros'
            elif columna in ['peso_real', 'peso_ave_real']: col_db = 'peso_real'
            elif columna in ['peso_tab', 'peso_ave_tab']: col_db = 'peso_tab'

            cur.execute(f"UPDATE semanal_levante SET {col_db} = %s WHERE id = %s", (valor_db, id_semanal))

            # Extracción del histórico secuencial para procesamiento matemático
            cur.execute("""
                SELECT id, cons_tab, cons_kilos_real, mort, sel, otros, peso_real, sem, peso_tab
                FROM semanal_levante WHERE id_lote = %s ORDER BY sem ASC
            """, (id_lote,))
            filas = cur.fetchall()

            acum_kilos = 0.0
            acum_mort = 0.0
            acum_sel = 0.0
            acum_otros = 0.0
            valores_update = []
            
            # Inicialización de variables de alta precisión para coincidencia exacta con hojas de cálculo
            acum_gr_ave_tab_exacto = 0.0
            gr_ave_tab_anterior_exacto = 0.0  
            
            peso_real_anterior = peso_recep if peso_recep > 0 else 0.0
            peso_tab_anterior = 35.0  
            gr_ave_ac_anterior_exacto = 0.0          

            for idx, f in enumerate(filas):
                f_id = f[0]
                num_semana = int(f[7]) if f[7] is not None else (idx + 1)
                dia_inicio, dia_fin = ((num_semana - 1) * 7) + 1, num_semana * 7

                c_tab = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_tab') else to_float_safe(f[1])
                c_k_real = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_kilos_real') else to_float_safe(f[2])
                m_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_sem') else to_float_safe(f[3])
                s_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_select_sem') else to_float_safe(f[4])
                o_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_venta') else to_float_safe(f[5])
                peso_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['peso_real', 'peso_ave_real']) else to_float_safe(f[6])
                peso_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['peso_tab', 'peso_ave_tab']) else to_float_safe(f[8])

                # Sincronización condicional: lectura desde tabla transaccional diaria si la celda manual está vacía
                if c_k_real == 0:
                    cur.execute("SELECT COALESCE(SUM(consumo_kg), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
                    res = cur.fetchone()
                    if res and res[0] > 0: c_k_real = to_float_safe(res[0])

                if m_sem == 0:
                    cur.execute("SELECT COALESCE(SUM(mortalidad), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
                    res = cur.fetchone()
                    if res and res[0] > 0: m_sem = to_float_safe(res[0])

                if s_sem == 0:
                    cur.execute("SELECT COALESCE(SUM(sel), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
                    res = cur.fetchone()
                    if res and res[0] > 0: s_sem = to_float_safe(res[0])

                if o_sem == 0:
                    cur.execute("SELECT COALESCE(SUM(otros), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
                    res = cur.fetchone()
                    if res and res[0] > 0: o_sem = to_float_safe(res[0])

                # Procesamiento de variables de estado acumulativas
                acum_kilos += c_k_real
                acum_mort += m_sem
                acum_sel += s_sem
                acum_otros += o_sem
                
                acum_gr_ave_tab_exacto += (c_tab * 7.0)

                tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or c_tab > 0 or peso_real_val > 0)
                acu_val = acum_mort + acum_sel + acum_otros
                acu_out = int(round(acu_val)) if tiene_datos else None
                saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

                p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
                p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and acum_mort > 0 and tiene_datos) else None
                p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
                p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

                c_k_acum_val = int(round(acum_kilos)) if (c_k_real > 0 or c_tab > 0) else None
                
                # Cálculo exacto sin truncar para propagación de precisión
                c_real_exacto = (c_k_real / float(saldo_val) / 7.0) * 1000.0 if (tiene_datos and saldo_val > 0) else None
                c_real_val = round(c_real_exacto, 1) if c_real_exacto is not None else None
                
                gr_ave_tab_val = int(round(acum_gr_ave_tab_exacto))
                
                gr_ave_ac_exacto = (float(acum_kilos) / float(saldo_val)) * 1000.0 if (acum_kilos > 0 and saldo_val > 0) else 0.0
                gr_ave_ac_val = int(round(gr_ave_ac_exacto))

                # Determinación de márgenes de ganancia corporal semanales
                ganancia_ave_dia_val = round(peso_real_val - peso_real_anterior, 2) if (peso_real_val > 0 and peso_real_anterior > 0) else 0.0
                if peso_real_val > 0: peso_real_anterior = peso_real_val 

                ganancia_ave_val = round(peso_tab_val - peso_tab_anterior, 2) if (peso_tab_val > 0 and peso_tab_anterior > 0) else 0.0
                if peso_tab_val > 0: peso_tab_anterior = peso_tab_val 

                porc_cumpl_ganan_val = round(((ganancia_ave_dia_val / ganancia_ave_val) - 1.0) * 100.0, 2) if (ganancia_ave_dia_val > 0 and ganancia_ave_val > 0) else 0.0
                
                # Formulación matemática de conversiones alimenticias
                conv_sem_tab_val = 0.0
                if ganancia_ave_val > 0:
                    diff_gr_tab_exacto = acum_gr_ave_tab_exacto - gr_ave_tab_anterior_exacto
                    conv_sem_tab_val = round(diff_gr_tab_exacto / ganancia_ave_val, 2)
                
                gr_ave_tab_anterior_exacto = acum_gr_ave_tab_exacto
                
                conversion_sem_val = 0.0
                if c_k_real > 0 and ganancia_ave_dia_val > 0:
                    diff_gramos_exacto = gr_ave_ac_exacto - gr_ave_ac_anterior_exacto
                    conversion_sem_val = round(diff_gramos_exacto / ganancia_ave_dia_val, 2)
                
                gr_ave_ac_anterior_exacto = gr_ave_ac_exacto

                porc_cumpl_cons_val = 0.0
                if c_real_exacto is not None and c_real_exacto > 0 and c_tab > 0:
                    porc_cumpl_cons_val = round(((c_real_exacto / c_tab) - 1.0) * 100.0, 2)

                try:
                    val_ajustado = int(round(float(u_peso) * float(c_k_real)))
                except Exception:
                    val_ajustado = 0

                tiene_datos_reales = (c_k_real > 0 or peso_real_val > 0 or m_sem > 0)

                # Compilación del paquete de datos transaccionales
                valores_update.append((
                    c_k_real, m_sem, s_sem, o_sem,
                    c_real_val, c_k_acum_val, gr_ave_tab_val, gr_ave_ac_val,
                    acu_out, p_mort_sem, p_mort_acum, p_sel_sem, p_ms_acu, saldo_val, 
                    conversion_sem_val, ganancia_ave_dia_val, ganancia_ave_val, porc_cumpl_ganan_val,
                    conv_sem_tab_val, val_ajustado, porc_cumpl_cons_val, f_id
                ))

                # Preparación del diccionario de respuesta para la vista asíncrona
                if f_id == id_semanal:
                    campos_actualizados.update({
                        'cons_kilos_real':               int(round(c_k_real)) if c_k_real > 0 else 0,
                        'cons_kilos_ajustado':           val_ajustado, 
                        'cons_real':                     f"{c_real_val:.1f}" if c_real_val is not None else '', 
                        'cons_k_acum':                   int(c_k_acum_val) if c_k_acum_val is not None else '',   
                        'cons_gr_ave_tab':               int(gr_ave_tab_val) if gr_ave_tab_val is not None else '', 
                        'cons_gr_ave_ao':                int(round(gr_ave_ac_val)) if gr_ave_ac_val > 0 else 0,
                        'salidas_acum':                  acu_out if acu_out is not None else '',
                        'mort_sem':                      int(round(m_sem)),
                        'saldo_ave':                     int(saldo_val),
                        'conv_sem':                      f"{conversion_sem_val:.2f}" if tiene_datos_reales else '',
                        'conv_sem_tab':                  f"{conv_sem_tab_val:.2f}" if tiene_datos_reales else '',
                        'ganancia_ave_dia':              f"{ganancia_ave_dia_val:.1f}" if tiene_datos_reales else '',
                        'ganancia_ave':                  f"{ganancia_ave_val:.1f}" if tiene_datos_reales else '',
                        'porc_cumpl_ganan':              f"{porc_cumpl_ganan_val:.2f}" if tiene_datos_reales else '',
                        'porc_cumpl_cons':               f"{porc_cumpl_cons_val:.2f}" if tiene_datos_reales else '' 
                    })

            # Ejecución optimizada de la persistencia masiva de datos en cascada
            if valores_update:
                cur.executemany("""
                    UPDATE semanal_levante 
                    SET cons_kilos_real = %s, mort = %s, sel = %s, otros = %s,
                        cons_real = %s, cons_k_acum = %s, cons_gr_ave_tab = %s, cons_gr_ave_ao = %s,
                        acu = %s, porc_mort_sem = %s, porc_mort_acm = %s, porc_sel_sem = %s, porc_ms_acu = %s, 
                        saldo_aves = %s, conv_sem = %s, ganancia_ave_dia = %s, ganancia_ave = %s, porc_cumpl_ganan = %s,
                        conv_sem_tab = %s, cons_kilos_ajustado = %s, porc_cumpl_cons = %s
                    WHERE id = %s                      
                """, valores_update)
        else:
            model.guardar_dato_simple(id_semanal, columna, valor_db, cur)

        conn.commit()
        return True, campos_actualizados, "Ok"
    except Exception as e:
        conn.rollback()
        return False, {}, str(e)
    finally:
        cur.close()
        conn.close()

def recalcular_lote_semanal_levante_directo(id_lote, cur):
    """
    Motor interno de sincronización y recalculación matemática profunda.
    Agrega información primaria originada en el control diario y recalcula 
    la cascada de índices de rendimiento técnico a través de las 18 semanas, 
    gestionando las precisiones posicionales para evitar propagación de errores de redondeo.
    """
    cur.execute("SELECT no_pollitas_recibidas, peso, COALESCE(unidad_peso, 1.0) FROM cabecera_lotes WHERE id = %s", (id_lote,))
    cab_info = cur.fetchone()
    
    aves_iniciales = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 10000.0
    peso_recep = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 0.0
    u_peso = to_float_safe(cab_info[2]) if cab_info and cab_info[2] else 1.0
    if aves_iniciales <= 0: aves_iniciales = 1.0

    cur.execute("""
        SELECT id, cons_tab, cons_kilos_real, mort, sel, otros, peso_real, sem, peso_tab
        FROM semanal_levante WHERE id_lote = %s ORDER BY sem ASC
    """, (id_lote,))
    filas = cur.fetchall()

    if not filas: return

    acum_kilos = 0.0
    acum_mort = 0.0
    acum_sel = 0.0
    acum_otros = 0.0
    valores_update = []
    acum_gr_ave_tab = 0.0
    
    # Manejo de alta precisión para coincidencia de índices técnicos
    acum_gr_ave_tab_exacto = 0.0
    gr_ave_tab_anterior_exacto = 0.0  
    
    peso_real_anterior = peso_recep if peso_recep > 0 else 0.0
    peso_tab_anterior = 35.0  
    gr_ave_ac_anterior_exacto = 0.0          

    for idx, f in enumerate(filas):
        f_id = f[0]
        c_tab = to_float_safe(f[1])
        c_k_real_manual = to_float_safe(f[2])
        m_sem_manual = to_float_safe(f[3])
        s_sem_manual = to_float_safe(f[4])
        o_sem_manual = to_float_safe(f[5])
        
        peso_real_val = to_float_safe(f[6])
        num_semana = int(f[7]) if f[7] is not None else (idx + 1)
        peso_tab_val = to_float_safe(f[8])

        # Definición de rangos temporales para agregación de la base de datos diaria
        dia_inicio, dia_fin = ((num_semana - 1) * 7) + 1, num_semana * 7

        cur.execute("SELECT COALESCE(SUM(consumo_kg), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
        res = cur.fetchone()
        c_k_real = to_float_safe(res[0]) if (res and res[0] > 0) else c_k_real_manual

        cur.execute("SELECT COALESCE(SUM(mortalidad), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
        res = cur.fetchone()
        m_sem = to_float_safe(res[0]) if (res and res[0] > 0) else m_sem_manual

        cur.execute("SELECT COALESCE(SUM(sel), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
        res = cur.fetchone()
        s_sem = to_float_safe(res[0]) if (res and res[0] > 0) else s_sem_manual

        cur.execute("SELECT COALESCE(SUM(otros), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
        res = cur.fetchone()
        o_sem = to_float_safe(res[0]) if (res and res[0] > 0) else o_sem_manual

        acum_kilos += c_k_real
        acum_mort += m_sem
        acum_sel += s_sem
        acum_otros += o_sem
        
        acum_gr_ave_tab_exacto += (c_tab * 7.0)

        tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or c_tab > 0 or peso_real_val > 0)
        acu_val = acum_mort + acum_sel + acum_otros
        acu_out = int(round(acu_val)) if tiene_datos else None
        saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

        p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
        p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and acum_mort > 0 and tiene_datos) else None
        p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
        p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

        c_k_acum_val = int(round(acum_kilos)) if (c_k_real > 0 or c_tab > 0) else None
        
        c_real_exacto = (c_k_real / float(saldo_val) / 7.0) * 1000.0 if (tiene_datos and saldo_val > 0) else None
        c_real_val = round(c_real_exacto, 1) if c_real_exacto is not None else None
        
        gr_ave_tab_val = int(round(acum_gr_ave_tab_exacto))
        
        gr_ave_ac_exacto = (float(acum_kilos) / float(saldo_val)) * 1000.0 if (acum_kilos > 0 and saldo_val > 0) else 0.0
        gr_ave_ac_val = int(round(gr_ave_ac_exacto))

        ganancia_ave_dia_val = round(peso_real_val - peso_real_anterior, 2) if (peso_real_val > 0 and peso_real_anterior > 0) else 0.0
        if peso_real_val > 0: peso_real_anterior = peso_real_val 

        ganancia_ave_val = round(peso_tab_val - peso_tab_anterior, 2) if (peso_tab_val > 0 and peso_tab_anterior > 0) else 0.0
        if peso_tab_val > 0: peso_tab_anterior = peso_tab_val 

        porc_cumpl_ganan_val = round(((ganancia_ave_dia_val / ganancia_ave_val) - 1.0) * 100.0, 2) if (ganancia_ave_dia_val > 0 and ganancia_ave_val > 0) else 0.0
        
        # Procesamiento matemático de las conversiones
        conv_sem_tab_val = 0.0
        if ganancia_ave_val > 0:
            diff_gr_tab_exacto = acum_gr_ave_tab_exacto - gr_ave_tab_anterior_exacto
            conv_sem_tab_val = round(diff_gr_tab_exacto / ganancia_ave_val, 2)
            
        gr_ave_tab_anterior_exacto = acum_gr_ave_tab_exacto
        
        conversion_sem_val = 0.0
        if c_k_real > 0 and ganancia_ave_dia_val > 0:
            diff_gramos_exacto = gr_ave_ac_exacto - gr_ave_ac_anterior_exacto
            conversion_sem_val = round(diff_gramos_exacto / ganancia_ave_dia_val, 2)
        
        gr_ave_ac_anterior_exacto = gr_ave_ac_exacto

        porc_cumpl_cons_val = 0.0
        if c_real_exacto is not None and c_real_exacto > 0 and c_tab > 0:
            porc_cumpl_cons_val = round(((c_real_exacto / c_tab) - 1.0) * 100.0, 2)

        try:
            val_ajustado = int(round(float(u_peso) * float(c_k_real)))
        except Exception:
            val_ajustado = 0

        valores_update.append((
            c_k_real, m_sem, s_sem, o_sem,
            c_real_val, c_k_acum_val, gr_ave_tab_val, gr_ave_ac_val,
            acu_out, p_mort_sem, p_mort_acum, p_sel_sem, p_ms_acu, saldo_val, 
            conversion_sem_val, ganancia_ave_dia_val, ganancia_ave_val, porc_cumpl_ganan_val,
            conv_sem_tab_val, val_ajustado, porc_cumpl_cons_val, f_id
        ))

    if valores_update:
        cur.executemany("""
            UPDATE semanal_levante 
            SET cons_kilos_real = %s, mort = %s, sel = %s, otros = %s,
                cons_real = %s, cons_k_acum = %s, cons_gr_ave_tab = %s, cons_gr_ave_ao = %s,
                acu = %s, porc_mort_sem = %s, porc_mort_acm = %s, porc_sel_sem = %s, porc_ms_acu = %s, 
                saldo_aves = %s, conv_sem = %s, ganancia_ave_dia = %s, ganancia_ave = %s, porc_cumpl_ganan = %s,
                conv_sem_tab = %s, cons_kilos_ajustado = %s, porc_cumpl_cons = %s
            WHERE id = %s                      
        """, valores_update)