# models/semanal/services.py

from datetime import datetime, timedelta, date
from models.base import get_db_connection, parse_empty, to_float_safe
from models.semanal.schemas import COLUMNAS_PERMITIDAS
from models.semanal import model
from models.cabecera.model import fetch_cabecera_by_lote

def generar_estructura_semanal_unificada(lote_nombre, fecha_recepcion, id_lote):
    if not id_lote or not lote_nombre:
        return
    if model.count_semanal(id_lote) > 0:
        return
    fecha_base = None
    if fecha_recepcion and str(fecha_recepcion).strip() != '':
        try:
            fecha_base = datetime.strptime(str(fecha_recepcion), '%Y-%m-%d')
        except ValueError:
            pass
    valores = []
    for i in range(18, 111):
        semana_vida = i
        fecha_str = None
        if fecha_base:
            fecha_str = (fecha_base + timedelta(days=((semana_vida - 17) * 7) - 1)).strftime('%Y-%m-%d')
        valores.append((lote_nombre, id_lote, fecha_str, semana_vida))
    model.insert_estructura_semanal(valores)

def get_semanal_all(lote_nombre: str = ''):
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
    return rows

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
            'prod_huevo_sem'
        ]

        if id_lote and (columna in columnas_matematicas):
            res_aves = model.get_aves_iniciales(id_lote)
            if res_aves is None: aves_iniciales = 10000.0
            elif isinstance(res_aves, (int, float)): aves_iniciales = float(res_aves)
            else:
                try: aves_iniciales = to_float_safe(res_aves[0] if isinstance(res_aves, tuple) else res_aves.get('no_pollitas_recibidas', 10000.0))
                except Exception: aves_iniciales = 10000.0

            if aves_iniciales <= 0: aves_iniciales = 1.0

            cur.execute("SELECT peso FROM cabecera_lotes WHERE id = %s", (id_lote,))
            cab_info = cur.fetchone()
            peso_recep = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 0.0

            col_db = columna
            if columna in ['cons_tab', 'gr_tb']: col_db = 'consumo_alim_tab'
            elif columna in ['cons_kilos_real']: col_db = 'consumo_alim_kg'
            elif columna in ['peso_real']: col_db = 'peso_ave_real'

            cur.execute(f"UPDATE bd_vargas SET {col_db} = %s WHERE id_sem_prod = %s", (valor_db, id_semanal))

            cur.execute("""
                SELECT id_sem_prod, consumo_alim_tab, consumo_alim_kg, mort_sem, mort_select_sem, mort_venta, 
                       peso_ave_real, sem_prod, porcentaje_prod_tb, precio_dieta, porcentaje_huevo_nc,
                       h_av_aloj_tab, h_av_aloj_real, peso_huevo_real, conv_kg_doc_acum
                FROM bd_vargas 
                WHERE id_lote = %s ORDER BY sem_prod ASC
            """, (id_lote,))
            filas = cur.fetchall()

            acum_kilos, acum_gr_ave_tab, acum_mort, acum_sel, acum_otros = 0.0, 0.0, 0.0, 0.0, 0.0
            acum_huevos_tab = 0.0
            acum_consumo_tab = 0.0
            valores_update = []

            for idx, f in enumerate(filas):
                f_id = f[0]
                num_semana = int(f[7]) if f[7] is not None else (idx + 1)
                
                dia_inicio = ((num_semana - 1) * 7) + 1
                dia_fin = num_semana * 7

                # --- SEPARACIÓN DE LÓGICAS (TRADUCCIÓN EXACTA DE EXCEL) ---
                # Para Huevos (acumulado histórico, Excel tenía >=)
                sql_rango_huevos = "dias <= %s"
                params_huevos = (id_lote, dia_fin)

                # Para Mortalidad, Consumo, etc (estrictamente semanal, Excel tenía =)
                sql_rango_estricto = "dias BETWEEN %s AND %s"
                params_estricto = (id_lote, dia_inicio, dia_fin)

                c_tab = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['cons_tab', 'gr_tb', 'consumo_alim_tab']) else to_float_safe(f[1])
                c_k_real = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['cons_kilos_real', 'consumo_alim_kg']) else to_float_safe(f[2])
                m_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_sem') else to_float_safe(f[3])
                s_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_select_sem') else to_float_safe(f[4])
                o_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_venta') else to_float_safe(f[5])
                peso_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['peso_real', 'peso_ave_real']) else to_float_safe(f[6])
                
                porc_prod_tb = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'porcentaje_prod_tb') else to_float_safe(f[8])
                precio_dieta = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'precio_dieta') else to_float_safe(f[9])
                porc_huevo_nc = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'porcentaje_huevo_nc') else to_float_safe(f[10])
                
                h_av_aloj_tab = to_float_safe(f[11])
                h_av_aloj_real = to_float_safe(f[12])
                peso_huevo_real_val = to_float_safe(f[13])
                conv_kg_doc_acum_val = to_float_safe(f[14])

                # Consultas a la tabla DIARIO separadas
                # TRUCO EXCEL: Le quitamos el condicional para que SIEMPRE sume el diario de forma estricta
                cur.execute(f"SELECT COALESCE(SUM(consumo_kg), 0), COALESCE(SUM(mortalidad), 0), COALESCE(SUM(sel), 0), COALESCE(SUM(otros), 0) FROM data_diario WHERE id_lote = %s AND {sql_rango_estricto}", params_estricto)
                res_estricto = cur.fetchone()
                
                if res_estricto:
                    if res_estricto[0] > 0: c_k_real = to_float_safe(res_estricto[0])
                    if res_estricto[1] > 0: m_sem = to_float_safe(res_estricto[1]) # Toma la Mortalidad SÍ o SÍ
                    if res_estricto[2] > 0: s_sem = to_float_safe(res_estricto[2])
                    if res_estricto[3] > 0: o_sem = to_float_safe(res_estricto[3])

                cur.execute(f"SELECT COALESCE(SUM(produccion), 0) FROM data_diario WHERE id_lote = %s AND {sql_rango_huevos}", params_huevos)
                res_huevos = cur.fetchone()
                huevos_semana = int(res_huevos[0]) if res_huevos else 0

                tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or peso_real_val > 0 or huevos_semana > 0)

                if tiene_datos:
                    prod_huevo_sem_val = int(huevos_semana)
                else:
                    prod_huevo_sem_val = None

                acum_kilos += c_k_real
                acum_gr_ave_tab += (c_tab * 7)
                acum_mort += m_sem
                acum_sel += s_sem
                acum_otros += o_sem

                acu_val = acum_mort + acum_sel + acum_otros
                acu_out = int(round(acu_val)) if tiene_datos else None
                saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

                p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
                p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and acum_mort > 0 and tiene_datos) else None
                p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
                p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

                c_k_acum_val = round(acum_kilos, 2) if (c_k_real > 0 or c_tab > 0) else None

                if tiene_datos:
                    c_real_val = round((c_k_real / float(saldo_val) / 7.0) * 1000.0, 2) if (c_k_real > 0 and saldo_val > 0) else 0.0
                else: c_real_val = None

                gr_ave_tab_val = round(acum_gr_ave_tab, 2) if c_tab > 0 else None
                gr_ave_ac_val = int(round((acum_kilos / float(saldo_val)) * 1000.0)) if (acum_kilos > 0 and saldo_val > 0) else 0

                if c_k_real > 0 and peso_real_val > 0 and peso_recep > 0 and (peso_real_val - peso_recep) != 0:
                    conversion_sem_val = round(gr_ave_ac_val / (peso_real_val - peso_recep), 2)
                else: conversion_sem_val = 0.0

                ganancia_ave_val = round(peso_real_val - peso_recep, 2) if (peso_real_val > 0 and peso_recep > 0) else 0.0

                salidas_semana = m_sem + s_sem + o_sem
                
                if saldo_val == 0:
                    prod_huevo_real_val = 0.0
                    porcentaje_prod_real = 0.0
                else:
                    if tiene_datos and prod_huevo_sem_val is not None:
                        prod_huevo_real_val = round((prod_huevo_sem_val / 7.0 / saldo_val) * 100, 2)
                        porcentaje_prod_real = prod_huevo_real_val
                    else:
                        prod_huevo_real_val = None
                        porcentaje_prod_real = None

                margen_tolerancia = 0.04 
                if porc_prod_tb:
                    porcentaje_tb = round(porc_prod_tb * (1 - margen_tolerancia), 2)
                    porcentaje_tx = round(porc_prod_tb * (1 + margen_tolerancia), 2)
                    porcentaje_rx = round(porcentaje_tx - porcentaje_tb, 2)
                    prod_tab_unidad_huevo = round((porc_prod_tb / 100.0) * saldo_val * 7, 2)
                else:
                    porcentaje_tb = porcentaje_tx = porcentaje_rx = prod_tab_unidad_huevo = None

                if c_tab and saldo_val > 0:
                    consumo_kg_tab_graf = round((c_tab / 1000.0) * saldo_val * 7, 2)
                else:
                    consumo_kg_tab_graf = None

                if prod_tab_unidad_huevo: acum_huevos_tab += prod_tab_unidad_huevo
                if consumo_kg_tab_graf: acum_consumo_tab += consumo_kg_tab_graf
                
                acum_huevos_tab_val = round(acum_huevos_tab, 2) if acum_huevos_tab > 0 else None
                acum_consumo_tab_val = round(acum_consumo_tab, 2) if acum_consumo_tab > 0 else None

                if tiene_datos and prod_huevo_sem_val is not None:
                    cant_unidades_perdida = round((porc_huevo_nc / 100.0) * prod_huevo_sem_val, 2)
                    total_huevo_real = round(float(prod_huevo_sem_val) - cant_unidades_perdida, 2)
                else:
                    cant_unidades_perdida = None
                    total_huevo_real = None

                if tiene_datos and prod_huevo_sem_val and prod_huevo_sem_val > 0:
                    gr_por_huevo = round((c_k_real * 1000.0) / prod_huevo_sem_val, 2)
                else:
                    gr_por_huevo = None

                if tiene_datos and total_huevo_real and total_huevo_real > 0 and precio_dieta:
                    costo_huevo = round((c_k_real * 1000.0 / total_huevo_real) * (precio_dieta / 1000.0), 2)
                else:
                    costo_huevo = None

                if tiene_datos:
                    suma_saldo_aves = round((saldo_val * 7) + (salidas_semana * 3.5), 2)
                else:
                    suma_saldo_aves = None

                valores_update.append((
                    c_real_val, c_k_acum_val, c_tab, gr_ave_ac_val, acu_out, p_mort_sem, p_mort_acum, 
                    p_sel_sem, p_ms_acu, saldo_val, conversion_sem_val, ganancia_ave_val, prod_huevo_sem_val,
                    prod_huevo_real_val, 
                    
                    num_semana, porc_prod_tb, porcentaje_tb, porcentaje_tx, porcentaje_rx,
                    h_av_aloj_tab, c_tab, porcentaje_prod_real, h_av_aloj_real, ganancia_ave_val,
                    p_mort_acum, conv_kg_doc_acum_val, gr_por_huevo, precio_dieta, costo_huevo,
                    prod_tab_unidad_huevo, consumo_kg_tab_graf, acum_huevos_tab_val, acum_consumo_tab_val,
                    porc_huevo_nc, total_huevo_real, cant_unidades_perdida, suma_saldo_aves, f_id
                ))

            if valores_update:
                cur.executemany("""
                    UPDATE bd_vargas 
                    SET consumo_alim_real = %s, consumo_alim_k_a_a = %s, consumo_alim_tab = %s, cons_gr_ave_ao = %s,
                        salidas_acum = %s, percent_mort_sem = %s, percent_mort_acum = %s, percent_select_sem = %s,
                        percent_mort_and_select_acum = %s, saldo_ave = %s, conv_sem = %s, ganancia_ave_dia = %s,
                        prod_huevo_sem = %s, prod_huevo_real = %s,
                        sem_graf = %s, porcentaje_prod_tb = %s, porcentaje_tb = %s, porcentaje_tx = %s, porcentaje_rx = %s,
                        haa_tab = %s, gr_tb_graf = %s, porcentaje_prod_real = %s, haa_real = %s, gr_ave_dia_graf = %s,
                        porcentaje_mort_acum_graf = %s, conv_acum = %s, gr_por_huevo = %s, precio_dieta = %s, costo_huevo = %s,
                        prod_tab_unidad_huevo = %s, consumo_kg_tab_graf = %s, huevos_acum_tab = %s, consumo_acum_tab = %s,
                        porcentaje_huevo_nc = %s, total_huevo_real = %s, cant_unidades_perdida = %s, suma_saldo_aves = %s
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


def recalcular_lote_semanal_completo_directo(id_lote, cur):
    cur.execute("SELECT no_pollitas_recibidas, peso FROM cabecera_lotes WHERE id = %s", (id_lote,))
    cab_info = cur.fetchone()
    aves_iniciales = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 10000.0
    if aves_iniciales <= 0: aves_iniciales = 1.0
    peso_recep = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 0.0

    cur.execute("""
        SELECT id_sem_prod, consumo_alim_tab, consumo_alim_kg, mort_sem, mort_select_sem, mort_venta, 
               peso_ave_real, sem_prod, porcentaje_prod_tb, precio_dieta, porcentaje_huevo_nc,
               h_av_aloj_tab, h_av_aloj_real, peso_huevo_real, conv_kg_doc_acum
        FROM bd_vargas WHERE id_lote = %s ORDER BY sem_prod ASC
    """, (id_lote,))
    filas = cur.fetchall()

    acum_kilos, acum_gr_ave_tab, acum_mort, acum_sel, acum_otros = 0.0, 0.0, 0.0, 0.0, 0.0
    acum_huevos_tab = 0.0
    acum_consumo_tab = 0.0
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
        
        h_av_aloj_tab = to_float_safe(f[11])
        h_av_aloj_real = to_float_safe(f[12])
        peso_huevo_real_val = to_float_safe(f[13])
        conv_kg_doc_acum_val = to_float_safe(f[14])

        # 1. Consulta estrictamente semanal para Consumo y Mortalidad
        cur.execute("""
            SELECT COALESCE(SUM(consumo_kg), 0), COALESCE(SUM(mortalidad), 0), COALESCE(SUM(sel), 0), COALESCE(SUM(otros), 0)
            FROM data_diario WHERE id_lote = %s AND dias BETWEEN %s AND %s
        """, (id_lote, dia_inicio, dia_fin))
        res_sem = cur.fetchone()
        
        c_k_real = to_float_safe(res_sem[0]) if res_sem else 0.0
        m_sem = to_float_safe(res_sem[1]) if res_sem else 0.0
        s_sem = to_float_safe(res_sem[2]) if res_sem else 0.0
        o_sem = to_float_safe(res_sem[3]) if res_sem else 0.0

        # 2. Consulta histórica (acumulada) solo para los Huevos
        cur.execute("""
            SELECT COALESCE(SUM(produccion), 0) 
            FROM data_diario WHERE id_lote = %s AND dias <= %s
        """, (id_lote, dia_fin))
        res_huevos = cur.fetchone()
        huevos_semana = to_float_safe(res_huevos[0]) if res_huevos else 0.0

        tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or peso_real_val > 0 or huevos_semana > 0)

        if tiene_datos:
            prod_huevo_sem_val = int(round(huevos_semana))
        else:
            prod_huevo_sem_val = None

        acum_kilos += c_k_real
        acum_gr_ave_tab += (c_tab * 7)
        acum_mort += m_sem
        acum_sel += s_sem
        acum_otros += o_sem

        acu_val = acum_mort + acum_sel + acum_otros
        acu_out = int(round(acu_val)) if tiene_datos else None
        saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

        p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
        p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and acum_mort > 0 and tiene_datos) else None
        p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
        p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

        c_k_acum_val = round(acum_kilos, 2) if (c_k_real > 0 or c_tab > 0) else None

        if tiene_datos:
            c_real_val = round((c_k_real / float(saldo_val) / 7.0) * 1000.0, 2) if (c_k_real > 0 and saldo_val > 0) else 0.0
        else: 
            c_real_val = None

        gr_ave_ac_val = int(round((acum_kilos / float(saldo_val)) * 1000.0)) if (acum_kilos > 0 and saldo_val > 0) else 0

        if c_k_real > 0 and peso_real_val > 0 and peso_recep > 0 and (peso_real_val - peso_recep) != 0:
            conversion_sem_val = round(gr_ave_ac_val / (peso_real_val - peso_recep), 2)
        else: 
            conversion_sem_val = 0.0

        ganancia_ave_val = round(peso_real_val - peso_recep, 2) if (peso_real_val > 0 and peso_recep > 0) else 0.0

        salidas_semana = m_sem + s_sem + o_sem
        
        if saldo_val == 0:
            prod_huevo_real_val = 0.0
            porcentaje_prod_real = 0.0
        else:
            if tiene_datos and prod_huevo_sem_val is not None:
                prod_huevo_real_val = round((prod_huevo_sem_val / 7.0 / saldo_val) * 100, 2)
                porcentaje_prod_real = prod_huevo_real_val
            else:
                prod_huevo_real_val = None
                porcentaje_prod_real = None

        margen_tolerancia = 0.04
        if porc_prod_tb:
            porcentaje_tb = round(porc_prod_tb * (1 - margen_tolerancia), 2)
            porcentaje_tx = round(porc_prod_tb * (1 + margen_tolerancia), 2)
            porcentaje_rx = round(porcentaje_tx - porcentaje_tb, 2)
            prod_tab_unidad_huevo = round((porc_prod_tb / 100.0) * saldo_val * 7, 2)
        else:
            porcentaje_tb = porcentaje_tx = porcentaje_rx = prod_tab_unidad_huevo = None

        if c_tab and saldo_val > 0:
            consumo_kg_tab_graf = round((c_tab / 1000.0) * saldo_val * 7, 2)
        else:
            consumo_kg_tab_graf = None

        if prod_tab_unidad_huevo: acum_huevos_tab += prod_tab_unidad_huevo
        if consumo_kg_tab_graf: acum_consumo_tab += consumo_kg_tab_graf
        
        acum_huevos_tab_val = round(acum_huevos_tab, 2) if acum_huevos_tab > 0 else None
        acum_consumo_tab_val = round(acum_consumo_tab, 2) if acum_consumo_tab > 0 else None

        if tiene_datos and prod_huevo_sem_val is not None:
            cant_unidades_perdida = round((porc_huevo_nc / 100.0) * prod_huevo_sem_val, 2)
            total_huevo_real = round(float(prod_huevo_sem_val) - cant_unidades_perdida, 2)
        else:
            cant_unidades_perdida = None
            total_huevo_real = None

        if tiene_datos and prod_huevo_sem_val and prod_huevo_sem_val > 0:
            gr_por_huevo = round((c_k_real * 1000.0) / prod_huevo_sem_val, 2)
        else:
            gr_por_huevo = None

        if tiene_datos and total_huevo_real and total_huevo_real > 0 and precio_dieta:
            costo_huevo = round((c_k_real * 1000.0 / total_huevo_real) * (precio_dieta / 1000.0), 2)
        else:
            costo_huevo = None

        if tiene_datos:
            suma_saldo_aves = round((saldo_val * 7) + (salidas_semana * 3.5), 2)
        else:
            suma_saldo_aves = None

        valores_update.append((
            c_k_real, m_sem, s_sem, o_sem,
            c_real_val, c_k_acum_val, c_tab, gr_ave_ac_val, acu_out, p_mort_sem, p_mort_acum, 
            p_sel_sem, p_ms_acu, saldo_val, conversion_sem_val, ganancia_ave_val, prod_huevo_sem_val,
            prod_huevo_real_val, 
            
            num_semana, porc_prod_tb, porcentaje_tb, porcentaje_tx, porcentaje_rx,
            h_av_aloj_tab, c_tab, porcentaje_prod_real, h_av_aloj_real, ganancia_ave_val,
            p_mort_acum, conv_kg_doc_acum_val, gr_por_huevo, precio_dieta, costo_huevo,
            prod_tab_unidad_huevo, consumo_kg_tab_graf, acum_huevos_tab_val, acum_consumo_tab_val,
            porc_huevo_nc, total_huevo_real, cant_unidades_perdida, suma_saldo_aves, f_id
        ))

    if valores_update:
        cur.executemany("""
            UPDATE bd_vargas 
            SET consumo_alim_kg = %s, mort_sem = %s, mort_select_sem = %s, mort_venta = %s,
                consumo_alim_real = %s, consumo_alim_k_a_a = %s, consumo_alim_tab = %s, cons_gr_ave_ao = %s,
                salidas_acum = %s, percent_mort_sem = %s, percent_mort_acum = %s, percent_select_sem = %s,
                percent_mort_and_select_acum = %s, saldo_ave = %s, conv_sem = %s, ganancia_ave_dia = %s,
                prod_huevo_sem = %s, prod_huevo_real = %s,
                sem_graf = %s, porcentaje_prod_tb = %s, porcentaje_tb = %s, porcentaje_tx = %s, porcentaje_rx = %s,
                haa_tab = %s, gr_tb_graf = %s, porcentaje_prod_real = %s, haa_real = %s, gr_ave_dia_graf = %s,
                porcentaje_mort_acum_graf = %s, conv_acum = %s, gr_por_huevo = %s, precio_dieta = %s, costo_huevo = %s,
                prod_tab_unidad_huevo = %s, consumo_kg_tab_graf = %s, huevos_acum_tab = %s, consumo_acum_tab = %s,
                porcentaje_huevo_nc = %s, total_huevo_real = %s, cant_unidades_perdida = %s, suma_saldo_aves = %s
            WHERE id_sem_prod = %s
        """, valores_update)