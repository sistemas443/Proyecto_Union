# models/lotes/model.py
import psycopg2.extras
from models.base import get_db_connection

def fetch_lotes_distintos():
    """
    Obtiene una lista limpia y única con los nombres de todos los lotes registrados.
    Ideal para alimentar listas desplegables y evitar nombres duplicados o vacíos.
    """
    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Filtramos para que no traiga lotes nulos ni nombres conformados solo por espacios
        cur.execute("SELECT DISTINCT lote FROM cabecera_lotes WHERE lote IS NOT NULL AND TRIM(lote) != '' ORDER BY lote")
        return [r['lote'] for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def fetch_todos_los_lotes():
    """
    Extrae toda la información de la cabecera de todos los lotes creados.
    Se ordenan de forma descendente (DESC) para ver siempre los más recientes primero.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT * FROM cabecera_lotes ORDER BY id DESC")
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def check_lote_exists(lote_nombre):
    """
    Valida si un nombre de lote ya está ocupado en el sistema.
    Retorna True si existe, o False si está disponible.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
        # Si fetchone() trae algo, no es None, por lo tanto existe (True)
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def insert_lote(datos, lote_nombre, parse_empty):
    """
    Guarda un lote completamente nuevo en la base de datos.
    Limpia los valores vacíos con 'parse_empty' y retorna el ID que le asignó la BD.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Usamos RETURNING id para obtener inmediatamente el número de registro creado
        cur.execute("""
            INSERT INTO cabecera_lotes (
                lote, cliente, ciudad, clima, responsable_tecnico, nutricionista, granja_lev, fecha_recepcion, no_pollitas_recibidas, variedad, peso, 
                unidad_peso, uniformidad, coeficiente_variacion, granja_prod, fecha_encasetamiento, no_aves_encasetadas, tipo_galpon, marca_galpon, unidad_medida, validacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, True) RETURNING id
        """, (
            lote_nombre, parse_empty(datos.get('cliente')), parse_empty(datos.get('ciudad')), parse_empty(datos.get('clima')), parse_empty(datos.get('responsable_tecnico')), parse_empty(datos.get('nutricionista')),
            parse_empty(datos.get('granja_lev')), parse_empty(datos.get('fecha_recepcion')), parse_empty(datos.get('no_pollitas_recibidas')), parse_empty(datos.get('variedad')), parse_empty(datos.get('peso')), parse_empty(datos.get('unidad_peso')),
            parse_empty(datos.get('uniformidad')), parse_empty(datos.get('coeficiente_variacion')), parse_empty(datos.get('granja_prod')), parse_empty(datos.get('fecha_encasetamiento')), parse_empty(datos.get('no_aves_encasetadas')), parse_empty(datos.get('tipo_galpon')),
            parse_empty(datos.get('marca_galpon')), parse_empty(datos.get('unidad_medida'))
        ))
        id_lote = cur.fetchone()[0]
        conn.commit()
        return id_lote
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def update_lote(id_lote, datos, parse_empty):
    """
    Modifica la información de la cabecera de un lote existente.
    Busca por el id_lote y sobreescribe todos los campos con los nuevos datos.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE cabecera_lotes SET 
                lote = %s, cliente = %s, ciudad = %s, clima = %s, responsable_tecnico = %s, nutricionista = %s, granja_lev = %s, 
                fecha_recepcion = %s, no_pollitas_recibidas = %s, variedad = %s, peso = %s, unidad_peso = %s, uniformidad = %s, 
                coeficiente_variacion = %s, granja_prod = %s, fecha_encasetamiento = %s, no_aves_encasetadas = %s, tipo_galpon = %s, marca_galpon = %s, 
                unidad_medida = %s, validacion = True
            WHERE id = %s
        """, (
            parse_empty(datos.get('lote')), parse_empty(datos.get('cliente')), parse_empty(datos.get('ciudad')), parse_empty(datos.get('clima')), parse_empty(datos.get('responsable_tecnico')), parse_empty(datos.get('nutricionista')),
            parse_empty(datos.get('granja_lev')), parse_empty(datos.get('fecha_recepcion')), parse_empty(datos.get('no_pollitas_recibidas')), parse_empty(datos.get('variedad')), parse_empty(datos.get('peso')), parse_empty(datos.get('unidad_peso')),
            parse_empty(datos.get('uniformidad')), parse_empty(datos.get('coeficiente_variacion')), parse_empty(datos.get('granja_prod')), parse_empty(datos.get('fecha_encasetamiento')), parse_empty(datos.get('no_aves_encasetadas')), parse_empty(datos.get('tipo_galpon')),
            parse_empty(datos.get('marca_galpon')), parse_empty(datos.get('unidad_medida')), id_lote
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def delete_lote(id_lote):
    """
    Elimina un lote y realiza un borrado en cascada profundo de todo su historial.
    Limpia los datos en primera_semana, data_diario, bd_vargas y finalmente la cabecera.
    """
    from models.base import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Primero, obtenemos el nombre del lote porque algunas tablas usan el nombre y otras el ID
        cur.execute("SELECT lote FROM cabecera_lotes WHERE id = %s", (id_lote,))
        resultado = cur.fetchone()
        
        if not resultado:
            return False # El lote ya no existe
            
        lote_nombre = resultado[0]

        print(f"🗑️ [BORRADO PROFUNDO] Iniciando eliminación total del lote: {lote_nombre}")

        # 2. Destruimos los registros en TODAS las tablas secundarias (Cascada manual)
        cur.execute("DELETE FROM primera_semana WHERE id_lote = %s", (id_lote,))
        cur.execute("DELETE FROM data_diario WHERE id_lote = %s OR lote = %s", (id_lote, lote_nombre))
        cur.execute("DELETE FROM bd_vargas WHERE id_lote = %s", (id_lote,))
        
        # Si tienes tabla de clasificación, descomenta la siguiente línea:
        # cur.execute("DELETE FROM tabla_clasificacion WHERE lote = %s", (lote_nombre,))

        # 3. Finalmente, destruimos el lote principal de la cabecera
        cur.execute("DELETE FROM cabecera_lotes WHERE id = %s", (id_lote,))
        
        conn.commit()
        print(f"✅ [ÉXITO] Lote {lote_nombre} y todo su historial fueron eliminados de la faz de la base de datos.")
        return True

    except Exception as e:
        conn.rollback()
        import traceback
        print(f"❌ [ERROR AL BORRAR LOTE]: {e}")
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()


def fetch_opciones_dinamicas():
    """
    Extrae las opciones únicas digitadas históricamente por los usuarios en columnas de texto.
    Se utiliza para alimentar autocompletados o menús desplegables sugeridos en los formularios.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    opciones = {}
    
    # Lista de columnas de las cuales queremos extraer el historial de respuestas
    columnas = ['cliente', 'ciudad', 'clima', 'responsable_tecnico', 'nutricionista', 'granja_lev', 'variedad', 'granja_prod', 'tipo_galpon', 'marca_galpon']
    
    try:
        for col in columnas:
            # Buscamos valores distintos que no estén vacíos
            cur.execute(f'SELECT DISTINCT "{col}" FROM cabecera_lotes WHERE "{col}" IS NOT NULL AND TRIM("{col}"::text) != \'\' ORDER BY "{col}"')
            opciones[col] = [row[0] for row in cur.fetchall()]
        return opciones
    except:
        conn.rollback()
        # Si algo falla, devolvemos un diccionario con listas vacías para no romper la pantalla
        return {col: [] for col in columnas}
    finally:
        cur.close()
        conn.close()