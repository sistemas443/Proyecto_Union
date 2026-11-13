# models/primera_semana/activa.py
"""Selección de la tabla activa de Primera Semana por lote."""
from models.base import get_db_connection
from models.primera_semana import dia2

TABLAS_VALIDAS = {'dia1', 'dia2'}


def get_tabla_activa(lote_nombre):
    """Devuelve 'dia1' o 'dia2' según la selección guardada del lote."""
    if not lote_nombre:
        return 'dia1'
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COALESCE(tabla_primera_activa, 'dia1') FROM cabecera_lotes WHERE lote = %s",
            (lote_nombre,),
        )
        fila = cur.fetchone()
        return fila[0] if fila and fila[0] in TABLAS_VALIDAS else 'dia1'
    finally:
        cur.close()
        conn.close()


def set_tabla_activa(lote_nombre, tabla, usuario_id=None, usuario_nombre=None):
    """Guarda qué tabla de Primera Semana debe usar el resto del sistema."""
    if not lote_nombre:
        return False, "Lote inválido."
    if tabla not in TABLAS_VALIDAS:
        return False, "Tabla inválida."

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote_nombre,))
        fila = cur.fetchone()
        if not fila:
            return False, "El lote no existe."
        id_lote = fila[0]

        if tabla == 'dia2' and dia2.count_dia2(lote_nombre) == 0:
            return False, "El lote no tiene la tabla del Día 2."

        cur.execute(
            "UPDATE cabecera_lotes SET tabla_primera_activa = %s WHERE id = %s",
            (tabla, id_lote),
        )

        from models.auditoria.services import registrar_cambio
        registrar_cambio(
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre or 'Desconocido',
            tabla='cabecera_lotes',
            id_registro=id_lote,
            campo='tabla_primera_activa',
            valor_anterior=None,
            valor_nuevo=tabla,
            accion='UPDATE',
            cursor=cur,
        )

        conn.commit()
        return True, "Tabla activa actualizada."
    except Exception as e:
        conn.rollback()
        print(f"[ERROR TABLA ACTIVA]: {e}")
        return False, str(e)
    finally:
        cur.close()
        conn.close()
