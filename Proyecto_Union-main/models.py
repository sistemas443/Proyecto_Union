# import psycopg2
# import psycopg2.extras
# from config import Config
# from datetime import datetime, timedelta

# def get_db_connection():
#     conn = psycopg2.connect(
#         host=Config.DB_HOST,
#         database=Config.DB_NAME,
#         user=Config.DB_USER,
#         password=Config.DB_PASSWORD,
#         port=Config.DB_PORT,
#         client_encoding='utf8'
#     )
#     return conn

# def parse_empty(value):
#     return value if value and str(value).strip() != '' else None

# def to_float_safe(val):
#     if val is None or str(val).strip() == '': 
#         return 0.0
#     try:
#         return float(str(val).replace(',', ''))
#     except:
#         return 0.0

# # ===========================================================================
# # 1. CABECERA UNIFICADA
# # ===========================================================================

# def get_cabecera_info(lote: str):
#     if not lote or lote == 'VACIO': return {}
#     conn = get_db_connection()
#     cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute("INSERT INTO cabecera_lotes (lote) VALUES (%s) ON CONFLICT (lote) DO NOTHING", (lote,))
#     conn.commit()
#     cur.execute("SELECT * FROM cabecera_lotes WHERE lote = %s", (lote,))
#     row = cur.fetchone()
#     cur.close()
#     conn.close()
#     return dict(row) if row else {}

# def update_cabecera_unificada(lote: str, columna: str, valor: str) -> tuple[bool, str]:
#     COLUMNAS_PERMITIDAS = {
#         'fecha_recepcion', 'granja_prod', 'granja_lev', 'no_pollitas_recibidas',
#         'responsable_tecnico', 'ciudad', 'tipo_galpon', 'clima', 'uniformidad',
#         'peso', 'unidad_peso', 'coeficiente_variacion', 'fecha_encasetamiento',
#         'no_aves_encasetadas', 'unidad_medida', 'cliente', 'variedad',
#         'marca_galpon', 'nutricionista', 'validacion'
#     }
#     if columna not in COLUMNAS_PERMITIDAS: return False, f"Columna '{columna}' no permitida"
#     valor_db = valor if valor.strip() != '' else None
#     conn = get_db_connection()
#     cur  = conn.cursor()
#     try:
#         cur.execute(f'UPDATE cabecera_lotes SET "{columna}" = %s WHERE lote = %s', (valor_db, lote))
#         conn.commit()
#         return True, "Ok"
#     except Exception as e:
#         conn.rollback()
#         return False, str(e)
#     finally:
#         cur.close()
#         conn.close()

# # ===========================================================================
# # 2 y 3. REGISTRO DIARIO UNIFICADO
# # ===========================================================================

# def generar_estructura_diario(cur, lote_nombre, id_lote, fecha_recepcion):
#     if not id_lote or not lote_nombre: return
#     cur.execute("SELECT COUNT(*) AS total FROM data_diario WHERE id_lote = %s", (id_lote,))
#     row = cur.fetchone()
#     count_val = row['total'] if hasattr(row, 'keys') else row[0]
#     if count_val > 0: return

#     fecha_base = None
#     if fecha_recepcion and str(fecha_recepcion).strip() != '':
#         try: fecha_base = datetime.strptime(str(fecha_recepcion), '%Y-%m-%d')
#         except ValueError: pass

#     valores = [] 
#     for i in range(770):
#         fecha_str = None
#         if fecha_base:
#             fecha_str = (fecha_base + timedelta(days=i)).strftime('%Y-%m-%d')
            
#         dia_vida = i + 1
#         semanas_completas = i // 7
#         dias_extra = (i % 7) + 1
        
#         if dia_vida <= 8:
#             etiquetas_semana = ["0", "0/1", "0/2", "0/3", "0/4", "0/5", "0/6", "0/7"]
#             semana_str = etiquetas_semana[i] if i < 8 else "1"
#         else:
#             semana_str = str(semanas_completas + 1) if dias_extra == 7 else f"{semanas_completas} + {dias_extra}/"
        
#         valores.append((lote_nombre, id_lote, fecha_str, dia_vida, semana_str))
    
#     psycopg2.extras.execute_values(
#         cur, "INSERT INTO data_diario (lote, id_lote, fecha_dia, dias, sem) VALUES %s", valores
#     )

