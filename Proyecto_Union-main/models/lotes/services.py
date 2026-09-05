# models/lotes/services.py
from models.base import parse_empty
from models.lotes import model

# Importamos los gatillos de las otras tablas
from models.diario.services import generar_estructura_diario
from models.clasificacion.services import generar_estructura_clasificacion

# 1. Producción (Carpeta antigua)
from models.semanal.services import generar_estructura_semanal_unificada

# 2. Levante (Nuevas carpetas independientes)
from models.semanal_levante.services import generar_estructura_semanal_levante

# 3. ¡LA NUEVA DIRECCIÓN DE PRIMERA SEMANA!
from models.primera_semana.services import generar_estructura_primera_semana, update_dia_0_desde_formulario

def get_lotes_distintos():
    """
    Llama al modelo para obtener una lista única de los nombres de los lotes.
    Actúa como un puente directo entre la vista (el controlador) y la base de datos.
    """
    return model.fetch_lotes_distintos()

def get_todos_los_lotes():
    """
    Obtiene la lista completa de lotes y realiza una "inyección" inteligente de datos.
    Busca específicamente la fila del "Día 0" en la tabla 'primera_semana' para cada lote
    y fusiona esos valores al diccionario principal. 
    Uso común: Es fundamental para que, al presionar el botón de "Editar", 
    los campos del Día 0 en el formulario web aparezcan ya llenos.
    """
    lotes = model.fetch_todos_los_lotes()
    
    from models.base import get_db_connection
    import psycopg2.extras
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        for lote in lotes:
            lote_nombre = lote.get('lote')
            if lote_nombre:
                # Buscamos exclusivamente la fila de la semana '0' para este lote
                cur.execute("""
                    SELECT 
                        mortalidad AS dia0_mortalidad, 
                        sel AS dia0_sel,
                        consumo_kg AS dia0_consumo_kg, 
                        cons_k_acum AS dia0_cons_k_acum,
                        peso_tabla AS dia0_peso_tabla, 
                        peso_real AS dia0_peso_real,
                        unif_10_menos AS dia0_unif_10_menos, 
                        porc_uniformidad AS dia0_porc_uniformidad,
                        unif_10_mas AS dia0_unif_10_mas, 
                        coef_variacion AS dia0_coef_variacion
                    FROM primera_semana 
                    WHERE lote = %s AND semana = '0' LIMIT 1
                """, (lote_nombre,))
                
                dia0_data = cur.fetchone()
                
                if dia0_data:
                    # Fusionamos los datos del Día 0 dentro del diccionario del lote actual
                    lote.update(dict(dia0_data))
    except Exception as e:
        print(f"[ERROR FETCH DÍA 0 PARA EDICIÓN]: {e}")
    finally:
        cur.close()
        conn.close()
        
    return lotes

def guardar_nuevo_lote(datos):
    """
    Orquesta la creación de un lote completamente nuevo en el sistema.
    1. Valida que el nombre no esté duplicado.
    2. Guarda la información en la tabla principal (Cabecera).
    3. Dispara todos los "gatillos" para generar las plantillas vacías en las tablas de diario, semanal, etc.
    """
    lote_nombre = parse_empty(datos.get('lote'))
    # Verificación de seguridad para evitar duplicados
    if model.check_lote_exists(lote_nombre):
        return False, f"Ya existe un lote registrado como '{lote_nombre}'."

    try:
        # 1. Guardar en BD (Cabecera) y obtener el ID recién creado
        id_lote = model.insert_lote(datos, lote_nombre, parse_empty)
        
        # 2. Empaquetamos los datos del Día 0 recibidos del formulario HTML
        # Esto sirve para enviarlos directamente a la tabla de Primera Semana
        datos_dia_0 = {
            'sel': datos.get('dia0_sel'),
            'peso_tabla': datos.get('dia0_peso_tabla'),
            'peso_real': datos.get('dia0_peso_real'),
            'unif_10_menos': datos.get('dia0_unif_10_menos'),
            'porc_uniformidad': datos.get('dia0_porc_uniformidad'),
            'unif_10_mas': datos.get('dia0_unif_10_mas'),
            'coef_variacion': datos.get('dia0_coef_variacion'),
            'mortalidad': datos.get('dia0_mortalidad'),
            'consumo_kg': datos.get('dia0_consumo_kg'),
            'cons_k_acum': datos.get('dia0_cons_k_acum'),
            'consumo_gr_a_d': datos.get('dia0_consumo_gr_a_d')
        }
        
        # 3. GATILLOS: Crear los esqueletos de las tablas dependientes
        # Al ejecutar esto, el lote nace con todas sus filas vacías preparadas
        generar_estructura_diario(lote_nombre, id_lote, datos.get('fecha_recepcion'))
        generar_estructura_semanal_unificada(lote_nombre, datos.get('fecha_recepcion'), id_lote)
        generar_estructura_clasificacion(lote_nombre, id_lote)
        
        # Gatillo Nuevo: Primera Semana con los datos inyectados del Día 0
        generar_estructura_primera_semana(lote_nombre, datos.get('fecha_recepcion'), datos_dia_0=datos_dia_0)
        
        # Gatillo Nuevo: Estructura exclusiva de Levante
        generar_estructura_semanal_levante(lote_nombre, datos.get('fecha_recepcion'), id_lote)

        return True, "Lote creado exitosamente"
    except Exception as e:
        return False, str(e)


