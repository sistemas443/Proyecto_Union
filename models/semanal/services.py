# models/semanal/services.py

from datetime import datetime, timedelta, date
from models.base import get_db_connection, parse_empty, to_float_safe
from models.semanal.schemas import COLUMNAS_PERMITIDAS
from models.semanal import model
from models.cabecera.model import fetch_cabecera_by_lote

# Las siguientes funciones contienen las curvas estándar de la genética del ave.

def obtener_guia_prod_huevo_tab():
    guia = [
        7.7, 27.1, 57.3, 80.5, 90.6, 94.1, 95.5, 96.2, 96.4, 96.6,
        96.6, 96.6, 96.5, 96.5, 96.5, 96.3, 96.1, 96.0, 95.8, 95.7,
        95.5, 95.3, 95.0, 94.9, 94.6, 94.4, 94.1, 93.8, 93.5, 93.3,
        93.1, 92.8, 92.7, 92.4, 92.2, 91.9, 91.7, 91.5, 91.4, 91.2,
        91.0, 90.8, 90.5, 90.2, 90.0, 89.8, 89.6, 89.3, 89.0, 88.6,
        88.3, 88.0, 87.6, 87.0, 86.4, 85.8, 85.2, 84.6, 84.0, 83.4,
        82.8, 82.2, 81.6, 81.0, 80.4, 79.8, 79.2, 78.6, 78.0, 77.4,
        76.8, 76.3, 75.8, 75.3, 74.9, 74.5, 74.1, 73.7, 73.3, 72.9,
        72.5, 72.1, 71.7, 70.0, 70.0, 70.0, 69.0, 69.0, 68.0, 68.0,
        67.0, 67.0, 66.0
    ]
    guia += [66.0] * 50 
    return guia

def obtener_guia_h_av_aloj_tab():
    guia = [
        0.5, 2.4, 6.4, 12.1, 18.4, 25.0, 31.6, 38.3, 45.0, 51.8,
        58.5, 65.2, 71.9, 78.6, 85.3, 92.0, 98.7, 105.3, 111.9, 118.6,
        125.2, 131.8, 138.3, 144.9, 151.4, 157.9, 164.4, 170.9, 177.3, 183.8,
        190.2, 196.5, 202.9, 209.3, 215.6, 221.9, 228.2, 234.4, 240.7, 246.9,
        253.2, 259.4, 265.5, 271.7, 277.8, 283.9, 290.0, 296.1, 302.1, 308.1,
        314.1, 320.1, 326.0, 331.9, 337.7, 343.5, 349.2, 354.9, 360.5, 366.1,
        371.6, 377.1, 382.5, 387.9, 393.2, 398.5, 403.7, 408.9, 414.1, 419.2,
        424.2, 429.2, 434.2, 439.1, 444.0, 448.8, 453.6, 458.4, 463.2, 467.9,
        472.5, 477.2, 481.8
    ]
    guia += [481.8] * 50
    return guia

def obtener_guia_consumo_alim_tab():
    guia = [88.0, 94.0, 99.0, 103.0, 107.0, 108.0, 108.0, 108.0]
    guia += [109.0] * 16
    guia += [108.0] * 49
    guia += [105.0] * 50
    return guia

def obtener_guia_mort_tab():
    guia = [
        0.05, 0.08, 0.13, 0.20, 0.27, 0.34, 0.40, 0.46, 0.50, 0.55,
        0.61, 0.66, 0.71, 0.76, 0.80, 0.86, 0.92, 0.97, 1.02, 1.08,
        1.12, 1.18, 1.24, 1.30, 1.35, 1.41, 1.47, 1.52, 1.59, 1.64,
        1.70, 1.76, 1.83, 1.89, 1.95, 2.01, 2.09, 2.16, 2.24, 2.33,
        2.40, 2.49, 2.57, 2.65, 2.77, 2.85, 2.92, 2.97, 3.08, 3.14,
        3.20, 3.30, 3.43, 3.58, 3.73, 3.88, 4.03, 4.18, 4.33, 4.48,
        4.63, 4.78, 4.93, 5.08, 5.23, 5.38, 5.53, 5.68, 5.83, 5.98,
        6.13, 6.28, 6.45, 6.65, 6.85, 7.10, 7.30, 7.50, 7.60, 7.80,
        8.00, 8.20, 8.40
    ]
    guia += [8.40] * 50
    return guia

def obtener_guia_peso_ave_tab():
    guia = [
        1670, 1740, 1800, 1850, 1890, 1890, 1900, 1910, 1920, 1940,
        1950, 1960, 1980, 1980, 1990, 1990, 2000, 2010, 2010, 2010,
        2020, 2020, 2020, 2020, 2020
    ]
    guia += [2030] * 70
    return guia

def obtener_guia_peso_huevo_tab():
    guia = [
        46.50, 49.30, 51.60, 53.50, 55.00, 56.40, 57.50, 58.40, 59.20, 59.90,
        60.40, 60.90, 61.30, 61.70, 62.00, 62.30, 62.50, 62.70, 62.90, 63.10,
        63.20, 63.30, 63.40, 63.50, 63.60, 63.70, 63.80, 63.90, 63.90, 64.00,
        64.00, 64.10, 64.10, 64.20, 64.20, 64.30, 64.30, 64.30, 64.40, 64.40,
        64.40, 64.50, 64.50, 64.60, 64.60, 64.60, 64.60, 64.70, 64.70, 64.70,
        64.70, 64.80, 64.80, 64.80, 64.90, 64.90, 64.90, 64.90, 64.90, 65.00,
        65.00, 65.00, 65.00, 65.00, 65.10, 65.10, 65.10, 65.10, 65.20, 65.20,
        65.20, 65.20, 65.30, 65.30, 65.30, 65.30, 65.30, 65.40, 65.40, 65.40,
        65.40, 65.40, 65.50
    ]
    guia += [65.50] * 50
    return guia

def obtener_guia_masa_huevo_tab_sem():
    guia = [
        50, 100, 200, 300, 400, 400, 400, 400, 300, 400,
        400, 400, 400, 400, 400, 400, 400, 400, 400, 400,
        400, 400, 400, 400, 400, 400, 400, 400, 300, 400,
        400, 400, 400, 300, 400, 400, 400, 300, 400, 400,
        300, 400, 400, 300, 400, 300, 400, 400, 300, 400,
        300, 400, 300, 300, 400, 300, 300, 400, 300, 300,
        300, 400, 300, 300, 300, 400, 300, 300, 300, 400,
        300, 300
    ]
    guia += [300] * 50
    return guia

