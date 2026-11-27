"""Iconos y titulos personalizados de las tarjetas de Consolidados."""

import psycopg2
import psycopg2.extras

from models.base import get_db_connection


def listar_tarjetas():
    """Metadata de las tarjetas personalizadas: {clave: {...}}."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT clave, titulo, icono_mime, actualizado_en
            FROM consolidados_tarjetas
            """
        )
        return {fila['clave']: dict(fila) for fila in cur.fetchall()}
    except Exception as e:
        print(f"[CONSOLIDADOS TARJETAS] No se pudo leer el catalogo: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


def listar_iconos():
    """Bytes de las miniaturas/originales: {clave: {...}}."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT clave, icono_thumb, icono_thumb_mime,
                   icono_data, icono_mime, actualizado_en
            FROM consolidados_tarjetas
            WHERE icono_thumb IS NOT NULL OR icono_data IS NOT NULL
            """
        )
        return {fila['clave']: dict(fila) for fila in cur.fetchall()}
    except Exception as e:
        print(f"[CONSOLIDADOS TARJETAS] No se pudieron leer los iconos: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


def obtener_icono(clave):
    """Devuelve la fila con bytea/mime/nombre/actualizado_en o None."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT icono_data, icono_mime, icono_nombre,
                   icono_thumb, icono_thumb_mime, actualizado_en
            FROM consolidados_tarjetas
            WHERE clave = %s
            """,
            (clave,),
        )
        fila = cur.fetchone()
        return dict(fila) if fila else None
    except Exception as e:
        print(f"[CONSOLIDADOS TARJETAS] No se pudo leer el icono: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def guardar_tarjeta(clave, titulo=None, icono_data=None, icono_mime=None,
                    icono_nombre=None, icono_thumb=None, icono_thumb_mime=None,
                    usuario_id=None):
    """Guarda titulo y/o icono. Si no llega icono, conserva el actual."""
    titulo = (str(titulo).strip()[:120] if titulo else None) or None
    binario = psycopg2.Binary(icono_data) if icono_data else None
    thumb = psycopg2.Binary(icono_thumb) if icono_thumb else None

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO consolidados_tarjetas
                (clave, titulo, icono_data, icono_mime, icono_nombre,
                 icono_thumb, icono_thumb_mime, actualizado_en, actualizado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (clave) DO UPDATE SET
                titulo = EXCLUDED.titulo,
                icono_data = COALESCE(EXCLUDED.icono_data,
                                      consolidados_tarjetas.icono_data),
                icono_mime = COALESCE(EXCLUDED.icono_mime,
                                      consolidados_tarjetas.icono_mime),
                icono_nombre = COALESCE(EXCLUDED.icono_nombre,
                                        consolidados_tarjetas.icono_nombre),
                icono_thumb = COALESCE(EXCLUDED.icono_thumb,
                                       consolidados_tarjetas.icono_thumb),
                icono_thumb_mime = COALESCE(EXCLUDED.icono_thumb_mime,
                                            consolidados_tarjetas.icono_thumb_mime),
                actualizado_en = now(),
                actualizado_por = EXCLUDED.actualizado_por
            RETURNING clave, titulo, icono_mime, icono_thumb_mime, actualizado_en
            """,
            (clave, titulo, binario, icono_mime, icono_nombre,
             thumb, icono_thumb_mime, usuario_id),
        )
        fila = dict(cur.fetchone())
        conn.commit()
        return fila
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def quitar_icono(clave):
    """Elimina solo el icono. Si la tarjeta no tiene titulo propio, borra la fila."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            UPDATE consolidados_tarjetas
            SET icono_data = NULL, icono_mime = NULL, icono_nombre = NULL,
                icono_thumb = NULL, icono_thumb_mime = NULL,
                actualizado_en = now()
            WHERE clave = %s
            RETURNING clave, titulo, actualizado_en
            """,
            (clave,),
        )
        fila = cur.fetchone()
        cur.execute(
            """
            DELETE FROM consolidados_tarjetas
            WHERE clave = %s AND titulo IS NULL
            """,
            (clave,),
        )
        conn.commit()
        return dict(fila) if fila else None
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