def actualizar_lote(id_lote, datos):
    """
    Coordina la modificación de un lote que ya existe en el sistema.
    INCLUYE RENOMBRAMIENTO MASIVO: Si el nombre del lote cambia, actualiza todas las tablas satélite.
    Sobreescribe la cabecera y sincroniza cambios del "Día 0".
    """
    try:
        # Importamos la herramienta para conectarnos directo a la base de datos
        from models.base import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # PASO 1: Descubrimos cómo se llamaba el lote antes de que el usuario lo editara
        cur.execute("SELECT lote FROM cabecera_lotes WHERE id = %s", (id_lote,))
        resultado = cur.fetchone()
        
        if not resultado:
            return False, "El lote que intentas editar ya no existe en la base de datos."
            
        lote_viejo = resultado[0] # Guardamos el nombre antiguo
        lote_nuevo = parse_empty(datos.get('lote')) # Extraemos el nombre que viene del formulario
        
        # PASO 2: Verificamos si realmente hubo un cambio de nombre
        if lote_nuevo and lote_viejo != lote_nuevo:
            
            # Medida de seguridad: Validar que el nuevo nombre no se lo hayan puesto ya a otro lote distinto
            cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote_nuevo,))
            if cur.fetchone():
                return False, f"No puedes renombrarlo a '{lote_nuevo}' porque ya existe otro lote con ese nombre."
            
            # --- INICIO DEL RENOMBRAMIENTO EN CASCADA ---
            # Le cambiamos el nombre en la tabla principal (Cabecera)
            cur.execute("UPDATE cabecera_lotes SET lote = %s WHERE id = %s", (lote_nuevo, id_lote))
            
            # Actualizamos las tablas que guardan el nombre como texto para no perder el enlace de datos
            cur.execute("UPDATE primera_semana SET lote = %s WHERE lote = %s", (lote_nuevo, lote_viejo))
            
            # Actualizamos las tablas asociadas (si tienen columna 'lote' además del id_lote)
            cur.execute("UPDATE data_diario SET lote = %s WHERE id_lote = %s", (lote_nuevo, id_lote))
            
            # --- LÍNEA CORREGIDA CON LA TABLA CORRECTA ---
            cur.execute("UPDATE bd_vargas SET lote = %s WHERE id_lote = %s", (lote_nuevo, id_lote))
            
            cur.execute("UPDATE semanal_levante SET lote = %s WHERE id_lote = %s", (lote_nuevo, id_lote))
            cur.execute("UPDATE clasificacion_produccion SET lote = %s WHERE id_lote = %s", (lote_nuevo, id_lote))
            # --- FIN DEL RENOMBRAMIENTO EN CASCADA ---
            
            # Confirmamos y guardamos permanentemente este cambio en la BD
            conn.commit()
            
        # Cerramos los puentes a la base de datos por seguridad y rendimiento
        cur.close()
        conn.close()

        # PASO 3: Ejecutamos la actualización normal de los demás campos 
        # (Granjas, fechas, cantidades, etc.) usando el modelo habitual
        model.update_lote(id_lote, datos, parse_empty)
        
        # PASO 4: MAGIA FINAL - Mandamos los datos nuevos a la tabla Primera Semana (Día 0)
        if lote_nuevo:
            update_dia_0_desde_formulario(lote_nuevo, datos)
            
        return True, "Lote actualizado exitosamente"
        
    except Exception as e:
        return False, f"Ocurrió un error al actualizar: {str(e)}"

def borrar_lote(id_lote):
    """
    Puente que comunica la orden de borrar un lote al modelo.
    Desencadenará el borrado profundo (en cascada) de todas las tablas relacionadas.
    """
    return model.delete_lote(id_lote)

def get_opciones_dinamicas():
    """
    Llama al modelo para obtener el diccionario de autocompletados (ciudades, marcas, etc.).
    Sirve para enviar estos datos al HTML y facilitar la digitación del usuario.
    """
    return model.fetch_opciones_dinamicas()