def obtener_guia_masa_huevo_tab_acum():
    guia = [
        0.0, 0.1, 0.2, 0.5, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8,
        3.2, 3.6, 4.0, 4.4, 4.8, 5.2, 5.6, 6.0, 6.4, 6.9,
        7.3, 7.7, 8.1, 8.5, 8.9, 9.3, 9.7, 10.1, 10.5, 10.9,
        11.4, 11.8, 12.2, 12.6, 13.0, 13.4, 13.8, 14.2, 14.5, 14.9,
        15.3, 15.7, 16.1, 16.5, 16.9, 17.3, 17.7, 18.1, 18.4, 18.8,
        19.2, 19.6, 20.0, 20.3, 20.7, 21.1, 21.4, 21.8, 22.1, 22.5,
        22.8, 23.2, 23.5, 23.9, 24.2, 24.5, 24.9, 25.2, 25.5, 25.9,
        26.2, 26.5, 26.8, 27.1, 27.4, 27.8, 28.1, 28.4, 28.7, 29.0,
        29.3, 29.6, 29.9
    ]
    # Rellenamos las semanas restantes manteniendo el tope de 29.9 para lotes viejos
    guia += [29.9] * 50
    return guia

def obtener_guia_cons_agua_tab():
    guia = [176, 188, 198, 206, 214, 216, 216, 216]
    guia += [218] * 14
    guia += [216] * 61
    guia += [210] * 10
    guia += [210] * 50
    return guia

def generar_estructura_semanal_unificada(lote_nombre, fecha_encasetamiento, id_lote):
    if not id_lote or not lote_nombre:
        return
    if model.count_semanal(id_lote) > 0:
        return
        
    fecha_base = None
    if fecha_encasetamiento and str(fecha_encasetamiento).strip() != '':
        try:
            fecha_base = datetime.strptime(str(fecha_encasetamiento), '%Y-%m-%d')
        except ValueError:
            pass
            
    valores = []
    # Genera semanas desde la 18 hasta la 110
    for i in range(18, 111):
        semana_vida = i
        fecha_str = None
        if fecha_base:
            dias_a_sumar = 6 + ((semana_vida - 18) * 7)
            fecha_str = (fecha_base + timedelta(days=dias_a_sumar)).strftime('%Y-%m-%d')
        valores.append((lote_nombre, id_lote, fecha_str, semana_vida))
    model.insert_estructura_semanal(valores)

def aplicar_parche_fechas_semanal(id_lote, fecha_encasetamiento, rows):
    if not fecha_encasetamiento or str(fecha_encasetamiento).strip() == '':
        return False
        
    try:
        fecha_base = datetime.strptime(str(fecha_encasetamiento), '%Y-%m-%d')
        conn = get_db_connection()
        cur = conn.cursor()
        actualizado = False
        
        for i, f in enumerate(rows):
            id_sem_prod = f['id_sem_prod']
            dias_a_sumar = 6 + (i * 7)
            fecha_correcta = (fecha_base + timedelta(days=dias_a_sumar)).strftime('%Y-%m-%d')
            fecha_actual = f['fecha_fin_sem']
            
            if fecha_actual != fecha_correcta:
                cur.execute("UPDATE bd_vargas SET fecha_fin_sem = %s WHERE id_sem_prod = %s", (fecha_correcta, id_sem_prod))
                actualizado = True
                
        if actualizado:
            conn.commit()
        return actualizado
    except Exception as e:
        print(f"[ERROR PARCHE FECHAS]: {e}")
        return False
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

def aplicar_parche_guias_semanal(id_lote):
    # Inyecta valores guía de genética en celdas vacías y fuerza la actualización de masa_huevo_tab_acum
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        guia_prod = obtener_guia_prod_huevo_tab()
        guia_aloj = obtener_guia_h_av_aloj_tab()
        guia_cons = obtener_guia_consumo_alim_tab()
        guia_mort = obtener_guia_mort_tab()
        guia_peso = obtener_guia_peso_ave_tab()
        guia_peso_huevo = obtener_guia_peso_huevo_tab()
        guia_masa_sem = obtener_guia_masa_huevo_tab_sem()
        guia_masa_acum = obtener_guia_masa_huevo_tab_acum()
        guia_agua = obtener_guia_cons_agua_tab()
        
        cur.execute("SELECT id_sem_prod, sem_prod, prod_huevo_tab, h_av_aloj_tab, consumo_alim_tab, mort_tab, peso_ave_tab, peso_huevo_tab, masa_huevo_tab_sem, masa_huevo_tab_acum, cons_agua_tab FROM bd_vargas WHERE id_lote = %s ORDER BY sem_prod ASC", (id_lote,))
        filas = cur.fetchall()
        valores_update = []
        
        for fila in filas:
            id_sem_prod = fila[0]
            sem_prod = int(fila[1]) if fila[1] else 18
            val_prod = fila[2]
            val_aloj = fila[3]
            val_cons = fila[4]
            val_mort = fila[5]
            val_peso = fila[6]
            val_peso_huevo = fila[7]
            val_masa_sem = fila[8]
            val_masa_acum = fila[9]
            val_agua = fila[10]
            
            idx = sem_prod - 18
            
            upd_prod, upd_aloj, upd_cons = val_prod, val_aloj, val_cons
            upd_mort, upd_peso, upd_peso_huevo = val_mort, val_peso, val_peso_huevo
            upd_masa_sem, upd_masa_acum, upd_agua = val_masa_sem, val_masa_acum, val_agua
            necesita_update = False
            
            if 0 <= idx < len(guia_prod):
                if val_prod is None or str(val_prod).strip() in ('', '0', '0.0', 'None'):
                    upd_prod = guia_prod[idx]
                    necesita_update = True
            
            if 0 <= idx < len(guia_aloj):
                if val_aloj is None or str(val_aloj).strip() in ('', '0', '0.0', 'None'):
                    upd_aloj = guia_aloj[idx]
                    necesita_update = True
                    
            if 0 <= idx < len(guia_cons):
                if val_cons is None or str(val_cons).strip() in ('', '0', '0.0', 'None'):
                    upd_cons = guia_cons[idx]
                    necesita_update = True
                    
            if 0 <= idx < len(guia_mort):
                if val_mort is None or str(val_mort).strip() in ('', '0', '0.0', 'None'):
                    upd_mort = guia_mort[idx]
                    necesita_update = True
                    
            if 0 <= idx < len(guia_peso):
                if val_peso is None or str(val_peso).strip() in ('', '0', '0.0', 'None'):
                    upd_peso = guia_peso[idx]
                    necesita_update = True
                    
            if 0 <= idx < len(guia_peso_huevo):
                if val_peso_huevo is None or str(val_peso_huevo).strip() in ('', '0', '0.0', 'None'):
                    upd_peso_huevo = guia_peso_huevo[idx]
                    necesita_update = True

            if 0 <= idx < len(guia_masa_sem):
                if val_masa_sem is None or str(val_masa_sem).strip() in ('', '0', '0.0', 'None'):
                    upd_masa_sem = guia_masa_sem[idx]
                    necesita_update = True
                    
            if 0 <= idx < len(guia_masa_acum):
                # Parche forzado sin restricción de celda vacía para corregir lotes viejos
                if to_float_safe(val_masa_acum) != guia_masa_acum[idx]:
                    upd_masa_acum = guia_masa_acum[idx]
                    necesita_update = True
                    
            if 0 <= idx < len(guia_agua):
                if val_agua is None or str(val_agua).strip() in ('', '0', '0.0', 'None'):
                    upd_agua = guia_agua[idx]
                    necesita_update = True
                    
            if necesita_update:
                valores_update.append((upd_prod, upd_aloj, upd_cons, upd_mort, upd_peso, upd_peso_huevo, upd_masa_sem, upd_masa_acum, upd_agua, id_sem_prod))
                
        if valores_update:
            cur.executemany("UPDATE bd_vargas SET prod_huevo_tab = %s, h_av_aloj_tab = %s, consumo_alim_tab = %s, mort_tab = %s, peso_ave_tab = %s, peso_huevo_tab = %s, masa_huevo_tab_sem = %s, masa_huevo_tab_acum = %s, cons_agua_tab = %s WHERE id_sem_prod = %s", valores_update)
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR PARCHE GUIAS SEMANAL]: {e}")
    finally:
        cur.close()
        conn.close()