# def get_primera_semana_by_lote(lote_nombre):
#     conn = get_db_connection()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute("SELECT id, fecha_recepcion FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
#     cabecera = cur.fetchone()
#     if not cabecera: return []
#     id_lote = cabecera['id']
#     query = """
#         SELECT id_diario as id, lote, fecha_dia as fecha, sem as semana, 
#                mortalidad, sel, porc_mort_sem, porc_mort_acum, saldo_aves, 
#                peso_tabla, peso_real, unif_10_menos, porc_uniformidad, 
#                unif_10_mas, coef_variacion, observaciones 
#         FROM data_diario WHERE id_lote = %s ORDER BY dias ASC LIMIT 8
#     """
#     cur.execute(query, (id_lote,))
#     rows = cur.fetchall()
#     if len(rows) == 0:
#         generar_estructura_diario(cur, lote_nombre, id_lote, cabecera['fecha_recepcion'])
#         conn.commit()
#         cur.execute(query, (id_lote,))
#         rows = cur.fetchall()
#     cur.close()
#     conn.close()
#     return rows

# def get_diario_all(lote_nombre: str = ''):
#     conn = get_db_connection()
#     cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     if lote_nombre and lote_nombre != 'VACIO':
#         cur.execute("SELECT id, fecha_recepcion FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
#         cabecera = cur.fetchone()
#         if cabecera:
#             id_lote = cabecera['id']
#             cur.execute('SELECT * FROM data_diario WHERE id_lote = %s ORDER BY dias ASC', (id_lote,))
#             rows = cur.fetchall()
#             if len(rows) == 0:
#                 generar_estructura_diario(cur, lote_nombre, id_lote, cabecera['fecha_recepcion'])
#                 conn.commit()
#                 cur.execute('SELECT * FROM data_diario WHERE id_lote = %s ORDER BY dias ASC', (id_lote,))
#                 rows = cur.fetchall()
#         else: rows = []
#     else: rows = []
#     cur.close()
#     conn.close()
#     return rows

# def update_registro_diario_field(id_reg: int, columna: str, valor: str) -> tuple[bool, str]:
#     mapa_columnas = {'fecha': 'fecha_dia', 'semana': 'sem'}
#     col_db = mapa_columnas.get(columna, columna)
    
#     COLUMNAS_PERMITIDAS = {
#         'fecha_dia', 'dias', 'sem', 'mortalidad', 'sel', 'otros', 
#         'produccion', 'consumo_kg', 'observaciones', 'consumo_agua',
#         'peso_tabla', 'peso_real', 'unif_10_menos', 'porc_uniformidad', 
#         'unif_10_mas', 'coef_variacion', 'saldo_aves', 'consumo_gr_a_d',
#         'consumo_gr_a_tab', 'percent_diario_prod', 'prom_ave_dia_cc'
#     }
    
#     if col_db not in COLUMNAS_PERMITIDAS: return False, f"Columna {col_db} no permitida"
    
#     valor_db = parse_empty(valor)
#     conn = get_db_connection()
#     cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
#     try:
#         if col_db in ['mortalidad', 'sel']:
#             # 1. Averiguar de qué lote estamos hablando
#             cur.execute("SELECT id_lote FROM data_diario WHERE id_diario = %s", (id_reg,))
#             lote_obj = cur.fetchone()
            
#             if lote_obj and lote_obj['id_lote']:
#                 id_lote = lote_obj['id_lote']
                
#                 # 2. BLINDAJE ANTI-DEADLOCK: Bloqueamos las filas en orden estricto (Semáforo)
#                 cur.execute("SELECT id_diario FROM data_diario WHERE id_lote = %s ORDER BY dias ASC FOR UPDATE", (id_lote,))
                
#                 # 3. Guardar el dato actual que digitó el operario
#                 cur.execute(f'UPDATE data_diario SET "{col_db}" = %s WHERE id_diario = %s', (valor_db, id_reg))
                
#                 # 4. Traer aves iniciales
#                 cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE id = %s", (id_lote,))
#                 cab_info = cur.fetchone()
#                 aves_iniciales = 1.0 
#                 if cab_info and cab_info['no_pollitas_recibidas']:
#                     val_aves = to_float_safe(cab_info['no_pollitas_recibidas'])
#                     if val_aves > 0: aves_iniciales = val_aves
                
