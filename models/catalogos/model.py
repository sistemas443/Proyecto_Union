"""SQL crudo de los catálogos con foto. El nombre de tabla SIEMPRE llega
validado desde services.py (whitelist de schemas.py)."""
from models.base import get_db_connection


def listar(tabla: str) -> list:
    """Lista los valores ACTIVOS del catálogo (id, nombre, foto)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT id, nombre, foto FROM {tabla}
            WHERE activo = TRUE ORDER BY nombre ASC
        """)
        return [{'id': r[0], 'nombre': r[1], 'foto': r[2]} for r in cur.fetchall()]
    except Exception as e:
        # Si la tabla aún no existe (SQL no corrido), la vista no debe romperse
        print(f"[ERROR LISTANDO {tabla}]: {e}")
        conn.rollback()
        return []
    finally:
        cur.close()
        conn.close()


def buscar_por_nombre(tabla: str, nombre: str):
    """Devuelve {id, nombre, foto, activo} si existe (activo o no), o None."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id, nombre, foto, activo FROM {tabla} WHERE nombre = %s", (nombre,))
        r = cur.fetchone()
        return {'id': r[0], 'nombre': r[1], 'foto': r[2], 'activo': r[3]} if r else None
    finally:
        cur.close()
        conn.close()


def buscar_por_id(tabla: str, id_item: int):
    """Devuelve {id, nombre, foto, activo} por id, o None."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id, nombre, foto, activo FROM {tabla} WHERE id = %s", (id_item,))
        r = cur.fetchone()
        return {'id': r[0], 'nombre': r[1], 'foto': r[2], 'activo': r[3]} if r else None
    finally:
        cur.close()
        conn.close()


def insertar(tabla: str, nombre: str, foto: str) -> int:
    """Inserta un valor nuevo y devuelve su id."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"INSERT INTO {tabla} (nombre, foto) VALUES (%s, %s) RETURNING id",
                    (nombre, foto))
        id_nuevo = cur.fetchone()[0]
        conn.commit()
        return id_nuevo
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def reactivar(tabla: str, id_item: int, nombre: str, foto: str) -> None:
    """Reactiva un valor borrado lógicamente (mismo nombre, foto nueva)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            UPDATE {tabla} SET nombre = %s, foto = %s, activo = TRUE WHERE id = %s
        """, (nombre, foto, id_item))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def actualizar(tabla: str, id_item: int, nombre: str, foto: str) -> None:
    """Actualiza nombre y foto de un valor existente."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE {tabla} SET nombre = %s, foto = %s WHERE id = %s",
                    (nombre, foto, id_item))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def borrar_logico(tabla: str, id_item: int) -> None:
    """Borrado LÓGICO: el nombre queda en BD para los lotes viejos."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE {tabla} SET activo = FALSE WHERE id = %s", (id_item,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
