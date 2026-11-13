# models/talento_humano/areas.py
"""
Catálogo de áreas (usado por el formulario de usuarios y de colaboradores).

Tabla propia `areas_catalogo` para no interferir con la tabla `areas` que ya
existía en la base (con otra estructura y otro listado).
"""
import psycopg2.extras

from models.base import get_db_connection


class Area:
    @staticmethod
    def listar(solo_activas=True):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = "SELECT id, nombre, activa FROM areas_catalogo"
                if solo_activas:
                    sql += " WHERE activa = TRUE"
                sql += " ORDER BY nombre"
                cur.execute(sql)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def nombres(solo_activas=True):
        return [a['nombre'] for a in Area.listar(solo_activas)]

    @staticmethod
    def crear(nombre):
        nombre = (nombre or '').strip()
        if not nombre:
            return None, 'El nombre del área no puede estar vacío.'
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM areas_catalogo WHERE LOWER(nombre) = LOWER(%s)",
                    (nombre,),
                )
                if cur.fetchone():
                    return None, 'Ya existe un área con ese nombre.'
                cur.execute(
                    "INSERT INTO areas_catalogo (nombre) VALUES (%s) RETURNING id",
                    (nombre,),
                )
                nuevo = cur.fetchone()[0]
            conn.commit()
            return nuevo, None
        finally:
            conn.close()

    @staticmethod
    def renombrar(area_id, nuevo_nombre):
        nuevo_nombre = (nuevo_nombre or '').strip()
        if not nuevo_nombre:
            return False, 'El nombre no puede estar vacío.'
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nombre FROM areas_catalogo WHERE id = %s", (area_id,))
                row = cur.fetchone()
                if not row:
                    return False, 'Área no encontrada.'
                viejo = row[0]
                if viejo == nuevo_nombre:
                    return True, None

                cur.execute(
                    "SELECT id FROM areas_catalogo WHERE LOWER(nombre) = LOWER(%s) AND id <> %s",
                    (nuevo_nombre, area_id),
                )
                if cur.fetchone():
                    return False, 'Ya existe un área con ese nombre.'

                cur.execute(
                    "UPDATE areas_catalogo SET nombre = %s, actualizado_en = CURRENT_TIMESTAMP WHERE id = %s",
                    (nuevo_nombre, area_id),
                )
                # Propagar el nuevo nombre a colaboradores y usuarios
                cur.execute("UPDATE colaboradores SET area = %s WHERE area = %s", (nuevo_nombre, viejo))
                cur.execute("UPDATE usuarios SET area = %s WHERE area = %s", (nuevo_nombre, viejo))
            conn.commit()
            return True, None
        finally:
            conn.close()

    @staticmethod
    def eliminar(area_id):
        """Elimina el área si no está en uso; si está en uso, la desactiva."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nombre FROM areas_catalogo WHERE id = %s", (area_id,))
                row = cur.fetchone()
                if not row:
                    return False, 'Área no encontrada.', None
                nombre = row[0]

                cur.execute(
                    "SELECT COUNT(*) FROM colaboradores WHERE area = %s AND eliminado_en IS NULL",
                    (nombre,),
                )
                en_colab = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM usuarios WHERE area = %s", (nombre,))
                en_usuarios = cur.fetchone()[0]

                if en_colab or en_usuarios:
                    cur.execute(
                        "UPDATE areas_catalogo SET activa = FALSE, actualizado_en = CURRENT_TIMESTAMP WHERE id = %s",
                        (area_id,),
                    )
                    accion = 'desactivada'
                else:
                    cur.execute("DELETE FROM areas_catalogo WHERE id = %s", (area_id,))
                    accion = 'eliminada'
            conn.commit()
            return True, None, accion
        finally:
            conn.close()