#                 # 5. Traer datos limpios para el recálculo
#                 cur.execute("SELECT id_diario, mortalidad, sel FROM data_diario WHERE id_lote = %s ORDER BY dias ASC", (id_lote,))
#                 filas = cur.fetchall()
                
#                 mort_acumulada = 0.0
#                 saldo_actual = aves_iniciales
#                 valores_update = [] # <--- Lista para armar el súper paquete
                
#                 for f in filas:
#                     m = to_float_safe(f['mortalidad'])
#                     s = to_float_safe(f['sel'])
                    
#                     mort_dia = m + s
#                     porc_sem = (mort_dia / aves_iniciales) * 100
                    
#                     mort_acumulada += mort_dia
#                     saldo_actual -= mort_dia
#                     porc_acum = (mort_acumulada / aves_iniciales) * 100
                    
#                     # Agregamos los cálculos a la lista, no hacemos insert todavía
#                     valores_update.append((round(porc_sem, 2), round(porc_acum, 2), int(round(saldo_actual)), f['id_diario']))
                
#                 # 6. INSERCIÓN EN BLOQUE: Actualiza las 770 filas en 1 solo viaje a la BD
#                 if valores_update:
#                     psycopg2.extras.execute_values(
#                         cur,
#                         """
#                         UPDATE data_diario AS d 
#                         SET porc_mort_sem = v.porc_mort_sem, 
#                             porc_mort_acum = v.porc_mort_acum, 
#                             saldo_aves = v.saldo_aves 
#                         FROM (VALUES %s) AS v(porc_mort_sem, porc_mort_acum, saldo_aves, id_diario) 
#                         WHERE d.id_diario = v.id_diario
#                         """,
#                         valores_update
#                     )
#             else:
#                 # Si por algún motivo no hay lote, guarda el dato de forma plana
#                 cur.execute(f'UPDATE data_diario SET "{col_db}" = %s WHERE id_diario = %s', (valor_db, id_reg))
#         else:
#             # Si tocan cualquier otra columna (producción, agua, peso), solo guarda esa celda
#             cur.execute(f'UPDATE data_diario SET "{col_db}" = %s WHERE id_diario = %s', (valor_db, id_reg))
            
#         conn.commit()
#         return True, "Ok"
#     except Exception as e:
#         conn.rollback()
#         return False, str(e)
#     finally:
#         cur.close()
#         conn.close()
# # ===========================================================================
# # 4 y 5. REGISTRO SEMANAL UNIFICADO (LEVANTE Y PRODUCCIÓN)
# # ===========================================================================

# def generar_estructura_semanal_unificada(cur, lote_nombre, fecha_recepcion, id_lote):
#     """ Genera de la semana 1 a la 110 en una sola tabla (bd_vargas) ultrarrápido """
#     if not id_lote or not lote_nombre: return
    
#     cur.execute("SELECT COUNT(*) AS total FROM bd_vargas WHERE id_lote = %s", (id_lote,))
#     row = cur.fetchone()
#     count_val = row['total'] if hasattr(row, 'keys') else row[0]
#     if count_val > 0: return

#     fecha_base = None
#     if fecha_recepcion and str(fecha_recepcion).strip() != '':
#         try: fecha_base = datetime.strptime(str(fecha_recepcion), '%Y-%m-%d')
#         except ValueError: pass

#     valores = []
#     for i in range(110):
#         semana_vida = i + 1
#         fecha_str = None
#         if fecha_base:
#             fecha_str = (fecha_base + timedelta(days=(semana_vida * 7) - 1)).strftime('%Y-%m-%d')
        
#         # Insertamos el esqueleto unificado
#         valores.append((lote_nombre, id_lote, fecha_str, semana_vida))
        
#     psycopg2.extras.execute_values(
#         cur,
#         "INSERT INTO bd_vargas (lote, id_lote, fecha_fin_sem, sem_prod) VALUES %s",
#         valores
#     )

