# models/diario/services.py
from datetime import datetime, timedelta, date
from models.base import get_db_connection, parse_empty, to_float_safe
from models.diario.schemas import MAPA_COLUMNAS, COLUMNAS_PERMITIDAS
from models.diario import model
from models.cabecera.model import fetch_cabecera_by_lote 
from models.semanal.services import recalcular_lote_semanal_completo_directo

def obtener_guia_grad_tab():
    """ Devuelve la guia teorica con margen de sobra para cubrir los 770 dias sin error de indice """
    guia = [
        12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 31.0,
        32.0, 33.0, 35.0, 36.0, 37.0, 38.0, 40.0, 40.0, 40.0, 40.0, 40.0, 41.0, 42.0, 43.0, 44.0, 46.0, 48.0, 48.0, 49.0, 49.0,
        51.0, 51.0, 53.0, 54.0, 55.0, 56.0, 56.0, 56.0, 56.0, 58.0, 60.0, 60.0, 62.0, 64.0, 66.0, 66.0, 66.0, 66.0, 66.0, 68.0,
        70.0, 70.0, 72.0, 72.0, 74.0, 74.0, 74.0, 74.0, 74.0, 74.0, 74.0, 76.0, 76.0, 76.0, 76.0, 78.0, 78.0, 80.0, 80.0, 82.0,
        82.0, 82.0, 82.0, 82.0, 84.0, 86.0, 88.0, 90.0, 90.0, 90.0, 94.0, 94.0, 94.0, 94.0, 99.0, 99.0, 99.0, 99.0, 99.0, 103.0,
        103.0, 103.0, 103.0, 107.0, 107.0, 107.0, 107.0, 107.0
    ]
    # Rellenamos con 600 dias adicionales al final para blindar la funcion (total 808 items)
    guia += [108.0] * 14 + [109.0] * 34 + [108.0] * 53 + [105.0] * 600
    return guia

def aplicar_parche_diario(id_lote):
    """ Inyecta los valores teoricos de Gr.A.D Tab en celdas vacias """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        guia_grad_tab = obtener_guia_grad_tab()
        cur.execute("SELECT id_diario, dias, consumo_gr_a_tab FROM data_diario WHERE id_lote = %s ORDER BY dias ASC", (id_lote,))
        filas = cur.fetchall()
        valores_update = []
        
        for fila in filas:
            id_diario = fila[0]
            dia = int(fila[1]) if fila[1] else 0
            val_actual = fila[2]
            
            # Aseguramos de que el dia no supere el tamano del arreglo
            if 1 <= dia <= len(guia_grad_tab):
                val_teorico = guia_grad_tab[dia - 1]
                
                # Comprobacion limpia y a prueba de fallos matematicos
                es_vacio = False
                if val_actual is None:
                    es_vacio = True
                else:
                    try:
                        es_vacio = (float(val_actual) == 0.0)
                    except:
                        es_vacio = str(val_actual).strip() in ('', 'None')

                if es_vacio:
                    valores_update.append((val_teorico, id_diario))
                    
        if valores_update:
            cur.executemany("UPDATE data_diario SET consumo_gr_a_tab = %s WHERE id_diario = %s", valores_update)
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR PARCHE DIARIO]: {e}")
    finally:
        cur.close()
        conn.close()

def generar_estructura_diario(lote_nombre, id_lote, fecha_recepcion):
    """ Despliega la matriz secuencial de 770 registros en la base de datos para data_diario """
    if not id_lote or not lote_nombre: 
        return
    if model.count_diario_lote(id_lote) > 0: 
        return

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

    guia_grad_tab = obtener_guia_grad_tab()
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
            0.0, 0.0, 0.0, guia_grad_tab[i], 0.0, 0.0
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
    except Exception as e:
        conn.rollback()
        print(f"[ERROR CRITICO GENERACION DIARIO]: {str(e)}")
    finally:
        cur.close()
        conn.close()

def get_diario_all(lote_nombre: str = ''):
    """ Obtiene la matriz completa y fuerza los parches de sincronizacion """
    if not lote_nombre or lote_nombre == 'VACIO': 
        return []
    
    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera: 
        return []
    
    id_lote = cabecera['id']
    
    if model.count_diario_lote(id_lote) == 0:
        generar_estructura_diario(lote_nombre, id_lote, cabecera.get('fecha_recepcion'))
        
    aplicar_parche_diario(id_lote)
        
    return model.fetch_diario_por_lote(id_lote)

