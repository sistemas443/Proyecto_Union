# models/semanal_levante/services.py
from datetime import datetime, timedelta
from models.base import get_db_connection, parse_empty, to_float_safe
from models.semanal_levante.schemas import COLUMNAS_PERMITIDAS
from models.semanal_levante import model
from models.cabecera.model import fetch_cabecera_by_lote

def generar_estructura_semanal_levante(lote_nombre, fecha_recepcion, id_lote):
    # Validaciones iniciales para evitar procesar datos nulos
    if not id_lote or not lote_nombre:
        return

    # Evita duplicar la estructura si el lote ya tiene semanas registradas
    if model.count_semanal(id_lote) > 0:
        return

    # Parsea la fecha de recepción para proyectar las fechas de cada semana
    fecha_base = None
    if fecha_recepcion and str(fecha_recepcion).strip() != '':
        try:
            fecha_base = datetime.strptime(str(fecha_recepcion), '%Y-%m-%d')
        except ValueError:
            pass

    # Genera los registros básicos para las 18 semanas de levante
    valores = []
    for i in range(18):
        semana_vida = i + 1
        fecha_str = None
        if fecha_base:
            # Calcula el último día de cada semana de vida
            fecha_str = (fecha_base + timedelta(days=(semana_vida * 7) - 1)).strftime('%Y-%m-%d')
        valores.append((lote_nombre, id_lote, fecha_str, semana_vida))

    try:
        model.insert_estructura_semanal(valores)
    except Exception as e:
        print(f"[ERROR INSERT ORIGINAL LEVANTE]: {e}")
        return

    # Tablas guía/estándar del manual genético para las 18 semanas
    guia_tab = [14, 21, 25, 30, 36, 44, 49, 56, 61, 64, 69, 72, 74, 77, 79, 82, 85, 0]
    guia_porc_tab = [0.4, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.6, 1.7, 1.8, 1.9, 2.0, 0.0]
    guia_peso_tab = [80, 145, 220, 320, 420, 520, 640, 760, 880, 995, 1105, 1205, 1295, 1365, 1445, 1510, 1590, 0]
    guia_unif_tab = [85, 85, 85, 80, 80, 80, 85, 85, 85, 85, 85, 85, 85, 85, 85, 85, 90, 0]
    guia_tarso_tab = [33, 40, 50, 58, 66, 72, 78, 83, 88, 92, 95, 98, 100, 101, 102, 103, 104, 105]
    guia_agua_tab = [28, 42, 50, 60, 73, 89, 98, 112, 122, 129, 137, 144, 148, 154, 158, 164, 170, 0]
    guia_ganan_tab = [45.0, 65.0, 75.0, 100.0, 100.0, 100.0, 120.0, 120.0, 120.0, 115.0, 110.0, 100.0, 90.0, 70.0, 80.0, 65.0, 80.0, 0.0]
    guia_conv_tab = [2.18, 2.26, 2.33, 2.10, 2.52, 3.08, 2.86, 3.27, 3.56, 3.90, 4.39, 5.04, 5.76, 7.70, 6.91, 8.83, 7.44, 0.0]
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Inyecta los valores de la guía genética en cada semana recién creada
        for i in range(18):
            semana_vida = i + 1
            cur.execute("""
                UPDATE semanal_levante 
                SET cons_tab = %s, porc_tab = %s, peso_tab = %s, unif_porc_uni = %s, 
                    t_tarso = %s, agua_tabla = %s, ganancia_ave = %s, conv_sem_tab = %s
                WHERE id_lote = %s AND sem = %s
            """, (guia_tab[i], guia_porc_tab[i], guia_peso_tab[i], guia_unif_tab[i], 
                  guia_tarso_tab[i], guia_agua_tab[i], guia_ganan_tab[i], guia_conv_tab[i], id_lote, semana_vida))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR INYECTANDO TAB LEVANTE]: {e}")
    finally:
        cur.close()
        conn.close()

