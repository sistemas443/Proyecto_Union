# models/eventualidades/model.py
"""Acceso a datos de las eventualidades por lote."""

import psycopg2.extras

from models.base import get_db_connection
from models.cabecera.model import fetch_cabecera_by_lote


def fetch_id_lote(lote):
    cabecera = fetch_cabecera_by_lote(lote)
    return cabecera.get('id') if cabecera else None


def fetch_eventualidades(id_lote, ambito):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT e.id, e.semana, e.fecha, e.tipo_id, e.titulo, e.detalle,
                       e.impacto, e.creado_por_nombre, e.creado_en,
                       t.nombre AS tipo, t.color AS tipo_color
                FROM eventualidades_lote e
                LEFT JOIN tipos_eventualidad t ON t.id = e.tipo_id
                WHERE e.id_lote = %s AND e.ambito = %s AND e.eliminado_en IS NULL
                ORDER BY e.semana, e.creado_en
            """, (id_lote, ambito))
            return [dict(fila) for fila in cur.fetchall()]
    finally:
        conn.close()


def insert_eventualidad(datos):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO eventualidades_lote
                    (id_lote, lote, ambito, semana, fecha, tipo_id, titulo,
                     detalle, impacto, creado_por, creado_por_nombre)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                datos['id_lote'], datos['lote'], datos['ambito'], datos['semana'],
                datos.get('fecha'), datos.get('tipo_id'), datos['titulo'],
                datos.get('detalle'), datos.get('impacto'),
                datos.get('creado_por'), datos.get('creado_por_nombre'),
            ))
            id_evento = cur.fetchone()[0]
        conn.commit()
        return id_evento
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_eventualidad(id_evento):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT e.id, e.id_lote, e.lote, e.ambito, e.semana, e.titulo, e.eliminado_en
                FROM eventualidades_lote e WHERE e.id = %s
            """, (id_evento,))
            fila = cur.fetchone()
            return dict(fila) if fila else None
    finally:
        conn.close()


def actualizar_eventualidad(id_evento, datos):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE eventualidades_lote
                SET tipo_id = %s, titulo = %s, detalle = %s, impacto = %s,
                    fecha = COALESCE(%s, fecha),
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id = %s AND eliminado_en IS NULL
                RETURNING id
            """, (
                datos.get('tipo_id'), datos['titulo'], datos.get('detalle'),
                datos.get('impacto'), datos.get('fecha'), id_evento,
            ))
            fila = cur.fetchone()
        conn.commit()
        return fila[0] if fila else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def eliminar_eventualidad(id_evento, usuario_id=None):
    """Borrado lógico. Devuelve el id del lote o None si no existía."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE eventualidades_lote
                SET eliminado_en = CURRENT_TIMESTAMP, actualizado_en = CURRENT_TIMESTAMP
                WHERE id = %s AND eliminado_en IS NULL
                RETURNING id_lote
            """, (id_evento,))
            fila = cur.fetchone()
        conn.commit()
        return fila[0] if fila else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_tipos():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, nombre, color FROM tipos_eventualidad
                WHERE activo ORDER BY nombre
            """)
            return [dict(fila) for fila in cur.fetchall()]
    finally:
        conn.close()


def insert_tipo(nombre, color):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO tipos_eventualidad (nombre, color)
                VALUES (%s, %s)
                ON CONFLICT (nombre) DO UPDATE SET activo = TRUE
                RETURNING id, nombre, color
            """, (nombre, color))
            fila = dict(cur.fetchone())
        conn.commit()
        return fila
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