def update_registro_diario_field(id_reg: int, columna: str, valor: str) -> tuple[bool, dict, str]:
    """ Ejecuta guardados directos y recalculos matematicos en cascada """
    import psycopg2.extras 
    
    col_db = MAPA_COLUMNAS.get(columna, columna)
    if col_db not in COLUMNAS_PERMITIDAS: 
        return False, {}, f"Columna '{col_db}' no permitida en el Diario."
    
    if str(valor).strip() == '0':
        valor_db = 0
    else:
        valor_db = parse_empty(valor)
        
    campos_diarios_actualizados = {}
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
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
        
import pandas as pd
import psycopg2.extras
import numpy as np
from models.base import get_db_connection

def procesar_excel_diario(archivo, lote_nombre):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # 1. Obtener ID del lote
        lote_variante = f"LOTE {lote_nombre}" if not lote_nombre.upper().startswith("LOTE") else lote_nombre.replace("LOTE ", "")
        cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s OR lote = %s", (lote_nombre, lote_variante))
        lote_row = cur.fetchone()
        
        if not lote_row:
            return False, f"No se encontró el lote '{lote_nombre}' en la base de datos."
        id_lote = lote_row['id']

        # 2. Leer el Excel
        df = pd.read_excel(archivo, sheet_name='DIARIO', skiprows=7, header=None)
        
        df = df[df[0].notnull()] 
        df = df.replace(r'^\s*$', np.nan, regex=True)
        df = df.replace({np.nan: None})

        # 3. Preparar los datos
        valores_a_insertar = []
        fechas_a_cargar = [] 

        for index, fila in df.iterrows():
            fecha_str = str(fila[0].date()) if hasattr(fila[0], 'date') else str(fila[0])
            fechas_a_cargar.append(fecha_str)
            
            # --- CÁLCULO PERFECTO DE LA SEMANA ---
            dias_valor = fila[1]
            semana_calculada = None
            
            if dias_valor is not None:
                try:
                    d = int(dias_valor)
                    semanas_completas = d // 7
                    dias_resto = d % 7
                    if dias_resto == 0:
                        semana_calculada = str(semanas_completas)
                    else:
                        semana_calculada = f"{semanas_completas} + {dias_resto}/7"
                except:
                    semana_calculada = str(fila[2]) # Respaldo en caso de error
            
            valores = (
                lote_nombre,                                                       
                fecha_str, 
                dias_valor,                                                           
                semana_calculada, # Usamos el cálculo en lugar de leer el Excel directamente           
                fila[3], fila[4], fila[5], fila[6], fila[7], fila[8], 
                fila[9], fila[10], fila[11], fila[12], fila[13], fila[14], 
                id_lote,
                None, None, None, None, None, None, None, None, None, None, None
            )
            valores_a_insertar.append(valores)

        if not valores_a_insertar:
            return False, "El archivo está vacío o no tiene datos válidos."

        # Prevención de duplicados
        if fechas_a_cargar:
            cur.execute(
                "DELETE FROM data_diario WHERE lote = %s AND fecha_dia = ANY(%s)", 
                (lote_nombre, fechas_a_cargar)
            )

        # 4. Inserción Masiva
        query_insert = """
            INSERT INTO data_diario (
                lote, fecha_dia, dias, sem, produccion, consumo_kg, 
                mortalidad, sel, otros, observaciones, saldo_aves, 
                consumo_gr_a_d, consumo_gr_a_tab, percent_diario_prod, 
                prom_ave_dia_cc, consumo_agua, id_lote,
                peso_tabla, peso_real, unif_10_menos, porc_uniformidad, 
                unif_10_mas, coef_variacion, porc_mort_sem, porc_mort_acum, 
                cons_k_acum, cons_gr_ave_tab_acum, cons_gr_ave_ac
            ) VALUES %s
        """
        
        psycopg2.extras.execute_values(cur, query_insert, valores_a_insertar)
        conn.commit()
        return True, f"Se actualizaron {len(valores_a_insertar)} registros diarios correctamente."

    except Exception as e:
        conn.rollback()
        print(f"[ERROR CARGA MASIVA DIARIO]: {str(e)}")
        return False, f"Error al procesar el archivo: {str(e)}"
    
    finally:
        cur.close()
        conn.close()