# def get_semanal_levante_all(lote_nombre: str = ''):
#     """ Trae SOLO las primeras 18 semanas para la pantalla de Levante """
#     conn = get_db_connection()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     if lote_nombre and lote_nombre != 'VACIO':
#         cur.execute("SELECT id, fecha_recepcion FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
#         cabecera = cur.fetchone()
#         if cabecera:
#             id_lote = cabecera['id']
#             cur.execute('SELECT * FROM bd_vargas WHERE id_lote = %s AND sem_prod <= 18 ORDER BY sem_prod ASC', (id_lote,))
#             rows = cur.fetchall()
#             if len(rows) == 0:
#                 generar_estructura_semanal_unificada(cur, lote_nombre, cabecera['fecha_recepcion'], id_lote)
#                 conn.commit()
#                 cur.execute('SELECT * FROM bd_vargas WHERE id_lote = %s AND sem_prod <= 18 ORDER BY sem_prod ASC', (id_lote,))
#                 rows = cur.fetchall()
#         else: rows = []
#     else: rows = []
#     cur.close()
#     conn.close()
#     return rows

# def get_semanal_all(lote_nombre: str = ''):
#     """ Trae de la semana 18 en adelante para la pantalla de Producción """
#     conn = get_db_connection()
#     cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     if lote_nombre and lote_nombre != 'VACIO':
#         cur.execute("SELECT id, fecha_recepcion FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
#         cabecera = cur.fetchone()
#         if cabecera:
#             id_lote = cabecera['id']
#             cur.execute('SELECT * FROM bd_vargas WHERE id_lote = %s AND sem_prod >= 18 ORDER BY sem_prod ASC', (id_lote,))
#             rows = cur.fetchall()
#             if len(rows) == 0:
#                 generar_estructura_semanal_unificada(cur, lote_nombre, cabecera['fecha_recepcion'], id_lote)
#                 conn.commit()
#                 cur.execute('SELECT * FROM bd_vargas WHERE id_lote = %s AND sem_prod >= 18 ORDER BY sem_prod ASC', (id_lote,))
#                 rows = cur.fetchall()
#         else: rows = []
#     else: rows = []
#     cur.close()
#     conn.close()
#     return rows

# def update_semanal_field(id_semanal: int, columna: str, valor: str) -> tuple[bool, dict, str]:
#     """ Guarda absolutamente cualquier dato y ejecuta fórmulas matemáticas en cascada """
#     COLUMNAS_PERMITIDAS = {
#         'fecha_fin_sem', 'sem_prod', 'edad_sem', 
#         'prod_huevo_sem', 'prod_huevo_tab', 'prod_huevo_real', 'h_av_aloj_tab', 'h_av_aloj_real', 'huevo_acum',
#         'masa_huevo_real_sem', 'masa_huevo_tab_sem', 'masa_huevo_real_acum', 'masa_huevo_tab_acum', 'gr_x_huevo',
#         'peso_huevo_real', 'peso_huevo_tab',
#         'consumo_alim_kg', 'consumo_alim_tab', 'consumo_alim_real', 'consumo_alim_k_a_a', 
#         'cons_tab', 'cons_real', 'cons_kilos_real', 'cons_k_acum', 'cons_gr_ave_tab', 'cons_gr_ave_ao',
#         'conv_sem', 'conv_sem_tab', 'conv_acum_tab', 'conv_kg_doc_acum', 'kg_sem', 'kg_acum',
#         'cons_agua_real', 'cons_agua_tab',
#         'mort_sem', 'mort_select_sem', 'mort_venta', 'salidas_acum', 'saldo_ave', 'mort_tab',
#         'percent_mort_sem', 'percent_mort_acum', 'percent_select_sem', 'percent_mort_and_select_acum',
#         'peso_ave_real', 'peso_ave_tab', 'unif', 'cv', 'unif_porc_uni', 'unif_10_menos', 
#         'unif_porc_unif', 'unif_10_mas', 'unif_cv', 't_tarso', 't_tarso_r',
#         'ganancia_ave_dia', 'ganancia_ave', 'porc_cumpl_ganan', 'porc_cumpl_cons',
#         'observaciones', 'observaciones_lev', 'marca_tipo_de', 'lote'
#     }

#     if columna not in COLUMNAS_PERMITIDAS: return False, {}, f"Columna {columna} no permitida"

#     valor_db = parse_empty(valor)
#     conn = get_db_connection()
#     cur  = conn.cursor()
#     campos_actualizados = {}

#     try:
#         cur.execute("SELECT id_lote FROM bd_vargas WHERE id_sem_prod = %s", (id_semanal,))
#         lote_row = cur.fetchone()