def get_semanal_levante_all(lote_nombre: str = ''):
    # Retorna vacío si no hay nombre de lote válido
    if not lote_nombre or lote_nombre == 'VACIO':
        return []

    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera:
        return []

    id_lote = cabecera['id']

    # Fuerza un recálculo de todas las variables antes de devolver los datos para asegurar coherencia
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        recalcular_lote_semanal_levante_directo(id_lote, cur)
        conn.commit()
    except Exception as e:
        print(f"[ERROR EN GET SEMANAL LEVANTE]: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    rows = model.fetch_semanal_levante(id_lote)

    # Si a pesar de todo no hay registros, genera la estructura desde cero y vuelve a recalcular
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

def update_semanal_field(id_semanal: int, columna: str, valor: str, 
                         usuario_id=None, usuario_nombre=None) -> tuple[bool, dict, str]:
    # Filtro de seguridad para evitar inyecciones SQL
    if columna not in COLUMNAS_PERMITIDAS:
        return False, {}, f"Columna '{columna}' no permitida"

    from models.auditoria.services import registrar_cambio

    valor_db = parse_empty(valor)
    campos_actualizados = {}
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        id_lote = model.get_lote_id_by_semanal(id_semanal)
        if not id_lote:
            return False, {}, "No se encontró el ID del lote"

        # Definición de columnas que afectan los cálculos de acumulados y saldos
        columnas_matematicas = [
            'cons_tab', 'cons_kilos_real', 'mort_sem', 
            'mort_select_sem', 'mort_venta', 'peso_ave_real', 'peso_real',
            'peso_ave_tab', 'peso_tab', 'ganancia_ave', 'conv_sem_tab'
        ]

        if id_lote and (columna in columnas_matematicas):
            # Obtiene la cantidad inicial de aves para hacer los cálculos de saldo
            res_aves = model.get_aves_iniciales(id_lote)
            if res_aves is None: aves_iniciales = 10000.0
            elif isinstance(res_aves, (int, float)): aves_iniciales = float(res_aves)
            else:
                try: aves_iniciales = to_float_safe(res_aves[0] if isinstance(res_aves, tuple) else res_aves.get('no_pollitas_recibidas', 10000.0))
                except Exception: aves_iniciales = 10000.0

            if aves_iniciales <= 0: aves_iniciales = 1.0

            # Obtiene el peso inicial del lote
            cur.execute("SELECT peso, COALESCE(unidad_peso, 1.0) FROM cabecera_lotes WHERE id = %s", (id_lote,))
            cab_info = cur.fetchone()
            peso_recep = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 0.0
            u_peso = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 1.0

            # Mapea los nombres de las columnas que vienen del frontend a los de la base de datos
            col_db = columna
            if columna == 'mort_sem': col_db = 'mort'
            elif columna == 'mort_select_sem': col_db = 'sel'
            elif columna == 'mort_venta': col_db = 'otros'
            elif columna in ['peso_real', 'peso_ave_real']: col_db = 'peso_real'
            elif columna in ['peso_tab', 'peso_ave_tab']: col_db = 'peso_tab'

            # SELECT previo para obtener el valor anterior
            valor_anterior = None
            try:
                cur.execute("SAVEPOINT sp_select_previo")
                cur.execute('SELECT "{}" FROM semanal_levante WHERE id = %s'.format(columna), (id_semanal,))
                row = cur.fetchone()
                valor_anterior = row[0] if row else None
                cur.execute("RELEASE SAVEPOINT sp_select_previo")
            except Exception:
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_select_previo")
                except Exception:
                    pass
                valor_anterior = None

            # Actualiza el valor puntual ingresado por el usuario
            cur.execute(f"UPDATE semanal_levante SET {col_db} = %s WHERE id = %s", (valor_db, id_semanal))

            # Sincroniza el peso real de la semana 1 con la tabla de 'primera_semana'
            cur.execute("""
                UPDATE semanal_levante sl
                SET peso_real = ps.peso_real
                FROM primera_semana ps
                WHERE sl.id_lote = ps.id_lote
                  AND ps.semana = '0/7'
                  AND sl.sem = 1
                  AND ps.id_lote = %s
                  AND ps.peso_real > 0
            """, (id_lote,))

            # Extrae todas las semanas del lote para recalcular secuencialmente
            cur.execute("""
                SELECT id, cons_tab, cons_kilos_real, mort, sel, otros, peso_real, sem, peso_tab, ganancia_ave, conv_sem_tab
                FROM semanal_levante WHERE id_lote = %s ORDER BY sem ASC
            """, (id_lote,))
            filas = cur.fetchall()

            # Variables para llevar los acumulados semana tras semana
            acum_kilos = 0.0
            acum_mort = 0.0
            acum_sel = 0.0
            acum_otros = 0.0
            valores_update = []
            acum_gr_ave_tab_exacto = 0.0
            peso_semana_anterior = peso_recep if peso_recep > 0 else 0.0
            gr_ave_ac_anterior = 0.0          

            # Bucle iterativo de recálculo (recorre semana por semana)
            for idx, f in enumerate(filas):
                f_id = f[0]
                num_semana = int(f[7]) if f[7] is not None else (idx + 1)
                dia_inicio, dia_fin = ((num_semana - 1) * 7) + 1, num_semana * 7

                # Si es la celda que se está editando, usa el valor nuevo, si no, usa el de DB
                c_tab = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_tab') else to_float_safe(f[1])
                c_k_real = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_kilos_real') else to_float_safe(f[2])
                m_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_sem') else to_float_safe(f[3])
                s_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_select_sem') else to_float_safe(f[4])
                o_sem = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_venta') else to_float_safe(f[5])
                peso_real_val = to_float_safe(valor_db) if (f_id == id_semanal and columna in ['peso_real', 'peso_ave_real']) else to_float_safe(f[6])
                ganancia_ave_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'ganancia_ave') else to_float_safe(f[9])
                conv_sem_tab_val = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'conv_sem_tab') else to_float_safe(f[10])

                # Si los valores semanales son 0, intenta traerlos consolidados de los reportes diarios
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

                # Actualiza variables acumuladoras
                acum_kilos += c_k_real
                acum_mort += m_sem
                acum_sel += s_sem
                acum_otros += o_sem
                acum_gr_ave_tab_exacto += (c_tab * 7.0)

                # Cálculos de inventario de aves (mortalidad y saldos)
                tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or c_tab > 0 or peso_real_val > 0)
                acu_val = acum_mort + acum_sel + acum_otros
                acu_out = int(round(acu_val)) if tiene_datos else None
                saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else 0

                # Cálculos de porcentajes de mortalidad
                p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
                p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and acum_mort > 0 and tiene_datos) else None
                p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
                p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

                # Cálculos de consumos
                c_k_acum_val = int(round(acum_kilos)) if (c_k_real > 0 or c_tab > 0) else None
                c_real_exacto = (c_k_real / float(saldo_val) / 7.0) * 1000.0 if (tiene_datos and saldo_val > 0) else None
                c_real_val = round(c_real_exacto, 1) if c_real_exacto is not None else None
                
                gr_ave_tab_val = int(round(acum_gr_ave_tab_exacto))
                gr_ave_ac_exacto = (float(acum_kilos) / float(saldo_val)) * 1000.0 if (acum_kilos > 0 and saldo_val > 0) else 0.0
                gr_ave_ac_val = int(round(gr_ave_ac_exacto))

                # Definir peso y consumo anterior según la semana
                if num_semana == 1:
                    u_ant = peso_recep if peso_recep > 0 else 0.0
                    i_ant = 0.0
                else:
                    u_ant = peso_semana_anterior
                    i_ant = gr_ave_ac_anterior

                # Cálculos de ganancia de peso
                ganancia_ave_dia_val = round(peso_real_val - u_ant, 2) if (peso_real_val > 0 and u_ant > 0) else 0.0
                porc_cumpl_ganan_val = round(((ganancia_ave_dia_val / ganancia_ave_val) - 1.0) * 100.0, 2) if (ganancia_ave_dia_val > 0 and ganancia_ave_val > 0) else 0.0

                # Conversión alimenticia semanal (fórmula Excel):
                # Sem 1: SI(E12>0, SI(Y(U12>0, W6>0), (I12/(U12-W6)), 0), 0)
                # Sem N: SI(E_n>0, SI(Y(U_n>0, U_(n-1)>0), ((I_n - I_(n-1))/(U_n - U_(n-1))), 0), 0)
                conversion_sem_val = 0.0
                if c_k_real > 0 and peso_real_val > 0 and u_ant > 0:
                    diff_peso = peso_real_val - u_ant
                    diff_consumo = gr_ave_ac_val - i_ant
                    if diff_peso > 0:
                        conversion_sem_val = round(diff_consumo / diff_peso, 2)

                # Actualizar acumuladores para la siguiente semana
                peso_semana_anterior = peso_real_val
                gr_ave_ac_anterior = gr_ave_ac_val

                porc_cumpl_cons_val = 0.0
                if c_real_exacto is not None and c_real_exacto > 0 and c_tab > 0:
                    porc_cumpl_cons_val = round(((c_real_exacto / c_tab) - 1.0) * 100.0, 2)

                try:
                    val_ajustado = int(round(float(u_peso) * float(c_k_real)))
                except Exception:
                    val_ajustado = 0

                tiene_datos_reales = (c_k_real > 0 or peso_real_val > 0 or m_sem > 0)

                # Guarda en memoria la fila lista para ser actualizada masivamente luego
                valores_update.append((
                    c_k_real, m_sem, s_sem, o_sem,
                    c_real_val, c_k_acum_val, gr_ave_tab_val, gr_ave_ac_val,
                    acu_out, p_mort_sem, p_mort_acum, p_sel_sem, p_ms_acu, saldo_val, 
                    conversion_sem_val, ganancia_ave_dia_val, ganancia_ave_val, porc_cumpl_ganan_val,
                    conv_sem_tab_val, val_ajustado, porc_cumpl_cons_val, f_id
                ))

                # Si es la fila que el usuario editó, prepara el diccionario de respuesta para el frontend
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
                        'conv_sem_tab':                  f"{conv_sem_tab_val:.2f}" if conv_sem_tab_val else '',
                        'ganancia_ave_dia':              f"{ganancia_ave_dia_val:.1f}" if tiene_datos_reales else '',
                        'ganancia_ave':                  f"{ganancia_ave_val:.1f}" if ganancia_ave_val else '',
                        'porc_cumpl_ganan':              f"{porc_cumpl_ganan_val:.2f}" if tiene_datos_reales else '',
                        'porc_cumpl_cons':               f"{porc_cumpl_cons_val:.2f}" if tiene_datos_reales else '' 
                    })

            # Ejecuta la actualización masiva de todas las semanas afectadas por el recálculo secuencial
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
            # Si no es una columna matemática, simplemente la guarda de forma aislada
            model.guardar_dato_simple(id_semanal, columna, valor_db, cur)

        # Registrar en auditoría
        registrar_cambio(
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre or 'Desconocido',
            tabla='semanal_levante',
            id_registro=id_semanal,
            campo=columna,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_db,
            accion='UPDATE',
            cursor=cur
        )

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
    BLINDAJE DE SQL ELIMINADO: Usamos comprobación 100% en Python para evitar fallos de base de datos.
    """
    # Se vuelven a definir las tablas guía estándar para llenar posibles huecos (retroactivo)
    guia_tab_retro = [14, 21, 25, 30, 36, 44, 49, 56, 61, 64, 69, 72, 74, 77, 79, 82, 85, 0]
    guia_porc_tab_retro = [0.4, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.6, 1.7, 1.8, 1.9, 2.0, 0.0]
    guia_peso_tab_retro = [80, 145, 220, 320, 420, 520, 640, 760, 880, 995, 1105, 1205, 1295, 1365, 1445, 1510, 1590, 0]
    guia_unif_tab_retro = [85, 85, 85, 80, 80, 80, 85, 85, 85, 85, 85, 85, 85, 85, 85, 85, 90, 0]
    guia_tarso_tab_retro = [33, 40, 50, 58, 66, 72, 78, 83, 88, 92, 95, 98, 100, 101, 102, 103, 104, 105]
    guia_agua_tab_retro = [28, 42, 50, 60, 73, 89, 98, 112, 122, 129, 137, 144, 148, 154, 158, 164, 170, 0]
    guia_ganan_tab_retro = [45.0, 65.0, 75.0, 100.0, 100.0, 100.0, 120.0, 120.0, 120.0, 115.0, 110.0, 100.0, 90.0, 70.0, 80.0, 65.0, 80.0, 0.0]
    guia_conv_tab_retro = [2.18, 2.26, 2.33, 2.10, 2.52, 3.08, 2.86, 3.27, 3.56, 3.90, 4.39, 5.04, 5.76, 7.70, 6.91, 8.83, 7.44, 0.0]
    
    # Función auxiliar para detectar de forma segura campos "vacíos"
    def is_empty(val):
        if val is None: return True
        if str(val).strip() in ('', '0', '0.0', 'None'): return True
        return False

    # Parche retroactivo: Se asegura de que no falte información clave en la base de datos
    try:
        cur.execute("""
            SELECT id, sem, cons_tab, porc_tab, peso_tab, unif_porc_uni, 
                   t_tarso, agua_tabla, ganancia_ave, conv_sem_tab 
            FROM semanal_levante WHERE id_lote = %s
        """, (id_lote,))
        
        # Recorre la BD actual y si nota un campo vital vacío, le inyecta el estándar
        for fila in cur.fetchall():
            f_id = fila[0]
            if not fila[1]: continue
            sem_idx = int(fila[1]) - 1
            
            if 0 <= sem_idx < 18:
                upd_cols = []
                upd_vals = []
                
                if is_empty(fila[2]): upd_cols.append("cons_tab = %s"); upd_vals.append(guia_tab_retro[sem_idx])
                if is_empty(fila[3]): upd_cols.append("porc_tab = %s"); upd_vals.append(guia_porc_tab_retro[sem_idx])
                if is_empty(fila[4]): upd_cols.append("peso_tab = %s"); upd_vals.append(guia_peso_tab_retro[sem_idx])
                if is_empty(fila[5]): upd_cols.append("unif_porc_uni = %s"); upd_vals.append(guia_unif_tab_retro[sem_idx])
                if is_empty(fila[6]): upd_cols.append("t_tarso = %s"); upd_vals.append(guia_tarso_tab_retro[sem_idx])
                if is_empty(fila[7]): upd_cols.append("agua_tabla = %s"); upd_vals.append(guia_agua_tab_retro[sem_idx])
                if is_empty(fila[8]): upd_cols.append("ganancia_ave = %s"); upd_vals.append(guia_ganan_tab_retro[sem_idx])
                if is_empty(fila[9]): upd_cols.append("conv_sem_tab = %s"); upd_vals.append(guia_conv_tab_retro[sem_idx])

                if upd_cols:
                    upd_vals.append(f_id)
                    cur.execute(f"UPDATE semanal_levante SET {', '.join(upd_cols)} WHERE id = %s", tuple(upd_vals))
    except Exception as e:
        print(f"[ADVERTENCIA CRÍTICA] Error en inyección de parche por Python: {e}")

    # Extrae parámetros iniciales del lote
    cur.execute("SELECT no_pollitas_recibidas, peso, COALESCE(unidad_peso, 1.0) FROM cabecera_lotes WHERE id = %s", (id_lote,))
    cab_info = cur.fetchone()
    
    aves_iniciales = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 10000.0
    peso_recep = to_float_safe(cab_info[1]) if cab_info and cab_info[1] else 0.0
    u_peso = to_float_safe(cab_info[2]) if cab_info and cab_info[2] else 1.0
    if aves_iniciales <= 0: aves_iniciales = 1.0

    # Fuerza la sincronización del peso real de la primera semana
    cur.execute("""
        UPDATE semanal_levante sl
        SET peso_real = ps.peso_real
        FROM primera_semana ps
        WHERE sl.id_lote = ps.id_lote
          AND ps.semana = '0/7'
          AND sl.sem = 1
          AND ps.id_lote = %s
          AND ps.peso_real > 0
    """, (id_lote,))

    # Obtiene toda la información semanal a recalcular
    cur.execute("""
        SELECT id, cons_tab, cons_kilos_real, mort, sel, otros, peso_real, sem, peso_tab, ganancia_ave, conv_sem_tab
        FROM semanal_levante WHERE id_lote = %s ORDER BY sem ASC
    """, (id_lote,))
    filas = cur.fetchall()

    if not filas: return

    # Inicialización de acumuladores
    acum_kilos = 0.0
    acum_mort = 0.0
    acum_sel = 0.0
    acum_otros = 0.0
    valores_update = []
    
    acum_gr_ave_tab_exacto = 0.0
    peso_semana_anterior = peso_recep if peso_recep > 0 else 0.0
    gr_ave_ac_anterior = 0.0          

    # Iteración exhaustiva: Reconstruye todo el historial del lote iterando semana por semana
    for idx, f in enumerate(filas):
        f_id = f[0]
        c_tab = to_float_safe(f[1])
        c_k_real_manual = to_float_safe(f[2])
        m_sem_manual = to_float_safe(f[3])
        s_sem_manual = to_float_safe(f[4])
        o_sem_manual = to_float_safe(f[5])
        peso_real_val = to_float_safe(f[6])
        num_semana = int(f[7]) if f[7] is not None else (idx + 1)
        ganancia_ave_val = to_float_safe(f[9])
        conv_sem_tab_val = to_float_safe(f[10])

        dia_inicio, dia_fin = ((num_semana - 1) * 7) + 1, num_semana * 7

        # Consulta consumos y mortalidades agrupadas desde la tabla de registros diarios (data_diario)
        # Si encuentra datos diarios, sobrescribe los manuales. Si no, mantiene los manuales.
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

        # Continúa el flujo matemático sumando a los acumuladores para usarse en la siguiente semana
        acum_kilos += c_k_real
        acum_mort += m_sem
        acum_sel += s_sem
        acum_otros += o_sem
        
        acum_gr_ave_tab_exacto += (c_tab * 7.0)

        # Re-calcula la viabilidad del inventario de animales
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

        # Definir peso y consumo anterior según la semana
        if num_semana == 1:
            u_ant = peso_recep if peso_recep > 0 else 0.0
            i_ant = 0.0
        else:
            u_ant = peso_semana_anterior
            i_ant = gr_ave_ac_anterior

        # Re-calcula ganancias de peso
        ganancia_ave_dia_val = round(peso_real_val - u_ant, 2) if (peso_real_val > 0 and u_ant > 0) else 0.0
        porc_cumpl_ganan_val = round(((ganancia_ave_dia_val / ganancia_ave_val) - 1.0) * 100.0, 2) if (ganancia_ave_dia_val > 0 and ganancia_ave_val > 0) else 0.0

        # Conversión alimenticia semanal (fórmula Excel):
        # Sem 1: SI(E12>0, SI(Y(U12>0, W6>0), (I12/(U12-W6)), 0), 0)
        # Sem N: SI(E_n>0, SI(Y(U_n>0, U_(n-1)>0), ((I_n - I_(n-1))/(U_n - U_(n-1))), 0), 0)
        conversion_sem_val = 0.0
        if c_k_real > 0 and peso_real_val > 0 and u_ant > 0:
            diff_peso = peso_real_val - u_ant
            diff_consumo = gr_ave_ac_val - i_ant
            if diff_peso > 0:
                conversion_sem_val = round(diff_consumo / diff_peso, 2)

        # Actualizar acumuladores para la siguiente semana
        peso_semana_anterior = peso_real_val
        gr_ave_ac_anterior = gr_ave_ac_val

        porc_cumpl_cons_val = 0.0
        if c_real_exacto is not None and c_real_exacto > 0 and c_tab > 0:
            porc_cumpl_cons_val = round(((c_real_exacto / c_tab) - 1.0) * 100.0, 2)

        try:
            val_ajustado = int(round(float(u_peso) * float(c_k_real)))
        except Exception:
            val_ajustado = 0

        # Almacena los resultados de esta semana reconstruida
        valores_update.append((
            c_k_real, m_sem, s_sem, o_sem,
            c_real_val, c_k_acum_val, gr_ave_tab_val, gr_ave_ac_val,
            acu_out, p_mort_sem, p_mort_acum, p_sel_sem, p_ms_acu, saldo_val, 
            conversion_sem_val, ganancia_ave_dia_val, ganancia_ave_val, porc_cumpl_ganan_val,
            conv_sem_tab_val, val_ajustado, porc_cumpl_cons_val, f_id
        ))

    # Aplica masivamente los resultados reconstruidos de las 18 semanas a la base de datos
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
        
def procesar_excel_semanal_levante(archivo_excel, lote_nombre, usuario_id=None, usuario_nombre=None):
    """
    Procesa el Excel para el módulo Semanal Levante.
    Extrae únicamente las columnas crudas digitadas por el usuario (peso, uniformidades, tarso, agua)
    y dispara el recálculo general para sincronizar consumos y mortalidades desde los registros diarios.
    """
    import pandas as pd
    import unicodedata
    from models.base import get_db_connection, to_float_safe
    from models.cabecera.model import fetch_cabecera_by_lote
    from models.semanal_levante import model

    if not lote_nombre or lote_nombre == 'VACIO':
        return False, "Debes seleccionar un lote válido de destino."

    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera:
        return False, f"El lote '{lote_nombre}' no existe en el sistema."

    id_lote = cabecera.get('id')

    try:
        # 1. Garantizar que la estructura de las 18 semanas exista en la BD
        if model.count_semanal(id_lote) == 0:
            generar_estructura_semanal_levante(lote_nombre, cabecera.get('fecha_recepcion'), id_lote)

        # 2. Leer TODAS las hojas del Excel sin encabezados
        hojas = pd.read_excel(archivo_excel, sheet_name=None, header=None)
        df = None
        header_idx = -1

        def normalizar(texto):
            texto = str(texto).lower().strip()
            texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
            return ' '.join(texto.replace('\n', ' ').split())

        # 3. Escáner: se detiene si encuentra "semana" junto a "tarso" o "agua"
        for nombre_hoja, hoja_df in hojas.items():
            for i, row in hoja_df.iterrows():
                fila_texto = " ".join([normalizar(x) for x in row.values])

                if 'semana' in fila_texto and ('tarso' in fila_texto or 'agua' in fila_texto):
                    df = hoja_df
                    header_idx = i
                    break
            if df is not None:
                break

        if df is None:
            return False, "No se encontró la tabla de Levante. Faltan las columnas 'Tarso' o 'Agua' junto a 'Semana'."

        # 4. Fusionar la fila principal y la de abajo (celdas combinadas)
        nuevas_columnas = []
        for col_idx in range(df.shape[1]):
            val1 = normalizar(df.iloc[header_idx, col_idx])
            val2 = normalizar(df.iloc[header_idx + 1, col_idx]) if (header_idx + 1) < len(df) else ''

            val1 = val1 if val1 not in ['nan', 'none'] else ''
            val2 = val2 if val2 not in ['nan', 'none'] else ''

            nuevas_columnas.append(f"{val1} {val2}".strip())

        df.columns = nuevas_columnas
        df = df.iloc[header_idx + 2:].reset_index(drop=True)

        # 5. Ubicar la columna "Semana" con lógica robusta
        col_semana = None

        claves_semana = ['semana', 'sem.', 'sem ', ' sem']
        exclusiones = ['ganancia', 'fecha', 'fin sem', 'conv', 'kilos', 'k.acum',
                       'mort', 'acum', 'acm', '%', 'tab', 'gr ave', 'peso',
                       'uniformidad', 'tarso', 'agua', 'saldo', 'aves', 'observaciones',
                       'marca', 'real', 'c.v', 'otros', 'sel', 'inventario']

        for col in df.columns:
            c = str(col).lower().strip()
            if not c:
                continue
            if any(excl in c for excl in exclusiones):
                continue
            if any(clave in c for clave in claves_semana):
                valores_prueba = df[col].dropna().astype(str).str.replace('.0', '', regex=False).str.strip()
                valores_prueba = valores_prueba[valores_prueba.str.isdigit()]
                if len(valores_prueba) > 0:
                    nums = valores_prueba.astype(int)
                    if ((nums >= 1) & (nums <= 18)).sum() > 0:
                        col_semana = col
                        break

        # Fallback: buscar cualquier columna con valores entre 1 y 18
        if not col_semana:
            for col in df.columns:
                valores_prueba = df[col].dropna().astype(str).str.replace('.0', '', regex=False).str.strip()
                valores_prueba = valores_prueba[valores_prueba.str.isdigit()]
                if len(valores_prueba) > 0:
                    nums = valores_prueba.astype(int)
                    if ((nums >= 1) & (nums <= 18)).sum() >= 3:
                        col_semana = col
                        break

        if not col_semana:
            return False, "Error interno: No se ubicó la columna 'Semana' con valores del 1 al 18."

        # 6. MAPEO ESTRICTO DE LA LISTA BLANCA
        mapeo_columnas = {
            'peso corporal': 'peso_real',
            '10%-':          'unif_10_menos',
            '%unif':         'unif_porc_unif',
            '10%+':          'unif_10_mas',
            'c.v':           'unif_cv',
            'tarso':         't_tarso_r',
            'agua':          'agua_real',
            'observaciones': 'observaciones',
            'marca/tipo':    'marca_tipo_de'
        }

        conn = get_db_connection()
        cur = conn.cursor()
        filas_actualizadas = 0

        def extraer_valor(v):
            if pd.isna(v): return None
            v_str = str(v).strip().lower()
            if v_str in ['', 'nan', '-', 'none']: return None
            return v

        # 7. Iterar sobre las 18 semanas y armar el UPDATE
        for _, row in df.iterrows():
            # --- LIMPIEZA ROBUSTA DEL VALOR DE SEMANA ---
            val_semana_raw = row[col_semana]
            if pd.isna(val_semana_raw):
                continue

            val_semana_str = str(val_semana_raw).strip()
            val_semana_str = val_semana_str.replace(',', '.').replace(' ', '')
            if '.' in val_semana_str:
                val_semana_str = val_semana_str.split('.')[0]
            val_semana_str = val_semana_str.lower().replace('semana', '').replace('sem', '').replace('s', '').strip()

            if not val_semana_str.isdigit():
                continue
            num_semana = int(val_semana_str)
            if not (1 <= num_semana <= 18):
                continue

            campos_a_actualizar = []
            valores = []
            columnas_ya_procesadas = set()

            for palabra_clave, col_db in mapeo_columnas.items():
                if col_db in columnas_ya_procesadas:
                    continue

                col_encontrada = next((c for c in df.columns if palabra_clave in c), None)
                if col_encontrada:
                    v = extraer_valor(row[col_encontrada])
                    if v is not None:
                        if col_db in ['observaciones', 'marca_tipo_de']:
                            campos_a_actualizar.append(f'"{col_db}" = %s')
                            valores.append(str(v))
                            columnas_ya_procesadas.add(col_db)
                        else:
                            try:
                                campos_a_actualizar.append(f'"{col_db}" = %s')
                                valores.append(to_float_safe(v) or 0.0)
                                columnas_ya_procesadas.add(col_db)
                            except: pass

            if campos_a_actualizar:
                valores.extend([id_lote, num_semana])
                query = f"UPDATE semanal_levante SET {', '.join(campos_a_actualizar)} WHERE id_lote = %s AND sem = %s"
                cur.execute(query, valores)
                filas_actualizadas += 1

        # 8. Recalcular cascada general del lote
        recalcular_lote_semanal_levante_directo(id_lote, cur)

        # Registrar en auditoría (1 solo registro por carga)
        if filas_actualizadas > 0:
            from models.auditoria.services import registrar_cambio
            registrar_cambio(
                usuario_id=usuario_id,
                usuario_nombre=usuario_nombre or 'Desconocido',
                tabla='semanal_levante',
                id_registro=None,
                campo=f'Lote {lote_nombre} - Carga Excel',
                valor_anterior=None,
                valor_nuevo='Datos de levante cargados correctamente',
                accion='IMPORT',
                cursor=cur
            )

        conn.commit()
        cur.close()
        conn.close()

        if filas_actualizadas > 0:
            return True, f"¡Éxito! Se cargaron datos puros de {filas_actualizadas} semanas de levante."
        else:
            return False, "La tabla fue detectada, pero las filas de las semanas (1-18) estaban vacías."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error al procesar el archivo Excel: {str(e)}"