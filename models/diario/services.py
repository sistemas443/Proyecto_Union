from datetime import datetime, timedelta, date
from models.base import get_db_connection, parse_empty, to_float_safe
from models.diario.schemas import MAPA_COLUMNAS, COLUMNAS_PERMITIDAS
from models.diario import model
from models.cabecera.model import fetch_cabecera_by_lote 
from models.semanal.services import recalcular_lote_semanal_completo_directo

def generar_estructura_diario(lote_nombre, id_lote, fecha_recepcion):
    """
    Despliega la matriz secuencial de 770 registros diarios en la base de datos para la tabla data_diario.
    Calcula los agrupadores por semana y mes, proporcionando la base transaccional requerida
    para la captura de información continua durante todo el ciclo productivo del lote.
    """
    if not id_lote or not lote_nombre: 
        return
    if model.count_diario_lote(id_lote) > 0: 
        return

    print(f"\n[DIARIO] Generando 770 dias estandar para: {lote_nombre} (ID: {id_lote})")

    fecha_base = None
    if fecha_recepcion and str(fecha_recepcion).strip() != '' and str(fecha_recepcion).strip().lower() != 'none':
        try: 
            if isinstance(fecha_recepcion, datetime):
                fecha_base = fecha_recepcion
            elif isinstance(fecha_recepcion, date):
                fecha_base = datetime.combine(fecha_recepcion, datetime.min.time())
            else:
                f_str = str(fecha_recepcion).split()[0].replace('/', '-')
                try:
                    fecha_base = datetime.strptime(f_str, '%Y-%m-%d')
                except ValueError:
                    fecha_base = datetime.strptime(f_str, '%d-%m-%Y')
        except Exception as e:
            print(f"[ERROR FECHA GENERACION DIARIO]: {e}")

    if not fecha_base:
        fecha_base = datetime.now()

    valores = [] 

    for i in range(770):
        fecha_str = (fecha_base + timedelta(days=i)).strftime('%Y-%m-%d')
        
        dia_vida = i + 1
        semanas_completas = i // 7
        dias_extra = (i % 7) + 1
        
        if dias_extra == 7:
            semana_str = str(semanas_completas + 1)
        else:
            semana_str = f"{semanas_completas} + {dias_extra}/"
    
        valores.append((
            lote_nombre, id_lote, fecha_str, dia_vida, semana_str,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        ))
    
    valores.sort(key=lambda x: x[3])
    
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.executemany("""
            INSERT INTO data_diario (
                lote, id_lote, fecha_dia, dias, sem, 
                mortalidad, sel, consumo_kg, consumo_gr_a_tab, otros, peso_real
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, valores)
        
        conn.commit()
        print(f"[BD DIARIO] Exito: Estructura de 770 dias generada independientemente.")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR CRITICO GENERACION DIARIO]: {str(e)}")
    finally:
        cur.close()
        conn.close()

def get_diario_all(lote_nombre: str = ''):
    """
    Obtiene la totalidad de la matriz del ciclo de recolección diaria de datos.
    Implementa el mecanismo de auto-generación de esquemas.
    """
    if not lote_nombre or lote_nombre == 'VACIO': 
        return []
    
    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera: 
        return []
    
    id_lote = cabecera['id']
    
    if model.count_diario_lote(id_lote) == 0:
        generar_estructura_diario(lote_nombre, id_lote, cabecera.get('fecha_recepcion'))
        
    return model.fetch_diario_por_lote(id_lote)

def update_registro_diario_field(id_reg: int, columna: str, valor: str) -> tuple[bool, dict, str]:
    import psycopg2.extras 
    
    col_db = MAPA_COLUMNAS.get(columna, columna)
    if col_db not in COLUMNAS_PERMITIDAS: 
        return False, {}, f"Columna '{col_db}' no permitida en el Diario."
    
    # Blindaje para aceptar el 0 como un dato real y biológicamente válido
    if str(valor).strip() == '0':
        valor_db = 0
    else:
        valor_db = parse_empty(valor)
    campos_diarios_actualizados = {}
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Se agrega 'consumo_agua' como columna detonante del recálculo
        if col_db in ['mortalidad', 'sel', 'consumo_kg', 'otros', 'peso_real', 'produccion', 'consumo_agua']:
            cur.execute("SELECT id_lote FROM data_diario WHERE id_diario = %s", (id_reg,))
            row_lote = cur.fetchone()
            id_lote = row_lote['id_lote'] if row_lote else None
            
            if id_lote:
                cur.execute("SELECT no_pollitas_recibidas, COALESCE(unidad_peso, 1.0) AS u_peso FROM cabecera_lotes WHERE id = %s FOR UPDATE", (id_lote,))
                
                cab_info = cur.fetchone()
                aves_iniciales = to_float_safe(cab_info['no_pollitas_recibidas']) if cab_info and cab_info['no_pollitas_recibidas'] else 1.0 
                u_peso = to_float_safe(cab_info['u_peso']) if cab_info else 1.0
                
                cur_update = conn.cursor()
                cur_update.execute(f'UPDATE data_diario SET "{col_db}" = %s WHERE id_diario = %s', (valor_db, id_reg))
                cur_update.close()
                
                # Se agrega 'consumo_agua' a la extracción de datos
                cur.execute("""
                    SELECT id_diario, mortalidad, sel, consumo_kg, otros, produccion, consumo_agua
                    FROM data_diario 
                    WHERE id_lote = %s 
                    ORDER BY dias ASC
                """, (id_lote,))
                filas = cur.fetchall()
                
                mort_acumulada = 0.0
                saldo_actual = aves_iniciales
                acum_kilos = 0.0
                acum_gr_real_exacto = 0.0 
                
                valores_update = []
                
                for f in filas:
                    f_id = f['id_diario']
                    
                    m_val = f['mortalidad'] if f['mortalidad'] is not None else 0
                    s_val = f['sel'] if f['sel'] is not None else 0
                    k_val = f['consumo_kg'] if f['consumo_kg'] is not None else 0
                    o_val = f['otros'] if f['otros'] is not None else 0
                    prod_val = f['produccion'] if f['produccion'] is not None else 0
                    agua_val = f['consumo_agua'] if f['consumo_agua'] is not None else 0
                    
                    m = to_float_safe(valor_db) if (int(f_id) == int(id_reg) and col_db == 'mortalidad') else to_float_safe(m_val)
                    s = to_float_safe(valor_db) if (int(f_id) == int(id_reg) and col_db == 'sel') else to_float_safe(s_val)
                    kilos = to_float_safe(valor_db) if (int(f_id) == int(id_reg) and col_db == 'consumo_kg') else to_float_safe(k_val)
                    o = to_float_safe(valor_db) if (int(f_id) == int(id_reg) and col_db == 'otros') else to_float_safe(o_val)
                    prod = to_float_safe(valor_db) if (int(f_id) == int(id_reg) and col_db == 'produccion') else to_float_safe(prod_val)
                    agua = to_float_safe(valor_db) if (int(f_id) == int(id_reg) and col_db == 'consumo_agua') else to_float_safe(agua_val)
                    
                    mort_dia = m + s + o
                    mort_acumulada += mort_dia
                    
                    saldo_actual -= mort_dia
                    if saldo_actual < 0: 
                        saldo_actual = 0
                    
                    base_inicial = aves_iniciales if aves_iniciales > 0 else 1.0
                    
                    porc_sem = (float(mort_dia) / float(base_inicial)) * 100
                    porc_acum = (float(mort_acumulada) / float(base_inicial)) * 100
                    acum_kilos += kilos     
                
                    real_gr_ave_exacto = (kilos * u_peso * 1000.0) / float(saldo_actual) if saldo_actual > 0 else 0.0
                    acum_gr_real_exacto += real_gr_ave_exacto

                    porc_prod_exacto = (float(prod) / float(saldo_actual)) * 100.0 if saldo_actual > 0 else 0.0
                    
                    # FÓRMULA DE PROMEDIO DE AGUA: =(O / J) * 1000 a 1 decimal
                    prom_agua_exacto = round((float(agua) / float(saldo_actual)) * 1000.0, 1) if saldo_actual > 0 else 0.0

                    valores_update.append((
                        round(porc_sem, 2), 
                        round(porc_acum, 2), 
                        int(round(saldo_actual)),
                        round(real_gr_ave_exacto, 1), 
                        round(acum_kilos, 2),
                        None, 
                        round(acum_gr_real_exacto, 2) if acum_gr_real_exacto > 0 else None, 
                        round(porc_prod_exacto, 1), 
                        round(prom_agua_exacto, 2), 
                        f_id
                    ))
                    
                    if int(f_id) == int(id_reg):
                        campos_diarios_actualizados = {
                            'produccion':          int(prod),
                            'consumo_agua':        float(agua),
                            'saldo_aves':          int(round(saldo_actual)),
                            'consumo_gr_a_d':      f"{real_gr_ave_exacto:.1f}" if real_gr_ave_exacto > 0 else '0.0',
                            'percent_diario_prod': f"{porc_prod_exacto:.1f}" if porc_prod_exacto > 0 else '0.0',
                            'prom_ave_dia_cc': f"{prom_agua_exacto:.1f}" if prom_agua_exacto > 0 else '0.0'
                        }
                
                if valores_update:
                    cur_update = conn.cursor()
                    cur_update.executemany("""
                        UPDATE data_diario 
                        SET porc_mort_sem = %s, 
                            porc_mort_acum = %s, 
                            saldo_aves = %s,
                            consumo_gr_a_d = %s, 
                            cons_k_acum = %s, 
                            cons_gr_ave_tab_acum = %s, 
                            cons_gr_ave_ac = %s,
                            percent_diario_prod = %s,
                            prom_ave_dia_cc = %s
                        WHERE id_diario = %s
                    """, valores_update)
                    cur_update.close()
                
                # ---------------------------------------------------------
                # EL DISPARADOR SEGURO (Solo se ejecuta si se tocaron números)
                # ---------------------------------------------------------
                try:
                    cur_sync = conn.cursor()
                    recalcular_lote_semanal_completo_directo(id_lote, cur_sync)
                    cur_sync.close()
                except Exception as ex_motor:
                    print(f"[DISPARADOR ADVERTENCIA] No se actualizo semanal: {str(ex_motor)}")
                    
            else:
                cur_update = conn.cursor()
                import models.diario.model as diario_model
                diario_model.guardar_dato_simple(id_reg, col_db, valor_db, cur_update)
                cur_update.close()
        else:
            # Si tocan columnas NO matemáticas (ej. observaciones), guarda directo y no recalcula nada
            cur_update = conn.cursor()
            import models.diario.model as diario_model
            diario_model.guardar_dato_simple(id_reg, col_db, valor_db, cur_update)
            cur_update.close()
            
        conn.commit()
        return True, campos_diarios_actualizados, "Ok"
        
    except Exception as e:
        import traceback
        traceback.print_exc() 
        conn.rollback()
        return False, {}, f"Error interno BD: {str(e)}"
    finally:
        cur.close()
        conn.close()