#         # Disparador ampliado a Kilos y todas las variaciones de Aves/Inventario
#         if lote_row and lote_row[0] and columna in ['cons_tab', 'cons_kilos_real', 'mort_sem', 'mort_select_sem', 'mort_venta']:
#             id_lote = lote_row[0]
            
#             # Traemos N° Pollitas Recibidas (E8)
#             cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE id = %s", (id_lote,))
#             cab_info = cur.fetchone()
#             aves_iniciales = to_float_safe(cab_info[0]) if cab_info and cab_info[0] else 0.0
            
#             # Bloqueo estricto del histórico
#             cur.execute("""
#                 SELECT id_sem_prod, cons_tab, cons_kilos_real, 
#                        mort_sem, mort_select_sem, mort_venta 
#                 FROM bd_vargas WHERE id_lote = %s ORDER BY sem_prod ASC FOR UPDATE
#             """, (id_lote,))
#             filas = cur.fetchall()

#             cur.execute(f'UPDATE bd_vargas SET "{columna}" = %s WHERE id_sem_prod = %s', (valor_db, id_semanal))

#             # ACUMULADORES MANTENIDOS EN MEMORIA (No se imprimen si la semana no tiene datos)
#             acum_kilos = 0.0
#             acum_gr_ave_tab = 0.0
#             acum_mort = 0.0
#             acum_sel = 0.0
#             acum_otros = 0.0
            
#             valores_update = []

#             for f in filas:
#                 f_id = f[0]
                
#                 # Identificar el dato entrante vs el historial
#                 c_tab    = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_tab') else to_float_safe(f[1])
#                 c_k_real = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'cons_kilos_real') else to_float_safe(f[2])
#                 m_sem    = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_sem') else to_float_safe(f[3])
#                 s_sem    = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_select_sem') else to_float_safe(f[4])
#                 o_sem    = to_float_safe(valor_db) if (f_id == id_semanal and columna == 'mort_venta') else to_float_safe(f[5])

#                 # Matematica progresiva sumativa
#                 acum_kilos += c_k_real
#                 acum_gr_ave_tab += (c_tab * 7)
#                 acum_mort += m_sem
#                 acum_sel += s_sem
#                 acum_otros += o_sem

#                 # REGLA: ¿Hay algún dato tecleado en esta semana específica?
#                 tiene_datos = (c_k_real > 0 or m_sem > 0 or s_sem > 0 or o_sem > 0 or c_tab > 0)
                
#                 # --- FÓRMULAS DE INVENTARIO Y SALDO ---
#                 acu_val = acum_mort + acum_sel + acum_otros
                
#                 # Solo calculamos si hay aves iniciales en cabecera y hay datos en esta semana
#                 acu_out = int(round(acu_val)) if tiene_datos else None
#                 saldo_val = int(round(aves_iniciales - acu_val)) if (aves_iniciales > 0 and tiene_datos) else None

#                 p_mort_sem = round((m_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and m_sem > 0) else None
#                 p_mort_acum = round((acum_mort / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and acum_mort > 0 and tiene_datos) else None
#                 p_sel_sem = round((s_sem / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and s_sem > 0) else None
#                 p_ms_acu = round(((acum_mort + acum_sel) / aves_iniciales) * 100, 2) if (aves_iniciales > 0 and (acum_mort + acum_sel) > 0 and tiene_datos) else None

#                 # --- FÓRMULAS DE ALIMENTO ---
#                 c_k_acum_val = round(acum_kilos, 2) if (c_k_real > 0 or c_tab > 0) else None
                
#                 c_real_val = None
#                 if c_k_real > 0 and saldo_val and saldo_val > 0:
#                     c_real_val = round((c_k_real / saldo_val / 7) * 1000, 2)

#                 gr_ave_tab_val = round(acum_gr_ave_tab, 2) if c_tab > 0 else None

#                 gr_ave_ac_val = None
#                 if c_k_acum_val is not None and saldo_val and saldo_val > 0:
#                     gr_ave_ac_val = round((acum_kilos / saldo_val) * 1000, 2)

#                 valores_update.append((
#                     c_real_val, c_k_acum_val, gr_ave_tab_val, gr_ave_ac_val,
#                     acu_out, p_mort_sem, p_mort_acum, p_sel_sem, p_ms_acu, saldo_val,
#                     f_id
#                 ))