def get_semanal_all(lote_nombre: str = ''):
    # Orquestador inicial
    if not lote_nombre or lote_nombre == 'VACIO':
        return []
    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera:
        return []
    id_lote = cabecera['id']
    rows = model.fetch_semanal_produccion(id_lote)
    
    if len(rows) == 0:
        generar_estructura_semanal_unificada(lote_nombre, cabecera.get('fecha_encasetamiento'), id_lote)
        rows = model.fetch_semanal_produccion(id_lote)
        
    aplicar_parche_fechas_semanal(id_lote, cabecera.get('fecha_encasetamiento'), rows)
    aplicar_parche_guias_semanal(id_lote)
        
    filas_db = model.fetch_semanal_produccion(id_lote)
    
    # CÁLCULO DE ACUMULADOS Y CONVERSIONES EN EL BACKEND
    filas_procesadas = []
    acumulado_huevos = 0
    acumulado_consumo = 0
    
    for f in filas_db:
        # Convertimos la fila de la BD a un diccionario manipulable
        try:
            fila_dict = dict(f)
        except Exception:
            fila_dict = f
            
        base_huevos = float(fila_dict.get('prod_tab_unidad_huevo') or 0)
        base_consumo = float(fila_dict.get('consumo_kg_tab_graf') or 0)
        
        # Rompemos la cascada: Solo suma si hay datos reales en esta semana
        if base_huevos > 0 or base_consumo > 0:
            if base_huevos > 0: acumulado_huevos += base_huevos
            if base_consumo > 0: acumulado_consumo += base_consumo
            
            fila_dict['huevos_acum_tab'] = int(round(acumulado_huevos))
            fila_dict['consumo_acum_tab'] = int(round(acumulado_consumo))
            
            if acumulado_huevos > 0:
                conversion = round((acumulado_consumo / acumulado_huevos) * 1200, 2)
                fila_dict['conv_acum_tab_1'] = conversion
                fila_dict['conv_acum_tab_2'] = conversion
            else:
                fila_dict['conv_acum_tab_1'] = ''
                fila_dict['conv_acum_tab_2'] = ''
        else:
            fila_dict['huevos_acum_tab'] = ''
            fila_dict['consumo_acum_tab'] = ''
            fila_dict['conv_acum_tab_1'] = ''
            fila_dict['conv_acum_tab_2'] = ''
            
        filas_procesadas.append(fila_dict)
        
    return filas_procesadas

