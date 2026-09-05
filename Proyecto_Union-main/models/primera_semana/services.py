# models/primera_semana/services.py
from datetime import datetime, timedelta, date
import traceback
from models.base import get_db_connection, parse_empty, to_float_safe
from models.cabecera.model import fetch_cabecera_by_lote
from models.primera_semana.schemas import COLUMNAS_PERMITIDAS

def generar_estructura_primera_semana(lote_nombre, fecha_recepcion, datos_dia_0=None):
    """
    Genera la estructura fundacional de 8 días (Día 0 al 7) para un lote específico.
    Inyecta automáticamente los valores teóricos de consumo diario y peso basándose
    en las guías estandarizadas. Opcionalmente, inicializa el Día 0 con datos externos.
    """
    if not lote_nombre: 
        return

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Identificación del identificador maestro del lote para vinculación relacional
        cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
        res_id = cur.fetchone()
        id_lote = res_id[0] if res_id else None

        # Proceso de autoreparación: Verifica si la estructura está completa.
        # Si hay filas parciales (menos de 8), las elimina para reconstruir la estructura limpia.
        cur.execute("SELECT COUNT(*) FROM primera_semana WHERE lote = %s", (lote_nombre,))
        conteo_filas = cur.fetchone()[0]
        
        if conteo_filas == 8:
            return  
            
        elif conteo_filas > 0:
            print(f"[AUTOREPARACIÓN] Limpiando {conteo_filas} filas incompletas para el lote {lote_nombre}...")
            cur.execute("DELETE FROM primera_semana WHERE lote = %s", (lote_nombre,))
            conn.commit()

        # Normalización y procesamiento seguro del formato de la fecha de recepción
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
            except Exception:
                pass

        if not fecha_base:
            fecha_base = datetime.now()

        # Arreglos constantes con los valores teóricos estándar para la primera semana
        etiquetas_semana = ["0", "0/1", "0/2", "0/3", "0/4", "0/5", "0/6", "0/7"]
        tabla_diaria_guia = [0.0, 5.4, 8.1, 9.5, 10.9, 12.2, 13.6, 15.7]
        peso_tabla_guia = [38, 41, 46, 52, 59, 65, 72, 80]
        
        # Iteración para la inserción secuencial de los 8 días
        for i in range(8):
            fecha_str = (fecha_base + timedelta(days=i)).strftime('%Y-%m-%d')
            semana_str = etiquetas_semana[i]
            
            # Inicialización de variables con valores por defecto o valores de la guía teórica
            v_mort = 0
            v_sel = 0
            v_peso_tab = peso_tabla_guia[i]   
            v_cons_tab = tabla_diaria_guia[i] 
            v_p_real = 0.0
            v_10_menos = 0.0
            v_unif = 0.0
            v_10_mas = 0.0
            v_cv = 0.0
            v_c_kg = 0.0
            v_k_acum = 0.0

            # Extracción estructurada de los parámetros del Día 0 si fueron proporcionados
            if i == 0 and datos_dia_0:
                def obtener_valor_estricto(llave1, llave2, defecto=0.0):
                    val = datos_dia_0.get(llave1) if datos_dia_0.get(llave1) is not None else datos_dia_0.get(llave2)
                    if val is None or str(val).strip() == '':
                        return defecto
                    return to_float_safe(val)

                v_mort = int(obtener_valor_estricto('mortalidad', 'dia0_mortalidad', 0))
                v_sel = int(obtener_valor_estricto('sel', 'dia0_sel', 0))
                
                v_p_real = round(obtener_valor_estricto('peso_real', 'dia0_peso_real', 0.0), 2)
                v_10_menos = round(obtener_valor_estricto('unif_10_menos', 'dia0_unif_10_menos', 0.0), 1)
                v_unif = round(obtener_valor_estricto('porc_uniformidad', 'dia0_porc_uniformidad', 0.0), 2)
                v_10_mas = round(obtener_valor_estricto('unif_10_mas', 'dia0_unif_10_mas', 0.0), 1)
                v_cv = round(obtener_valor_estricto('coef_variacion', 'dia0_coef_variacion', 0.0), 2)
                
                v_c_kg = int(round(obtener_valor_estricto('consumo_kg', 'dia0_consumo_kg', 0.0)))
                v_k_acum = obtener_valor_estricto('cons_k_acum', 'dia0_cons_k_acum', 0.0)

            # Ejecución de la inserción en base de datos
            cur.execute("""
                INSERT INTO primera_semana (
                    lote, id_lote, fecha, semana, 
                    mortalidad, sel, porc_mort_sem, porc_mort_acum, saldo_aves,
                    peso_tabla, peso_real, unif_10_menos, porc_uniformidad, unif_10_mas,
                    coef_variacion, observaciones,
                    consumo_gr_a_tab, consumo_kg, consumo_gr_a_d, cons_k_acum, cons_gr_ave_tab_acum, cons_gr_ave_ac
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                lote_nombre, id_lote, fecha_str, semana_str, 
                v_mort, v_sel, 0.0, 0.0, 0,                        
                v_peso_tab, v_p_real, v_10_menos, v_unif, v_10_mas,    
                v_cv, '',                                              
                v_cons_tab, v_c_kg, 0.0, v_k_acum, 0.0, 0.0
            ))

        conn.commit()
        print(f"[ÉXITO] Estructura de 8 días creada exitosamente para el lote: {lote_nombre}")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR GENERAR 1ERA SEMANA]: {e}")
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


def get_primera_semana_by_lote(lote_nombre):
    """
    Consulta los registros de la primera semana, sincroniza los datos relevantes desde 
    la tabla de registro diario (data_diario), aplica cálculos en cascada y formatea 
    la salida de datos para su presentación en la interfaz de usuario.
    """
    if not lote_nombre or lote_nombre == 'VACIO':
        return []

    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera:
        return []

    fecha_recep = cabecera.get('fecha_recepcion')
    id_lote = cabecera.get('id')

    # Garantiza que la estructura exista antes de intentar consultarla o actualizarla
    generar_estructura_primera_semana(lote_nombre, fecha_recep)

    import psycopg2.extras
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Sincronización cruzada: Actualiza mortalidad, selección y consumo basándose en los registros diarios
        cur.execute("""
            UPDATE primera_semana ps
            SET consumo_kg = dd.consumo_kg,
                mortalidad = dd.mortalidad,
                sel = dd.sel
            FROM data_diario dd
            WHERE ps.lote = dd.lote 
              AND ps.lote = %s
              AND (
                (ps.semana = '0/1' AND dd.dias = 1) OR
                (ps.semana = '0/2' AND dd.dias = 2) OR
                (ps.semana = '0/3' AND dd.dias = 3) OR
                (ps.semana = '0/4' AND dd.dias = 4) OR
                (ps.semana = '0/5' AND dd.dias = 5) OR
                (ps.semana = '0/6' AND dd.dias = 6) OR
                (ps.semana = '0/7' AND dd.dias = 7)
              )
        """, (lote_nombre,))

        # Obtención del parámetro base de población para los cálculos de la cascada
        cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE id = %s", (id_lote,))
        cab_info = cur.fetchone()
        aves_iniciales = float(cab_info['no_pollitas_recibidas']) if cab_info and cab_info['no_pollitas_recibidas'] else 10000.0
        if aves_iniciales <= 0: 
            aves_iniciales = 1.0

        # Ejecución del motor matemático para actualizar saldos y acumulados
        recalcular_primera_semana_cascada_interna(lote_nombre, aves_iniciales, cur)

        # Extracción de la información ya procesada y sincronizada
        query = """
            SELECT id AS id_diario, lote, fecha AS fecha_dia, semana AS sem,
                   mortalidad, sel, porc_mort_sem, porc_mort_acum, saldo_aves,
                   peso_tabla, peso_real, unif_10_menos, porc_uniformidad,
                   unif_10_mas, coef_variacion, observaciones,
                   consumo_gr_a_tab, consumo_kg, consumo_gr_a_d, 
                   cons_k_acum, cons_gr_ave_tab_acum, cons_gr_ave_ac
            FROM primera_semana
            WHERE lote = %s
            ORDER BY id ASC
        """
        cur.execute(query, (lote_nombre,))
        filas = cur.fetchall()
        
        # Aplicación de reglas de formato estricto para la interfaz web
        for f in filas:
            if f['mortalidad'] is not None: f['mortalidad'] = str(int(float(f['mortalidad'])))
            if f['sel'] is not None: f['sel'] = str(int(float(f['sel'])))
            if f['consumo_kg'] is not None: f['consumo_kg'] = str(int(round(float(f['consumo_kg']))))
            
            # REGLA 1: Kilos Acumulados Reales visualizado estrictamente como ENTERO sin decimales
            if f['cons_k_acum'] is not None: f['cons_k_acum'] = str(int(round(float(f['cons_k_acum']))))
            
            if f['peso_tabla'] is not None: f['peso_tabla'] = str(int(round(float(f['peso_tabla']))))
            if f['peso_real'] is not None: f['peso_real'] = f"{float(f['peso_real']):.2f}"
            if f['unif_10_menos'] is not None: f['unif_10_menos'] = f"{float(f['unif_10_menos']):.1f}"
            if f['porc_uniformidad'] is not None: f['porc_uniformidad'] = f"{float(f['porc_uniformidad']):.2f}"
            if f['unif_10_mas'] is not None: f['unif_10_mas'] = f"{float(f['unif_10_mas']):.1f}"
            if f['coef_variacion'] is not None: f['coef_variacion'] = f"{float(f['coef_variacion']):.2f}"
            
            # Formatos de precisión de dos decimales para variables de gramos
            if f['cons_gr_ave_ac'] is not None: f['cons_gr_ave_ac'] = f"{float(f['cons_gr_ave_ac']):.2f}"
            if f['consumo_gr_a_d'] is not None: f['consumo_gr_a_d'] = f"{float(f['consumo_gr_a_d']):.2f}"
            
            # REGLA 2: Forzar Tabla diaria a imprimirse con precisión estricta de un decimal
            if f['consumo_gr_a_tab'] is not None: f['consumo_gr_a_tab'] = f"{float(f['consumo_gr_a_tab']):.1f}"

        conn.commit() 
        return filas

    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN SINC/LECTURA 1ERA SEMANA]: {str(e)}")
        traceback.print_exc()
        conn.rollback()
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()


def update_primera_semana_field(id_reg: int, columna: str, valor: str) -> tuple[bool, dict, str]:
    """
    Procesa las peticiones de actualización originadas desde la edición en línea en la vista web.
    Realiza validación de columnas, conversión de tipos de datos, actualización del registro 
    y detonación del recálculo en cascada para mantener la integridad referencial.
    """
    if columna not in COLUMNAS_PERMITIDAS:
        return False, {}, f"Columna '{columna}' no permitida"

    # Conversión de tipos de datos y aplicación de reglas de redondeo específicas por columna
    val_final = parse_empty(valor)
    if val_final is not None and columna != 'observaciones':
        val_final = float(val_final)
        if columna in ['peso_real', 'porc_uniformidad', 'coef_variacion']:
            val_final = round(val_final, 2)
        elif columna in ['unif_10_menos', 'unif_10_mas']:
            val_final = round(val_final, 1)
        elif columna in ['peso_tabla', 'consumo_kg']:
            val_final = int(round(val_final))

    conn = get_db_connection()
    cur = conn.cursor()
    campos_actualizados = {}

    try:
        # Actualización del valor individual en la base de datos
        cur.execute(f'UPDATE primera_semana SET "{columna}" = %s WHERE id = %s', (val_final, id_reg))
    
        # Obtención de parámetros necesarios para el recálculo
        cur.execute("SELECT lote FROM primera_semana WHERE id = %s", (id_reg,))
        lote_nombre = cur.fetchone()[0]
        
        cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
        cab_info = cur.fetchone()
        aves_iniciales = float(cab_info[0]) if cab_info and cab_info[0] else 10000.0
        if aves_iniciales <= 0: aves_iniciales = 1.0 

        # Ejecución de la rutina matemática de actualización general
        valores_update, campos_actualizados = recalcular_primera_semana_cascada_interna(lote_nombre, aves_iniciales, cur, id_reg)

        conn.commit()
        return True, campos_actualizados, "Ok"
    except Exception as e:
        conn.rollback()
        return False, {}, str(e)
    finally:
        cur.close()
        conn.close()


def update_dia_0_desde_formulario(lote_nombre, datos_dia_0):
    """
    Sincroniza la información del Día 0 basándose en los parámetros provistos 
    desde el formulario general de configuración de la cabecera del lote.
    """
    if not lote_nombre or not datos_dia_0: return

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Función auxiliar para asegurar la extracción correcta de datos o asignar valores por defecto
        def obtener_valor_estricto(llave1, llave2, defecto=0.0):
            val = datos_dia_0.get(llave1) if datos_dia_0.get(llave1) is not None else datos_dia_0.get(llave2)
            if val is None or str(val).strip() == '':
                return defecto
            return to_float_safe(val)

        # Asignación y conversión de variables para el Día 0
        v_mort = int(obtener_valor_estricto('mortalidad', 'dia0_mortalidad', 0))
        v_sel = int(obtener_valor_estricto('sel', 'dia0_sel', 0))
        v_p_real = round(obtener_valor_estricto('peso_real', 'dia0_peso_real', 0.0), 2)
        v_10_menos = round(obtener_valor_estricto('unif_10_menos', 'dia0_unif_10_menos', 0.0), 1)
        v_unif = round(obtener_valor_estricto('porc_uniformidad', 'dia0_porc_uniformidad', 0.0), 2)
        v_10_mas = round(obtener_valor_estricto('unif_10_mas', 'dia0_unif_10_mas', 0.0), 1)
        v_cv = round(obtener_valor_estricto('coef_variacion', 'dia0_coef_variacion', 0.0), 2)
        
        v_c_kg = int(round(obtener_valor_estricto('consumo_kg', 'dia0_consumo_kg', 0.0)))
        v_k_acum = obtener_valor_estricto('cons_k_acum', 'dia0_cons_k_acum', 0.0)

        # Actualización del registro correspondiente al Día 0
        cur.execute("""
            UPDATE primera_semana SET
                mortalidad = %s, sel = %s, peso_real = %s,
                unif_10_menos = %s, porc_uniformidad = %s, unif_10_mas = %s,
                coef_variacion = %s, consumo_kg = %s, cons_k_acum = %s
            WHERE lote = %s AND semana = '0'
        """, (v_mort, v_sel, v_p_real, v_10_menos, v_unif, v_10_mas, v_cv, v_c_kg, v_k_acum, lote_nombre))
        
        # Recuperación de la población inicial para activar el recálculo
        cur.execute("SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
        cab_info = cur.fetchone()
        aves_iniciales = float(cab_info[0]) if cab_info and cab_info[0] else 10000.0
        
        recalcular_primera_semana_cascada_interna(lote_nombre, aves_iniciales, cur)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def recalcular_primera_semana_cascada_interna(lote_nombre, aves_iniciales, cur, id_reg=None):
    """
    Motor matemático central que procesa secuencialmente los registros de la primera semana.
    Calcula los saldos dinámicos de aves, la acumulación de mortalidades y los consumos reales
    diarios e históricos, garantizando la consistencia de los datos en toda la matriz.
    """
    cur.execute("""
        SELECT id, mortalidad, sel, consumo_kg, consumo_gr_a_tab 
        FROM primera_semana WHERE lote = %s ORDER BY id ASC
    """, (lote_nombre,))
    filas = cur.fetchall()

    # Variables acumuladoras para el procesamiento en cascada
    saldo_actual = aves_iniciales
    acum_mort = 0.0
    acum_kilos = 0.0
    acum_gr_tab = 0.0
    
    # REGLA 3 (MÁXIMA SEGURIDAD): Inicializamos la acumulación de gramos por ave en 0
    acum_gr_real_ave = 0.0 
    
    valores_update = []
    campos_reg_actualizado = {}

    for f in filas:
        # Manejo condicional dependiendo de si 'filas' retorna diccionarios o tuplas
        if isinstance(f, dict):
            f_id = f['id']
            m_dia = float(f['mortalidad'] or 0)
            s_dia = float(f['sel'] or 0)
            c_kg = float(f['consumo_kg'] or 0)
            c_tab = float(f['consumo_gr_a_tab'] or 0)
        else:
            f_id = f[0]
            m_dia = float(f[1] or 0)
            s_dia = float(f[2] or 0)
            c_kg = float(f[3] or 0)
            c_tab = float(f[4] or 0)

        # Progresión de acumulados
        acum_mort += m_dia
        acum_kilos += c_kg
        acum_gr_tab += c_tab

        # Cálculo dinámico del saldo de la población de aves
        saldo_actual -= (m_dia + s_dia)
        if saldo_actual < 0: saldo_actual = 0
        saldo_entero = int(saldo_actual)

        # Porcentajes de incidencia de mortalidad
        porc_mort_sem = round((m_dia / aves_iniciales) * 100, 2)
        porc_mort_acum = round((acum_mort / aves_iniciales) * 100, 2)
        
        # Consumo Real Diaria = E16 * 1000 / M16
        real_diaria = round((c_kg * 1000.0) / float(saldo_entero), 2) if saldo_entero > 0 else 0.0
        
        # REGLA 3: Suma consecutiva de la columna 'real_diaria' desde el día inicial
        acum_gr_real_ave += real_diaria
        c_gr_ac = round(acum_gr_real_ave, 2)
        
        c_k_acum = round(acum_kilos, 2)
        c_gr_tab_acum = int(round(acum_gr_tab))

        # Almacenamiento temporal de la tupla para la actualización por lotes
        valores_update.append((
            porc_mort_sem, porc_mort_acum, saldo_entero,
            real_diaria, c_k_acum, c_gr_tab_acum, c_gr_ac, f_id
        ))

        # Si se procesó una actualización en línea, captura los datos exactos modificados para el frontend
        if id_reg and int(f_id) == int(id_reg):
            campos_reg_actualizado = {
                'porc_mort_sem': porc_mort_sem,
                'porc_mort_acum': porc_mort_acum,
                'saldo_aves': saldo_entero,
                'consumo_gr_a_d': real_diaria,
                'cons_k_acum': c_k_acum,
                'cons_gr_ave_tab_acum': c_gr_tab_acum,
                'cons_gr_ave_ac': c_gr_ac
            }

    # Ejecución masiva de la actualización en cascada para todos los días
    if valores_update:
        cur.executemany("""
            UPDATE primera_semana 
            SET porc_mort_sem = %s, porc_mort_acum = %s, saldo_aves = %s,
                consumo_gr_a_d = %s, cons_k_acum = %s, cons_gr_ave_tab_acum = %s, cons_gr_ave_ac = %s
            WHERE id = %s
        """, valores_update)

    return valores_update, campos_reg_actualizado