#                 # Extraer info para AJAX a la fila tocada
#                 if f_id == id_semanal:
#                     campos_actualizados['cons_real'] = c_real_val if c_real_val is not None else ''
#                     campos_actualizados['cons_k_acum'] = c_k_acum_val if c_k_acum_val is not None else ''
#                     campos_actualizados['cons_gr_ave_tab'] = gr_ave_tab_val if gr_ave_tab_val is not None else ''
#                     campos_actualizados['cons_gr_ave_ao'] = gr_ave_ac_val if gr_ave_ac_val is not None else ''
                    
#                     campos_actualizados['salidas_acum'] = acu_out if acu_out is not None else ''
#                     campos_actualizados['percent_mort_sem'] = p_mort_sem if p_mort_sem is not None else ''
#                     campos_actualizados['percent_mort_acum'] = p_mort_acum if p_mort_acum is not None else ''
#                     campos_actualizados['percent_select_sem'] = p_sel_sem if p_sel_sem is not None else ''
#                     campos_actualizados['percent_mort_and_select_acum'] = p_ms_acu if p_ms_acu is not None else ''
#                     campos_actualizados['saldo_ave'] = saldo_val if saldo_val is not None else ''

#             if valores_update:
#                 psycopg2.extras.execute_values(
#                     cur,
#                     """
#                     UPDATE bd_vargas AS b
#                     SET cons_real = v.c_real,
#                         cons_k_acum = v.c_k_acum,
#                         cons_gr_ave_tab = v.gr_ave_tab,
#                         cons_gr_ave_ao = v.gr_ave_ac,
#                         salidas_acum = v.acu_out,
#                         percent_mort_sem = v.p_mort_sem,
#                         percent_mort_acum = v.p_mort_acum,
#                         percent_select_sem = v.p_sel_sem,
#                         percent_mort_and_select_acum = v.p_ms_acu,
#                         saldo_ave = v.saldo_val
#                     FROM (VALUES %s) AS v(
#                         c_real, c_k_acum, gr_ave_tab, gr_ave_ac, 
#                         acu_out, p_mort_sem, p_mort_acum, p_sel_sem, p_ms_acu, saldo_val, 
#                         id_sem_prod
#                     )
#                     WHERE b.id_sem_prod = v.id_sem_prod
#                     """,
#                     valores_update,
#                     template="(%s::numeric, %s::numeric, %s::numeric, %s::numeric, %s::integer, %s::numeric, %s::numeric, %s::numeric, %s::numeric, %s::integer, %s::integer)"
#                 )
#         else:
#             cur.execute(f'UPDATE bd_vargas SET "{columna}" = %s WHERE id_sem_prod = %s', (valor_db, id_semanal))

#         conn.commit()
#         return True, campos_actualizados, "Ok"
#     except Exception as e:
#         conn.rollback()
#         print(f"Error BD Semanal: {e}")
#         return False, {}, str(e)
#     finally:
#         cur.close()
#         conn.close()

        
# # ===========================================================================
# # 6. CLASIFICACIÓN PRODUCCIÓN (SV 18 a 109)
# # ===========================================================================

# def generar_estructura_clasificacion(cur, lote_nombre, id_lote):
#     if not id_lote or not lote_nombre: return
#     cur.execute("SELECT COUNT(*) AS total FROM clasificacion_produccion WHERE id_lote = %s", (id_lote,))
#     row = cur.fetchone()
#     count_val = row['total'] if hasattr(row, 'keys') else row[0]
#     if count_val > 0: return

#     valores = []
#     for sv in range(18, 110):
#         valores.append((lote_nombre, id_lote, sv))
        
#     psycopg2.extras.execute_values(
#         cur, "INSERT INTO clasificacion_produccion (lote, id_lote, sv) VALUES %s", valores
#     )

# def get_clasificacion_all(lote_nombre: str = ''):
#     conn = get_db_connection()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     if lote_nombre and lote_nombre != 'VACIO':
#         cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
#         cabecera = cur.fetchone()
#         if cabecera:
#             id_lote = cabecera['id']
#             cur.execute('SELECT * FROM clasificacion_produccion WHERE id_lote = %s ORDER BY sv ASC', (id_lote,))
#             rows = cur.fetchall()
#             if len(rows) == 0:
#                 generar_estructura_clasificacion(cur, lote_nombre, id_lote)
#                 conn.commit()
#                 cur.execute('SELECT * FROM clasificacion_produccion WHERE id_lote = %s ORDER BY sv ASC', (id_lote,))
#                 rows = cur.fetchall()
#         else: rows = []
#     else: rows = []
#     cur.close()
#     conn.close()
#     return rows