# FUNCIÓN CENTRAL DE MATEMÁTICA Y LÓGICA DE NEGOCIO
def update_semanal_field(id_semanal: int, columna: str, valor: str) -> tuple[bool, dict, str]:
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

        columnas_matematicas = [
            'cons_tab', 'gr_tb', 'consumo_alim_tab',
            'cons_kilos_real', 'consumo_alim_kg', 
            'mort_sem', 'mort_select_sem', 'mort_venta', 
            'peso_real', 'peso_ave_real',
            'porcentaje_prod_tb', 'precio_dieta', 'porcentaje_huevo_nc',
            'prod_huevo_sem', 'prod_huevo_tab', 'h_av_aloj_tab', 'mort_tab', 'peso_ave_tab',
            'peso_huevo_tab', 'masa_huevo_tab_sem', 'masa_huevo_tab_acum', 'cons_agua_tab',
            'prod_huevo_real', 'h_av_aloj_real', 'ganancia_ave_dia', 'percent_mort_acum', 
            'conv_kg_doc_acum', 'peso_huevo_real', 'consumo_alim_real',
            'conv_sem_real', 'conv_acum_real', 'masa_huevo_real_sem', 'masa_huevo_real_acum', 'cons_agua_real'
        ]

        if id_lote and (columna in columnas_matematicas):
            cur.execute("SELECT no_aves_encasetadas, peso, unidad_peso FROM cabecera_lotes WHERE id = %s", (id_lote,))
            cab_info = cur.fetchone()
            
            aves_iniciales = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 1.0
            if aves_iniciales <= 0: aves_iniciales = 1.0
            peso_recep = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 0.0
            
            multiplicador_unidad = to_float_safe(cab_info[2]) if cab_info and len(cab_info) > 2 and cab_info[2] else 1.0

            col_db = columna
            if columna in ['cons_tab', 'gr_tb']: col_db = 'consumo_alim_tab'
            elif columna in ['cons_kilos_real']: col_db = 'consumo_alim_kg'
            elif columna in ['peso_real']: col_db = 'peso_ave_real'

            cur.execute(f"UPDATE bd_vargas SET {col_db} = %s WHERE id_sem_prod = %s", (valor_db, id_semanal))
            
            if columna == 'prod_huevo_real':
                cur.execute("UPDATE bd_vargas SET porcentaje_prod_real = %s WHERE id_sem_prod = %s", (valor_db, id_semanal))
            if columna == 'h_av_aloj_real':
                cur.execute("UPDATE bd_vargas SET haa_real = %s WHERE id_sem_prod = %s", (valor_db, id_semanal))
            if columna == 'consumo_alim_real':
                cur.execute("UPDATE bd_vargas SET gr_ave_dia_graf = %s WHERE id_sem_prod = %s", (valor_db, id_semanal))
            if columna == 'percent_mort_acum':
                cur.execute("UPDATE bd_vargas SET porcentaje_mort_acum_graf = %s WHERE id_sem_prod = %s", (valor_db, id_semanal))

            cur.execute("""
                SELECT id_sem_prod, consumo_alim_tab, consumo_alim_kg, mort_sem, mort_select_sem, mort_venta, 
                       peso_ave_real, sem_prod, porcentaje_prod_tb, precio_dieta, porcentaje_huevo_nc,
                       h_av_aloj_tab, h_av_aloj_real, peso_huevo_real, conv_kg_doc_acum, prod_huevo_tab,
                       mort_tab, peso_ave_tab, peso_huevo_tab, masa_huevo_tab_sem, masa_huevo_tab_acum, cons_agua_tab,
                       prod_huevo_real, percent_mort_acum, ganancia_ave_dia, prod_huevo_sem,
                       conv_sem_real, conv_acum_real, cons_agua_real
                FROM bd_vargas 
                WHERE id_lote = %s ORDER BY sem_prod ASC
            """, (id_lote,))
            filas = cur.fetchall()

            acum_kilos, acum_gr_ave_tab, acum_mort, acum_sel, acum_otros = 0.0, 0.0, 0.0, 0.0, 0.0
            acum_huevos_tab = 0.0
            acum_consumo_tab = 0.0
            acum_huevos_real = 0.0
            acum_kaa = 0.0  
            acum_c_tab_sum = 0.0
            acum_porc_prod_tb_sum = 0.0
            prev_haa_real = 0.0
            acum_masa_huevo_real = 0.0
            valores_update = []

            for idx, f in enumerate(filas):
                f_id = f[0]
                num_semana = int(f[7]) if f[7] is not None else (idx + 1)
                dia_inicio = ((num_semana - 1) * 7) + 1
                dia_fin = num_semana * 7

                c_tab = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['cons_tab', 'gr_tb', 'consumo_alim_tab']) else to_float_safe(f[1])
                c_k_real = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['cons_kilos_real', 'consumo_alim_kg']) else to_float_safe(f[2])
                m_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_sem') else to_float_safe(f[3])
                s_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_select_sem') else to_float_safe(f[4])
                o_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_venta') else to_float_safe(f[5])
                peso_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['peso_real', 'peso_ave_real']) else to_float_safe(f[6])
                porc_prod_tb = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'porcentaje_prod_tb') else to_float_safe(f[8])
                precio_dieta = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'precio_dieta') else to_float_safe(f[9])
                porc_huevo_nc = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'porcentaje_huevo_nc') else to_float_safe(f[10])
                
                h_av_aloj_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'h_av_aloj_tab') else to_float_safe(f[11])
                prod_huevo_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'prod_huevo_tab') else to_float_safe(f[15])
                mort_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_tab') else to_float_safe(f[16])
                peso_ave_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'peso_ave_tab') else to_float_safe(f[17])
                peso_huevo_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'peso_huevo_tab') else to_float_safe(f[18])
                masa_huevo_tab_sem_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'masa_huevo_tab_sem') else to_float_safe(f[19])
                masa_huevo_tab_acum_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'masa_huevo_tab_acum') else to_float_safe(f[20])
                cons_agua_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_agua_tab') else to_float_safe(f[21])

                prod_huevo_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'prod_huevo_real') else to_float_safe(f[22])
                h_av_aloj_real = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'h_av_aloj_real') else to_float_safe(f[12])
                p_mort_acum = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'percent_mort_acum') else to_float_safe(f[23])
                ganancia_ave_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'ganancia_ave_dia') else to_float_safe(f[24])
                peso_huevo_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'peso_huevo_real') else to_float_safe(f[13])

                cur.execute("SELECT COUNT(*) FROM data_diario WHERE id_lote = %s", (id_lote,))
                usa_diario = cur.fetchone()[0] > 0

                cur.execute("SELECT COALESCE(SUM(consumo_kg), 0), COALESCE(SUM(mortalidad), 0), COALESCE(SUM(sel), 0), COALESCE(SUM(otros), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
                res_estricto = cur.fetchone()
                
                if usa_diario:
                    c_k_real = to_float_safe(res_estricto[0]) if res_estricto else 0.0
                    m_sem = to_float_safe(res_estricto[1]) if res_estricto else 0.0
                    s_sem = to_float_safe(res_estricto[2]) if res_estricto else 0.0
                    o_sem = to_float_safe(res_estricto[3]) if res_estricto else 0.0
                else:
                    if res_estricto:
                        if res_estricto[0] > 0: c_k_real = to_float_safe(res_estricto[0])
                        if res_estricto[1] > 0: m_sem = to_float_safe(res_estricto[1])
                        if res_estricto[2] > 0: s_sem = to_float_safe(res_estricto[2])
                        if res_estricto[3] > 0: o_sem = to_float_safe(res_estricto[3])

                db_prod_sem = to_float_safe(f[25])
                
                if num_semana <= 18:
                    cur.execute("SELECT COALESCE(SUM(produccion), 0) FROM data_diario WHERE id_lote = %s AND dias <= %s", (id_lote, dia_fin))
                else:
                    cur.execute("SELECT COALESCE(SUM(produccion), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
                
                res_huevos = cur.fetchone()
                diarios_huevos = to_float_safe(res_huevos[0]) if res_huevos else 0.0

                val_ingresado = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'prod_huevo_sem') else db_prod_sem
                huevos_semana = diarios_huevos if usa_diario else val_ingresado
                tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or peso_real_val > 0 or huevos_semana > 0)
                prod_huevo_sem_val = int(round(huevos_semana)) if huevos_semana > 0 else None

                acum_kilos += c_k_real
                acum_gr_ave_tab += (c_tab * 7)
                acum_mort += m_sem
                acum_sel += s_sem
                acum_otros += o_sem

                acu_val = acum_mort + acum_sel + acum_otros
                acu_out = int(round(acu_val)) if tiene_datos else None
                saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

                # FRENO DE CASCADA: %M Ac
                if tiene_datos:
                    calculo_p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if aves_iniciales > 0 else 0.0
                    p_mort_acum = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'percent_mort_acum') else calculo_p_mort_acum
                else:
                    p_mort_acum = None
                porcentaje_mort_acum_graf = p_mort_acum

                p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
                p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
                
                # Freno de cascada para %M Ac- AVES
                p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

                if saldo_val > 0 and c_k_real > 0:
                    acum_kaa += (c_k_real / float(saldo_val))
                
                # Freno de cascada para K.A.A
                c_kaa_val = round(acum_kaa, 3) if (acum_kaa > 0 and tiene_datos) else None

                if c_tab and porc_prod_tb and porc_prod_tb > 0:
                    conversion_sem_val = round((c_tab * 100 / porc_prod_tb) * 12, 2)
                else: 
                    conversion_sem_val = 0.0

                if c_tab: acum_c_tab_sum += float(c_tab)
                if porc_prod_tb: acum_porc_prod_tb_sum += float(porc_prod_tb)

                if acum_porc_prod_tb_sum > 0:
                    conv_acum = round((acum_c_tab_sum * 100 / acum_porc_prod_tb_sum) * 12, 2)
                else:
                    conv_acum = 0.0
                
                if tiene_datos and c_k_real > 0 and saldo_val > 0:
                    calculo_c_real = round((c_k_real / float(saldo_val) / 7.0) * 1000.0, 1)
                    c_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'consumo_alim_real') else calculo_c_real
                else:
                    c_real_val = 0.0 if tiene_datos else None
                
                gr_ave_ac_val = int(round((acum_kilos / float(saldo_val)) * 1000.0)) if (acum_kilos > 0 and saldo_val > 0) else 0

                if ganancia_ave_val is None:
                    ganancia_ave_val = round(peso_real_val - peso_recep, 2) if (peso_real_val > 0 and peso_recep > 0) else 0.0
                gr_ave_dia_graf = ganancia_ave_val
                
                salidas_semana = m_sem + s_sem + o_sem
                
                # Freno de cascada y 1 decimal para % Prod Real
                if tiene_datos and prod_huevo_sem_val is not None and saldo_val > 0:
                    calculo_real = round((prod_huevo_sem_val / 7.0 / saldo_val) * 100, 1)
                    prod_huevo_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'prod_huevo_real') else calculo_real
                else:
                    prod_huevo_real_val = None
                porcentaje_prod_real = prod_huevo_real_val

                # Huevos acumulados por Ave Alojada
                if prod_huevo_sem_val:
                    acum_huevos_real += float(prod_huevo_sem_val)
                    
                # Freno de cascada y 1 decimal para H.AV.ALOJ
                if aves_iniciales > 0 and tiene_datos:
                    calculo_haa = round(acum_huevos_real / aves_iniciales, 1)
                    h_av_aloj_real = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'h_av_aloj_real') else calculo_haa
                else:
                    h_av_aloj_real = None
                haa_real = h_av_aloj_real

                # FRENO ESTRICTO: Solo calcula H. Acum si hay producción de huevos esta semana
                if prod_huevo_sem_val is not None and prod_huevo_sem_val > 0:
                    huevo_acum_val = int(round(acum_huevos_real))
                else:
                    huevo_acum_val = None
                    
                # FRENO ESTRICTO: Solo calcula Kilos si hay consumo registrado esta semana
                if c_k_real > 0:
                    kg_acum_val = round(acum_kilos, 2)
                    kg_sem_val = round(c_k_real * multiplicador_unidad, 2)
                else:
                    kg_acum_val = None
                    kg_sem_val = None

                # FÓRMULA DE CONVERSIÓN KG/DOC ACUM
                if acum_huevos_real > 0 and ((prod_huevo_sem_val and prod_huevo_sem_val > 0) or c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0):
                    conv_kg_doc_acum_val = round((acum_kilos / acum_huevos_real) * 12, 2)
                else:
                    conv_kg_doc_acum_val = 0.0

                # FÓRMULAS DE CONVERSIÓN REAL
                if tiene_datos and prod_huevo_sem_val and float(prod_huevo_sem_val) > 0:
                    calculo_conv_sem = round((c_k_real / float(prod_huevo_sem_val)) * 12, 3)
                    conv_sem_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'conv_sem_real') else calculo_conv_sem
                else:
                    conv_sem_real_val = 0.0 if tiene_datos else None

                if tiene_datos and acum_huevos_real > 0:
                    calculo_conv_acum = round((acum_kilos / acum_huevos_real) * 12, 3)
                    conv_acum_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'conv_acum_real') else calculo_conv_acum
                else:
                    conv_acum_real_val = 0.0 if tiene_datos else None

                # CÁLCULOS DE MASA DE HUEVO
                if tiene_datos and peso_huevo_real_val and peso_huevo_real_val > 0 and haa_real is not None:
                    if num_semana <= 18:
                        masa_huevo_real_sem_val = int(round(peso_huevo_real_val * haa_real))
                    else:
                        masa_huevo_real_sem_val = int(round(peso_huevo_real_val * (haa_real - prev_haa_real)))
                else:
                    masa_huevo_real_sem_val = 0 if tiene_datos else None

                if tiene_datos and masa_huevo_real_sem_val is not None and masa_huevo_real_sem_val > 0:
                    acum_masa_huevo_real += float(masa_huevo_real_sem_val)
                    masa_huevo_real_acum_val = int(round(acum_masa_huevo_real))
                else:
                    masa_huevo_real_acum_val = 0 if tiene_datos else None

                # FRENO DE CASCADA: Consumo de Agua Real
                if tiene_datos:
                    if num_semana <= 18:
                        cons_agua_real_val = masa_huevo_real_acum_val
                    else:
                        cons_agua_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_agua_real') else to_float_safe(f[28])
                else:
                    cons_agua_real_val = None

                prev_haa_real = haa_real if haa_real is not None else 0.0

                # LÍMITES DE TOLERANCIA DE PRODUCCIÓN
                porc_prod_tb = prod_huevo_tab_val
                margen_tolerancia = 0.04 
                if porc_prod_tb:
                    porcentaje_tb = round(porc_prod_tb * (1 - margen_tolerancia), 2)
                    porcentaje_tx = round(porc_prod_tb * (1 + margen_tolerancia), 2)
                    porcentaje_rx = round(porcentaje_tx - porcentaje_tb, 2)
                    
                    # FRENO DE CASCADA: Producción Tab-Unidad-Huevo
                    if tiene_datos and saldo_val > 0:
                        prod_tab_unidad_huevo = round((porc_prod_tb / 100.0) * saldo_val * 7, 2)
                    else:
                        prod_tab_unidad_huevo = None
                else:
                    porcentaje_tb = porcentaje_tx = porcentaje_rx = prod_tab_unidad_huevo = None

                if c_tab and saldo_val > 0 and c_real_val is not None:
                    consumo_kg_tab_graf = (float(c_tab) / 100.0) * float(saldo_val) * 7.0 * (float(c_real_val) / 1000.0)
                else:
                    consumo_kg_tab_graf = None

                if prod_tab_unidad_huevo: acum_huevos_tab += prod_tab_unidad_huevo
                if consumo_kg_tab_graf: acum_consumo_tab += consumo_kg_tab_graf
                
                acum_huevos_tab_val = int(round(acum_huevos_tab)) if acum_huevos_tab > 0 else None
                acum_consumo_tab_val = round(acum_consumo_tab, 2) if acum_consumo_tab > 0 else None

                if tiene_datos and prod_huevo_sem_val is not None:
                    cant_unidades_perdida = round((porc_huevo_nc / 100.0) * prod_huevo_sem_val, 2)
                    total_huevo_real = round(float(prod_huevo_sem_val) - cant_unidades_perdida, 2)
                else:
                    cant_unidades_perdida = total_huevo_real = None

                gr_por_huevo = round((c_k_real * 1000.0) / prod_huevo_sem_val, 1) if (tiene_datos and prod_huevo_sem_val and prod_huevo_sem_val > 0) else None
                costo_huevo = round((c_k_real * 1000.0 / total_huevo_real) * (precio_dieta / 1000.0), 2) if (tiene_datos and total_huevo_real and total_huevo_real > 0 and precio_dieta) else None
                
                # Suma Saldo Aves entero redondeado
                suma_saldo_aves = int(round((saldo_val * 7) + (salidas_semana * 3.5))) if tiene_datos else None

                valores_update.append((
                    c_k_real, m_sem, s_sem, o_sem,
                    c_real_val, c_kaa_val, c_tab, acu_out, p_mort_sem, p_mort_acum,
                    p_sel_sem, p_ms_acu, saldo_val, conversion_sem_val, ganancia_ave_val, prod_huevo_sem_val,
                    prod_huevo_real_val, 
                    
                    num_semana, porc_prod_tb, porcentaje_tb, porcentaje_tx, porcentaje_rx,
                    h_av_aloj_tab_val, c_tab, porcentaje_prod_real, haa_real, h_av_aloj_real, gr_ave_dia_graf,
                    porcentaje_mort_acum_graf, conv_acum, gr_por_huevo, precio_dieta, costo_huevo,
                    prod_tab_unidad_huevo, consumo_kg_tab_graf, acum_huevos_tab_val, acum_consumo_tab_val,
                    porc_huevo_nc, total_huevo_real, cant_unidades_perdida, suma_saldo_aves, prod_huevo_tab_val,
                    mort_tab_val, peso_ave_tab_val, peso_huevo_tab_val, masa_huevo_tab_sem_val, masa_huevo_tab_acum_val, 
                    cons_agua_tab_val, conv_sem_real_val, conv_acum_real_val, masa_huevo_real_sem_val, masa_huevo_real_acum_val, 
                    cons_agua_real_val, conv_kg_doc_acum_val, huevo_acum_val, kg_acum_val, kg_sem_val, f_id
                ))

            if valores_update:
                cur.executemany("""
                    UPDATE bd_vargas 
                    SET consumo_alim_kg = %s, mort_sem = %s, mort_select_sem = %s, mort_venta = %s,
                        consumo_alim_real = %s, consumo_alim_k_a_a = %s, consumo_alim_tab = %s,
                        salidas_acum = %s, percent_mort_sem = %s, percent_mort_acum = %s, percent_select_sem = %s,
                        percent_mort_and_select_acum = %s, saldo_ave = %s, conv_sem_tab = %s, ganancia_ave_dia = %s,
                        prod_huevo_sem = %s, prod_huevo_real = %s,
                        sem_graf = %s, porcentaje_prod_tb = %s, porcentaje_tb = %s, porcentaje_tx = %s, porcentaje_rx = %s,
                        haa_tab = %s, gr_tb_graf = %s, porcentaje_prod_real = %s, haa_real = %s, h_av_aloj_real = %s, gr_ave_dia_graf = %s,
                        porcentaje_mort_acum_graf = %s, conv_acum_tab = %s, gr_por_huevo = %s, precio_dieta = %s, costo_huevo = %s,
                        prod_tab_unidad_huevo = %s, consumo_kg_tab_graf = %s, huevos_acum_tab = %s, consumo_acum_tab = %s,
                        porcentaje_huevo_nc = %s, total_huevo_real = %s, cant_unidades_perdida = %s, suma_saldo_aves = %s,
                        prod_huevo_tab = %s, mort_tab = %s, peso_ave_tab = %s, peso_huevo_tab = %s, masa_huevo_tab_sem = %s,
                        masa_huevo_tab_acum = %s, cons_agua_tab = %s, conv_sem_real = %s, conv_acum_real = %s,
                        masa_huevo_real_sem = %s, masa_huevo_real_acum = %s, cons_agua_real = %s,
                        conv_kg_doc_acum = %s, huevo_acum = %s, kg_acum = %s, kg_sem = %s
                    WHERE id_sem_prod = %s
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

# 2. FUNCIÓN DE RECÁLCULO MASIVO (Botón "Recalcular Tabla")
def recalcular_lote_semanal_completo_directo(id_lote, cur):
    cur.execute("SELECT no_aves_encasetadas, peso, unidad_peso FROM cabecera_lotes WHERE id = %s", (id_lote,))
    cab_info = cur.fetchone()
    aves_iniciales = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 1.0
    if aves_iniciales <= 0: aves_iniciales = 1.0
    peso_recep = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 0.0
    multiplicador_unidad = to_float_safe(cab_info[2]) if cab_info and len(cab_info) > 2 and cab_info[2] else 1.0

    cur.execute("""
        SELECT id_sem_prod, consumo_alim_tab, consumo_alim_kg, mort_sem, mort_select_sem, mort_venta, 
               peso_ave_real, sem_prod, porcentaje_prod_tb, precio_dieta, porcentaje_huevo_nc,
               h_av_aloj_tab, h_av_aloj_real, peso_huevo_real, conv_kg_doc_acum, prod_huevo_tab, mort_tab,
               peso_ave_tab, peso_huevo_tab, masa_huevo_tab_sem, masa_huevo_tab_acum, cons_agua_tab,
               prod_huevo_real, percent_mort_acum, ganancia_ave_dia, prod_huevo_sem,
               conv_sem_real, conv_acum_real, cons_agua_real
        FROM bd_vargas WHERE id_lote = %s ORDER BY sem_prod ASC
    """, (id_lote,))
    filas = cur.fetchall()

    acum_kilos, acum_gr_ave_tab, acum_mort, acum_sel, acum_otros = 0.0, 0.0, 0.0, 0.0, 0.0
    acum_huevos_tab = 0.0
    acum_consumo_tab = 0.0
    acum_huevos_real = 0.0
    acum_kaa = 0.0  
    acum_c_tab_sum = 0.0         
    acum_porc_prod_tb_sum = 0.0  
    prev_haa_real = 0.0
    acum_masa_huevo_real = 0.0
    valores_update = []

    for idx, f in enumerate(filas):
        f_id = f[0]
        num_semana = int(f[7]) if f[7] is not None else (idx + 1)
        dia_inicio = ((num_semana - 1) * 7) + 1
        dia_fin = num_semana * 7
        
        c_tab = to_float_safe(f[1])
        peso_real_val = to_float_safe(f[6])
        porc_prod_tb = to_float_safe(f[8])
        precio_dieta = to_float_safe(f[9])
        porc_huevo_nc = to_float_safe(f[10])
        h_av_aloj_tab_val = to_float_safe(f[11])
        prod_huevo_tab_val = to_float_safe(f[15])
        mort_tab_val = to_float_safe(f[16])
        peso_ave_tab_val = to_float_safe(f[17])
        peso_huevo_tab_val = to_float_safe(f[18])
        masa_huevo_tab_sem_val = to_float_safe(f[19])
        masa_huevo_tab_acum_val = to_float_safe(f[20])
        cons_agua_tab_val = to_float_safe(f[21])

        p_mort_acum = to_float_safe(f[23])
        ganancia_ave_val = to_float_safe(f[24])

        peso_huevo_real_val = to_float_safe(f[13])

        cur.execute("SELECT COUNT(*) FROM data_diario WHERE id_lote = %s", (id_lote,))
        usa_diario = cur.fetchone()[0] > 0

        cur.execute("""
            SELECT COALESCE(SUM(consumo_kg), 0), COALESCE(SUM(mortalidad), 0), COALESCE(SUM(sel), 0), COALESCE(SUM(otros), 0)
            FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s
        """, (id_lote, dia_inicio, dia_fin))
        res_sem = cur.fetchone()
        
        if usa_diario:
            c_k_real = to_float_safe(res_sem[0]) if res_sem else 0.0
            m_sem = to_float_safe(res_sem[1]) if res_sem else 0.0
            s_sem = to_float_safe(res_sem[2]) if res_sem else 0.0
            o_sem = to_float_safe(res_sem[3]) if res_sem else 0.0
        else:
            c_k_real = to_float_safe(res_sem[0]) if res_sem and res_sem[0] > 0 else to_float_safe(f[2])
            m_sem = to_float_safe(res_sem[1]) if res_sem and res_sem[1] > 0 else to_float_safe(f[3])
            s_sem = to_float_safe(res_sem[2]) if res_sem and res_sem[2] > 0 else to_float_safe(f[4])
            o_sem = to_float_safe(res_sem[3]) if res_sem and res_sem[3] > 0 else to_float_safe(f[5])

        if num_semana <= 18:
            cur.execute("SELECT COALESCE(SUM(produccion), 0) FROM data_diario WHERE id_lote = %s AND dias <= %s", (id_lote, dia_fin))
        else:
            cur.execute("SELECT COALESCE(SUM(produccion), 0) FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s", (id_lote, dia_inicio, dia_fin))
        
        res_huevos = cur.fetchone()
        diarios_huevos = to_float_safe(res_huevos[0]) if res_huevos else 0.0

        db_prod_sem = to_float_safe(f[25])
        huevos_semana = diarios_huevos if usa_diario else db_prod_sem
        tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or peso_real_val > 0 or huevos_semana > 0)
        prod_huevo_sem_val = int(round(huevos_semana)) if huevos_semana > 0 else None

        acum_kilos += c_k_real
        acum_gr_ave_tab += (c_tab * 7)
        acum_mort += m_sem
        acum_sel += s_sem
        acum_otros += o_sem

        acu_val = acum_mort + acum_sel + acum_otros
        acu_out = int(round(acu_val)) if tiene_datos else None
        saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

        # FRENO DE CASCADA: %M Ac
        if tiene_datos:
            p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if aves_iniciales > 0 else 0.0
        else:
            p_mort_acum = None
        porcentaje_mort_acum_graf = p_mort_acum

        p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
        p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
        
        # Freno de cascada %M Ac
        p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

        if saldo_val > 0 and c_k_real > 0:
            acum_kaa += (c_k_real / float(saldo_val))
            
        # Freno de cascada K.A.A
        c_kaa_val = round(acum_kaa, 3) if (acum_kaa > 0 and tiene_datos) else None

        if c_tab and porc_prod_tb and porc_prod_tb > 0:
            conversion_sem_val = round((c_tab * 100 / porc_prod_tb) * 12, 2)
        else: 
            conversion_sem_val = 0.0

        if c_tab:
            acum_c_tab_sum += float(c_tab)
        if porc_prod_tb:
            acum_porc_prod_tb_sum += float(porc_prod_tb)

        if acum_porc_prod_tb_sum > 0:
            conv_acum = round((acum_c_tab_sum * 100 / acum_porc_prod_tb_sum) * 12, 2)
        else:
            conv_acum = 0.0
        
        # 1 decimal Consumo Alimento Real
        if tiene_datos and c_k_real > 0 and saldo_val > 0:
            c_real_val = round((c_k_real / float(saldo_val) / 7.0) * 1000.0, 1)
        else:
            c_real_val = 0.0 if tiene_datos else None
            
        gr_ave_ac_val = int(round((acum_kilos / float(saldo_val)) * 1000.0)) if (acum_kilos > 0 and saldo_val > 0) else 0

        if ganancia_ave_val is None:
            ganancia_ave_val = round(peso_real_val - peso_recep, 2) if (peso_real_val > 0 and peso_recep > 0) else 0.0
        gr_ave_dia_graf = ganancia_ave_val
        salidas_semana = m_sem + s_sem + o_sem
        
        # Freno y 1 decimal % Prod Real
        if tiene_datos and prod_huevo_sem_val is not None and saldo_val > 0:
            prod_huevo_real_val = round((prod_huevo_sem_val / 7.0 / saldo_val) * 100, 1)
        else:
            prod_huevo_real_val = None
        porcentaje_prod_real = prod_huevo_real_val

        if prod_huevo_sem_val:
            acum_huevos_real += float(prod_huevo_sem_val)
            
        # Freno de cascada H.AV.ALOJ
        if aves_iniciales > 0 and tiene_datos:
            h_av_aloj_real = round(acum_huevos_real / aves_iniciales, 1)
        else:
            h_av_aloj_real = None
        haa_real = h_av_aloj_real
        
        # FRENO ESTRICTO: Solo calcula H. Acum si hay producción de huevos esta semana
        if prod_huevo_sem_val is not None and prod_huevo_sem_val > 0:
            huevo_acum_val = int(round(acum_huevos_real))
        else:
            huevo_acum_val = None
            
        # FRENO ESTRICTO: Solo calcula Kilos si hay consumo registrado esta semana
        if c_k_real > 0:
            kg_acum_val = round(acum_kilos, 2)
            kg_sem_val = round(c_k_real * multiplicador_unidad, 2)
        else:
            kg_acum_val = None
            kg_sem_val = None

        if acum_huevos_real > 0 and ((prod_huevo_sem_val and prod_huevo_sem_val > 0) or c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0):
            conv_kg_doc_acum_val = round((acum_kilos / acum_huevos_real) * 12, 2)
        else:
            conv_kg_doc_acum_val = 0.0

        if tiene_datos and prod_huevo_sem_val and float(prod_huevo_sem_val) > 0:
            conv_sem_real_val = round((c_k_real / float(prod_huevo_sem_val)) * 12, 3)
        else:
            conv_sem_real_val = 0.0 if tiene_datos else None

        if tiene_datos and acum_huevos_real > 0:
            conv_acum_real_val = round((acum_kilos / acum_huevos_real) * 12, 3)
        else:
            conv_acum_real_val = 0.0 if tiene_datos else None

        if tiene_datos and peso_huevo_real_val and peso_huevo_real_val > 0 and haa_real is not None:
            if num_semana <= 18:
                masa_huevo_real_sem_val = int(round(peso_huevo_real_val * haa_real))
            else:
                masa_huevo_real_sem_val = int(round(peso_huevo_real_val * (haa_real - prev_haa_real)))
        else:
            masa_huevo_real_sem_val = 0 if tiene_datos else None

        if tiene_datos and masa_huevo_real_sem_val is not None and masa_huevo_real_sem_val > 0:
            acum_masa_huevo_real += float(masa_huevo_real_sem_val)
            masa_huevo_real_acum_val = int(round(acum_masa_huevo_real))
        else:
            masa_huevo_real_acum_val = 0 if tiene_datos else None

        # FRENO DE CASCADA: Consumo Agua Real
        if tiene_datos:
            if num_semana <= 18:
                cons_agua_real_val = masa_huevo_real_acum_val
            else:
                cons_agua_real_val = to_float_safe(f[28])
        else:
            cons_agua_real_val = None

        prev_haa_real = haa_real if haa_real is not None else 0.0

        porc_prod_tb = prod_huevo_tab_val
        margen_tolerancia = 0.04
        if porc_prod_tb:
            porcentaje_tb = round(porc_prod_tb * (1 - margen_tolerancia), 2)
            porcentaje_tx = round(porc_prod_tb * (1 + margen_tolerancia), 2)
            porcentaje_rx = round(porcentaje_tx - porcentaje_tb, 2)
            prod_tab_unidad_huevo = round((porc_prod_tb / 100.0) * saldo_val * 7, 2)
        else:
            porcentaje_tb = porcentaje_tx = porcentaje_rx = prod_tab_unidad_huevo = None

        if c_tab and saldo_val > 0 and c_real_val is not None:
            consumo_kg_tab_graf = (float(c_tab) / 100.0) * float(saldo_val) * 7.0 * (float(c_real_val) / 1000.0)
        else:
            consumo_kg_tab_graf = None

        if prod_tab_unidad_huevo: acum_huevos_tab += prod_tab_unidad_huevo
        if consumo_kg_tab_graf: acum_consumo_tab += consumo_kg_tab_graf
        
        acum_huevos_tab_val = int(round(acum_huevos_tab)) if acum_huevos_tab > 0 else None
        acum_consumo_tab_val = round(acum_consumo_tab, 2) if acum_consumo_tab > 0 else None

        if tiene_datos and prod_huevo_sem_val is not None:
            cant_unidades_perdida = round((porc_huevo_nc / 100.0) * prod_huevo_sem_val, 2)
            total_huevo_real = round(float(prod_huevo_sem_val) - cant_unidades_perdida, 2)
        else:
            cant_unidades_perdida = total_huevo_real = None

        gr_por_huevo = round((c_k_real * 1000.0) / prod_huevo_sem_val, 1) if (tiene_datos and prod_huevo_sem_val and prod_huevo_sem_val > 0) else None
        costo_huevo = round((c_k_real * 1000.0 / total_huevo_real) * (precio_dieta / 1000.0), 2) if (tiene_datos and total_huevo_real and total_huevo_real > 0 and precio_dieta) else None
        
        # Suma Saldo Aves entero redondeado
        suma_saldo_aves = int(round((saldo_val * 7) + (salidas_semana * 3.5))) if tiene_datos else None

        valores_update.append((
            c_k_real, m_sem, s_sem, o_sem,
            c_real_val, c_kaa_val, c_tab, acu_out, p_mort_sem, p_mort_acum,
            p_sel_sem, p_ms_acu, saldo_val, conversion_sem_val, ganancia_ave_val, prod_huevo_sem_val,
            prod_huevo_real_val, 
            
            num_semana, porc_prod_tb, porcentaje_tb, porcentaje_tx, porcentaje_rx,
            h_av_aloj_tab_val, c_tab, porcentaje_prod_real, haa_real, h_av_aloj_real, gr_ave_dia_graf,
            porcentaje_mort_acum_graf, conv_acum, gr_por_huevo, precio_dieta, costo_huevo,
            prod_tab_unidad_huevo, consumo_kg_tab_graf, acum_huevos_tab_val, acum_consumo_tab_val,
            porc_huevo_nc, total_huevo_real, cant_unidades_perdida, suma_saldo_aves, prod_huevo_tab_val,
            mort_tab_val, peso_ave_tab_val, peso_huevo_tab_val, masa_huevo_tab_sem_val, masa_huevo_tab_acum_val, 
            cons_agua_tab_val, conv_sem_real_val, conv_acum_real_val, masa_huevo_real_sem_val, masa_huevo_real_acum_val, 
            cons_agua_real_val, conv_kg_doc_acum_val, huevo_acum_val, kg_acum_val, kg_sem_val, f_id
        ))

    if valores_update:
        cur.executemany("""
            UPDATE bd_vargas 
            SET consumo_alim_kg = %s, mort_sem = %s, mort_select_sem = %s, mort_venta = %s,
                consumo_alim_real = %s, consumo_alim_k_a_a = %s, consumo_alim_tab = %s,
                salidas_acum = %s, percent_mort_sem = %s, percent_mort_acum = %s, percent_select_sem = %s,
                percent_mort_and_select_acum = %s, saldo_ave = %s, conv_sem_tab = %s, ganancia_ave_dia = %s,
                prod_huevo_sem = %s, prod_huevo_real = %s,
                sem_graf = %s, porcentaje_prod_tb = %s, porcentaje_tb = %s, porcentaje_tx = %s, porcentaje_rx = %s,
                haa_tab = %s, gr_tb_graf = %s, porcentaje_prod_real = %s, haa_real = %s, h_av_aloj_real = %s, gr_ave_dia_graf = %s,
                porcentaje_mort_acum_graf = %s, conv_acum_tab = %s, gr_por_huevo = %s, precio_dieta = %s, costo_huevo = %s,
                prod_tab_unidad_huevo = %s, consumo_kg_tab_graf = %s, huevos_acum_tab = %s, consumo_acum_tab = %s,
                porcentaje_huevo_nc = %s, total_huevo_real = %s, cant_unidades_perdida = %s, suma_saldo_aves = %s,
                prod_huevo_tab = %s, mort_tab = %s, peso_ave_tab = %s, peso_huevo_tab = %s, masa_huevo_tab_sem = %s,
                masa_huevo_tab_acum = %s, cons_agua_tab = %s, conv_sem_real = %s, conv_acum_real = %s,
                masa_huevo_real_sem = %s, masa_huevo_real_acum = %s, cons_agua_real = %s,
                conv_kg_doc_acum = %s, huevo_acum = %s, kg_acum = %s, kg_sem = %s
            WHERE id_sem_prod = %s
        """, valores_update)
        
def recalcular_todos_los_lotes_historicos():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT id_lote FROM bd_vargas")
        lotes_existentes = cur.fetchall()
        
        for lote in lotes_existentes:
            id_lote = lote[0]
            recalcular_lote_semanal_completo_directo(id_lote, cur)
            
        conn.commit()
        return True, f"¡Éxito! Se recalcularon {len(lotes_existentes)} lotes históricos."
    except Exception as e:
        conn.rollback()
        print(f"[ERROR RECÁLCULO MASIVO]: {e}")
        return False, f"Error al recalcular: {str(e)}"
    finally:
        cur.close()
        conn.close()