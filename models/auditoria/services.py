# models/auditoria/services.py
from models.base import get_db_connection

def registrar_cambio(usuario_id, usuario_nombre, tabla, id_registro, 
                     campo, valor_anterior, valor_nuevo, accion, cursor):
    """
    Registra un cambio en auditoria_cambios usando el cursor existente
    para mantener la misma transacción. Usa SAVEPOINT para aislar fallos.
    """
    try:
        cursor.execute("SAVEPOINT sp_auditoria")
        cursor.execute("""
            INSERT INTO auditoria_cambios 
                (usuario_id, usuario_nombre, tabla, id_registro, campo, valor_anterior, valor_nuevo, accion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            usuario_id, 
            usuario_nombre, 
            tabla, 
            id_registro, 
            campo, 
            str(valor_anterior) if valor_anterior is not None else None,
            str(valor_nuevo) if valor_nuevo is not None else None,
            accion
        ))
        cursor.execute("RELEASE SAVEPOINT sp_auditoria")
    except Exception as e:
        print(f"[AUDITORÍA ERROR] No se pudo registrar el cambio: {e}")
        try:
            cursor.execute("ROLLBACK TO SAVEPOINT sp_auditoria")
        except Exception as e2:
            print(f"[AUDITORÍA ERROR CRÍTICO] {e2}")


def contar_historial():
    """Cuenta el total de registros en auditoría."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM auditoria_cambios")
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def obtener_historial(limite=100, offset=0):
    """
    Obtiene cambios registrados con paginación y JOIN condicional.
    
    Args:
        limite: Número máximo de registros a retornar
        offset: Número de registros a saltar (para paginación)
        
    Returns:
        Lista de tuplas con los cambios
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                a.id, a.usuario_id, a.usuario_nombre, a.fecha, a.tabla, 
                a.id_registro, a.campo, a.valor_anterior, a.valor_nuevo, a.accion,
                p.lote, p.semana
            FROM auditoria_cambios a
            LEFT JOIN primera_semana p 
                ON a.tabla = 'primera_semana' AND a.id_registro = p.id
            ORDER BY a.fecha DESC
            LIMIT %s OFFSET %s
        """, (limite, offset))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def obtener_historial_filtrado(filtros=None, limite=100, offset=0):
    """
    Obtiene cambios registrados con filtros y paginación.
    Los filtros de dropdown usan igualdad exacta (=).
    Solo 'campo' usa ILIKE para búsqueda de texto libre.
    """
    if filtros is None:
        filtros = {}
    
    condiciones = []
    parametros = []
    
    # Filtro por usuario (igualdad exacta por ID)
    if filtros.get('usuario'):
        condiciones.append("a.usuario_id = %s")
        parametros.append(filtros['usuario'])
    
    # Filtro por tabla (igualdad exacta)
    if filtros.get('tabla'):
        condiciones.append("a.tabla = %s")
        parametros.append(filtros['tabla'])
    
    # Filtro por acción (igualdad exacta)
    if filtros.get('accion'):
        condiciones.append("a.accion = %s")
        parametros.append(filtros['accion'])
    
    # Filtro por campo (ILIKE para texto libre)
    if filtros.get('campo'):
        condiciones.append("a.campo ILIKE %s")
        parametros.append(f"%{filtros['campo']}%")
    
    # Filtro por fecha desde
    if filtros.get('fecha_desde'):
        condiciones.append("a.fecha >= %s")
        parametros.append(filtros['fecha_desde'])
    
    # Filtro por fecha hasta
    if filtros.get('fecha_hasta'):
        condiciones.append("a.fecha <= %s")
        parametros.append(filtros['fecha_hasta'] + " 23:59:59")
    
    # Filtro por lote (igualdad exacta)
    if filtros.get('lote'):
        condiciones.append("p.lote = %s")
        parametros.append(filtros['lote'])
    
    where_clause = " AND ".join(condiciones) if condiciones else "1=1"
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT 
                a.id, a.usuario_id, a.usuario_nombre, a.fecha, a.tabla, 
                a.id_registro, a.campo, a.valor_anterior, a.valor_nuevo, a.accion,
                p.lote, p.semana
            FROM auditoria_cambios a
            LEFT JOIN primera_semana p 
                ON a.tabla = 'primera_semana' AND a.id_registro = p.id
            WHERE {where_clause}
            ORDER BY a.fecha DESC
            LIMIT %s OFFSET %s
        """, (*parametros, limite, offset))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def contar_historial_filtrado(filtros=None):
    """Cuenta registros según filtros aplicados."""
    if filtros is None:
        filtros = {}
    
    condiciones = []
    parametros = []
    
    if filtros.get('usuario'):
        condiciones.append("a.usuario_id = %s")
        parametros.append(filtros['usuario'])
    if filtros.get('tabla'):
        condiciones.append("a.tabla = %s")
        parametros.append(filtros['tabla'])
    if filtros.get('accion'):
        condiciones.append("a.accion = %s")
        parametros.append(filtros['accion'])
    if filtros.get('campo'):
        condiciones.append("a.campo ILIKE %s")
        parametros.append(f"%{filtros['campo']}%")
    if filtros.get('fecha_desde'):
        condiciones.append("a.fecha >= %s")
        parametros.append(filtros['fecha_desde'])
    if filtros.get('fecha_hasta'):
        condiciones.append("a.fecha <= %s")
        parametros.append(filtros['fecha_hasta'] + " 23:59:59")
    if filtros.get('lote'):
        condiciones.append("p.lote = %s")
        parametros.append(filtros['lote'])
    
    where_clause = " AND ".join(condiciones) if condiciones else "1=1"
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT COUNT(*) 
            FROM auditoria_cambios a
            LEFT JOIN primera_semana p 
                ON a.tabla = 'primera_semana' AND a.id_registro = p.id
            WHERE {where_clause}
        """, tuple(parametros))
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def obtener_opciones_filtros():
    """
    Obtiene los valores únicos para los dropdowns de filtros.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Usuarios únicos
        cur.execute("""
            SELECT DISTINCT usuario_id, usuario_nombre 
            FROM auditoria_cambios 
            ORDER BY usuario_nombre
        """)
        usuarios = [{'id': row[0], 'nombre': row[1]} for row in cur.fetchall()]
        
        # Tablas únicas
        cur.execute("SELECT DISTINCT tabla FROM auditoria_cambios ORDER BY tabla")
        tablas = [row[0] for row in cur.fetchall()]
        
        # Acciones únicas
        cur.execute("SELECT DISTINCT accion FROM auditoria_cambios ORDER BY accion")
        acciones = [row[0] for row in cur.fetchall()]
        
        # Campos únicos
        cur.execute("SELECT DISTINCT campo FROM auditoria_cambios WHERE campo IS NOT NULL ORDER BY campo")
        campos = [row[0] for row in cur.fetchall()]
        
        # Lotes únicos (del JOIN con primera_semana)
        cur.execute("""
            SELECT DISTINCT p.lote 
            FROM auditoria_cambios a
            JOIN primera_semana p ON a.tabla = 'primera_semana' AND a.id_registro = p.id
            ORDER BY p.lote
        """)
        lotes = [row[0] for row in cur.fetchall()]
        
        return {
            'usuarios': usuarios,
            'tablas': tablas,
            'acciones': acciones,
            'campos': campos,
            'lotes': lotes
        }
    finally:
        cur.close()
        conn.close()


def obtener_campos_por_tabla(tabla):
    """Obtiene los campos únicos de una tabla específica."""
    if not tabla:
        return []
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT campo 
            FROM auditoria_cambios 
            WHERE tabla = %s AND campo IS NOT NULL 
            ORDER BY campo
        """, (tabla,))
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