# def update_clasificacion_field(id_reg: int, columna: str, valor: str) -> bool:
#     COLUMNAS_PERMITIDAS = {
#         'clas_jum', 'clas_extra', 'clas_aa', 'clas_a', 'clas_b', 'clas_c', 'clas_pipo', 'clas_sucio', 'clas_totiao', 'clas_yema', 'clas_segundas', 'clas_ttl',
#         'acum_jum', 'acum_extra', 'acum_aa', 'acum_a', 'acum_b', 'acum_c', 'acum_pipo', 'acum_sucio', 'acum_totiao', 'acum_yema', 'acum_segundas', 'acum_total',
#         'porc_sem_jum', 'porc_sem_extra', 'porc_sem_aa', 'porc_sem_a', 'porc_sem_b', 'porc_sem_c', 'porc_sem_pipo', 'porc_sem_sucio', 'porc_sem_totiao', 'porc_sem_yema', 'porc_sem_segundas', 'porc_sem_total',
#         'peso_p', 'porc_h_grande', 'porc_acu_jum', 'porc_acu_extra', 'porc_acu_aa', 'porc_acu_a', 'porc_acu_b', 'porc_acu_c', 'porc_acu_pipo', 'porc_acu_sucio', 'porc_acu_totiao', 'porc_acu_yema', 'porc_acu_segundas',
#         'roto', 'peso_h_prom', 'peso_h_tabla'
#     }
#     if columna not in COLUMNAS_PERMITIDAS: return False
#     valor_db = parse_empty(valor)
#     conn = get_db_connection()
#     cur  = conn.cursor()
#     try:
#         cur.execute(f'UPDATE clasificacion_produccion SET "{columna}" = %s WHERE id = %s', (valor_db, id_reg))
#         conn.commit()
#         return cur.rowcount > 0
#     except Exception as e:
#         conn.rollback()
#         return False
#     finally:
#         cur.close()
#         conn.close()

# # ===========================================================================
# # 7. UTILIDADES Y CRUD DE LOTES
# # ===========================================================================

# def get_lotes_distintos():
#     conn = get_db_connection()
#     cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute("SELECT DISTINCT lote FROM cabecera_lotes WHERE lote IS NOT NULL AND TRIM(lote) != '' ORDER BY lote")
#     rows = cur.fetchall()
#     cur.close()
#     conn.close()
#     return [r['lote'] for r in rows]

# def get_todos_los_lotes():
#     conn = get_db_connection()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute("SELECT * FROM cabecera_lotes ORDER BY id DESC")
#     rows = cur.fetchall()
#     cur.close()
#     conn.close()
#     return rows

# def guardar_nuevo_lote(datos):
#     conn = get_db_connection()
#     cur = conn.cursor()
#     try:
#         lote_nombre = parse_empty(datos.get('lote'))
#         cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
#         if cur.fetchone(): return False, f"Ya existe un lote registrado como '{lote_nombre}'."

#         cur.execute("""
#             INSERT INTO cabecera_lotes (
#                 lote, cliente, ciudad, clima, responsable_tecnico, nutricionista, granja_lev, fecha_recepcion, no_pollitas_recibidas, variedad, peso, 
#                 unidad_peso, uniformidad, coeficiente_variacion, granja_prod, fecha_encasetamiento, no_aves_encasetadas, tipo_galpon, marca_galpon, unidad_medida, validacion
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, True) RETURNING id
#         """, (
#             lote_nombre, parse_empty(datos.get('cliente')), parse_empty(datos.get('ciudad')), parse_empty(datos.get('clima')), parse_empty(datos.get('responsable_tecnico')), parse_empty(datos.get('nutricionista')),
#             parse_empty(datos.get('granja_lev')), parse_empty(datos.get('fecha_recepcion')), parse_empty(datos.get('no_pollitas_recibidas')), parse_empty(datos.get('variedad')), parse_empty(datos.get('peso')), parse_empty(datos.get('unidad_peso')),
#             parse_empty(datos.get('uniformidad')), parse_empty(datos.get('coeficiente_variacion')), parse_empty(datos.get('granja_prod')), parse_empty(datos.get('fecha_encasetamiento')), parse_empty(datos.get('no_aves_encasetadas')), parse_empty(datos.get('tipo_galpon')),
#             parse_empty(datos.get('marca_galpon')), parse_empty(datos.get('unidad_medida'))
#         ))
#         id_lote = cur.fetchone()[0]
        
#         # GATILLOS UNIFICADOS
#         generar_estructura_diario(cur, lote_nombre, id_lote, datos.get('fecha_recepcion'))
#         generar_estructura_semanal_unificada(cur, lote_nombre, datos.get('fecha_recepcion'), id_lote)
#         generar_estructura_clasificacion(cur, lote_nombre, id_lote)

#         conn.commit()
#         return True, "Lote creado exitosamente"
#     except Exception as e:
#         conn.rollback()
#         return False, str(e)
#     finally:
#         cur.close()
#         conn.close()

# def actualizar_lote(id_lote, datos):
#     conn = get_db_connection()
#     cur = conn.cursor()
#     try:
#         cur.execute("""
#             UPDATE cabecera_lotes SET 
#                 lote = %s, cliente = %s, ciudad = %s, clima = %s, responsable_tecnico = %s, nutricionista = %s, granja_lev = %s, 
#                 fecha_recepcion = %s, no_pollitas_recibidas = %s, variedad = %s, peso = %s, unidad_peso = %s, uniformidad = %s, 
#                 coeficiente_variacion = %s, granja_prod = %s, fecha_encasetamiento = %s, no_aves_encasetadas = %s, tipo_galpon = %s, marca_galpon = %s, 
#                 unidad_medida = %s, validacion = False
#             WHERE id = %s
#         """, (
#             parse_empty(datos.get('lote')), parse_empty(datos.get('cliente')), parse_empty(datos.get('ciudad')), parse_empty(datos.get('clima')), parse_empty(datos.get('responsable_tecnico')), parse_empty(datos.get('nutricionista')),
#             parse_empty(datos.get('granja_lev')), parse_empty(datos.get('fecha_recepcion')), parse_empty(datos.get('no_pollitas_recibidas')), parse_empty(datos.get('variedad')), parse_empty(datos.get('peso')), parse_empty(datos.get('unidad_peso')),
#             parse_empty(datos.get('uniformidad')), parse_empty(datos.get('coeficiente_variacion')), parse_empty(datos.get('granja_prod')), parse_empty(datos.get('fecha_encasetamiento')), parse_empty(datos.get('no_aves_encasetadas')), parse_empty(datos.get('tipo_galpon')),
#             parse_empty(datos.get('marca_galpon')), parse_empty(datos.get('unidad_medida')), id_lote
#         ))
#         conn.commit()
#         cur.execute("UPDATE cabecera_lotes SET validacion = True WHERE id = %s", (id_lote,))
#         conn.commit()
#         return True, "Lote actualizado exitosamente"
#     except Exception as e:
#         conn.rollback()
#         return False, str(e)
#     finally:
#         cur.close()
#         conn.close()

# def borrar_lote(id_lote):
#     conn = get_db_connection()
#     cur = conn.cursor()
#     try:
#         cur.execute("DELETE FROM cabecera_lotes WHERE id = %s", (id_lote,))
#         conn.commit()
#         return True
#     except Exception as e:
#         conn.rollback()
#         return False
#     finally:
#         cur.close()
#         conn.close()

# def get_opciones_dinamicas():
#     conn = get_db_connection()
#     cur = conn.cursor()
#     opciones = {}
#     columnas = ['cliente', 'ciudad', 'clima', 'responsable_tecnico', 'nutricionista', 'granja_lev', 'variedad', 'granja_prod', 'tipo_galpon', 'marca_galpon']
#     for col in columnas:
#         opciones[col] = []
#         try:
#             cur.execute(f'SELECT DISTINCT "{col}" FROM cabecera_lotes WHERE "{col}" IS NOT NULL AND TRIM("{col}"::text) != \'\' ORDER BY "{col}"')
#             opciones[col] = [row[0] for row in cur.fetchall()]
#         except:
#             conn.rollback()
#     cur.close()
#     conn.close()
#     return opciones