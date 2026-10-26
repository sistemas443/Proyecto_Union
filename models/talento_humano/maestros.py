# models/talento_humano/maestros.py
"""
Catálogos maestros para Talento Humano: EPS, ARL, Fondos, etc.
Patrón similar a models/planta_alimentos/maestros.py
"""
import psycopg2
import psycopg2.extras

from models.base import get_db_connection, parse_empty


class EPS:
    """Catálogo de EPS (Entidades Promotoras de Salud)"""

    @staticmethod
    def get_all(activas_solo=True):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = "SELECT id, nombre, codigo, activa FROM eps"
                if activas_solo:
                    sql += " WHERE activa = TRUE"
                sql += " ORDER BY nombre"
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(eps_id):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre, codigo, activa FROM eps WHERE id = %s", (eps_id,))
                return cur.fetchone()
        finally:
            conn.close()

    @staticmethod
    def create(nombre, codigo=None, activa=True):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO eps (nombre, codigo, activa) VALUES (%s, %s, %s) RETURNING id",
                    (nombre.strip().upper(), codigo.strip().upper() if codigo else None, activa)
                )
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe una EPS con ese nombre o código")
            raise
        finally:
            conn.close()

    @staticmethod
    def update(eps_id, nombre, codigo=None, activa=True):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE eps SET nombre = %s, codigo = %s, activa = %s WHERE id = %s",
                    (nombre.strip().upper(), codigo.strip().upper() if codigo else None, activa, eps_id)
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe una EPS con ese nombre o código")
            raise
        finally:
            conn.close()

    @staticmethod
    def toggle_activa(eps_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE eps SET activa = NOT activa WHERE id = %s RETURNING activa", (eps_id,))
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
        finally:
            conn.close()


class ARL:
    """Catálogo de ARL (Administradoras de Riesgos Laborales)"""

    @staticmethod
    def get_all(activas_solo=True):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = "SELECT id, nombre, codigo, activa FROM arl"
                if activas_solo:
                    sql += " WHERE activa = TRUE"
                sql += " ORDER BY nombre"
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(arl_id):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre, codigo, activa FROM arl WHERE id = %s", (arl_id,))
                return cur.fetchone()
        finally:
            conn.close()

    @staticmethod
    def create(nombre, codigo=None, activa=True):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO arl (nombre, codigo, activa) VALUES (%s, %s, %s) RETURNING id",
                    (nombre.strip().upper(), codigo.strip().upper() if codigo else None, activa)
                )
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe una ARL con ese nombre o código")
            raise
        finally:
            conn.close()

    @staticmethod
    def update(arl_id, nombre, codigo=None, activa=True):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE arl SET nombre = %s, codigo = %s, activa = %s WHERE id = %s",
                    (nombre.strip().upper(), codigo.strip().upper() if codigo else None, activa, arl_id)
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe una ARL con ese nombre o código")
            raise
        finally:
            conn.close()

    @staticmethod
    def toggle_activa(arl_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE arl SET activa = NOT activa WHERE id = %s RETURNING activa", (arl_id,))
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
        finally:
            conn.close()


class Talla:
    """Catálogos de tallas EPP: camisa, pantalón, botas y casco.

    Cada tipo tiene su propia tabla. El nombre de la tabla NUNCA se toma
    del usuario: se resuelve contra este mapa (lista blanca).
    """

    TABLAS = {
        'camisa': 'tallas_camisa',
        'pantalon': 'tallas_pantalon',
        'botas': 'tallas_botas',
        'casco': 'tallas_casco',
    }

    ETIQUETAS = {
        'camisa': 'Camisa',
        'pantalon': 'Pantalón',
        'botas': 'Botas',
        'casco': 'Casco',
    }

    @classmethod
    def _tabla(cls, tipo):
        tabla = cls.TABLAS.get((tipo or '').strip().lower())
        if not tabla:
            raise ValueError("Tipo de talla no válido")
        return tabla

    @classmethod
    def get_all(cls, tipo, activas_solo=True):
        tabla = cls._tabla(tipo)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = f"SELECT id, nombre, codigo, orden, activa FROM {tabla}"
                if activas_solo:
                    sql += " WHERE activa = TRUE"
                sql += " ORDER BY orden, nombre"
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    @classmethod
    def get_by_id(cls, tipo, talla_id):
        tabla = cls._tabla(tipo)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    f"SELECT id, nombre, codigo, orden, activa FROM {tabla} WHERE id = %s",
                    (talla_id,)
                )
                return cur.fetchone()
        finally:
            conn.close()

    @classmethod
    def create(cls, tipo, nombre, codigo=None, activa=True):
        tabla = cls._tabla(tipo)
        etiqueta = cls.ETIQUETAS.get(tipo, 'talla')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COALESCE(MAX(orden), 0) + 1 FROM {tabla}")
                orden = cur.fetchone()[0]
                cur.execute(
                    f"""INSERT INTO {tabla} (nombre, codigo, orden, activa)
                        VALUES (%s, %s, %s, %s) RETURNING id""",
                    (nombre.strip().upper(),
                     codigo.strip().upper() if codigo else None,
                     orden, activa)
                )
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe una talla de {etiqueta} con ese nombre o código")
            raise
        finally:
            conn.close()

    @classmethod
    def update(cls, tipo, talla_id, nombre, codigo=None, activa=True):
        tabla = cls._tabla(tipo)
        etiqueta = cls.ETIQUETAS.get(tipo, 'talla')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {tabla} SET nombre = %s, codigo = %s, activa = %s
                        WHERE id = %s""",
                    (nombre.strip().upper(),
                     codigo.strip().upper() if codigo else None,
                     activa, talla_id)
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe una talla de {etiqueta} con ese nombre o código")
            raise
        finally:
            conn.close()

    @classmethod
    def toggle_activa(cls, tipo, talla_id):
        tabla = cls._tabla(tipo)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {tabla} SET activa = NOT activa WHERE id = %s RETURNING activa",
                    (talla_id,)
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
        finally:
            conn.close()


class Catalogo:
    """Catálogos de texto libre de Talento Humano.

    Cada campo del formulario tiene su propia tabla. El nombre de la tabla
    NUNCA se toma del usuario: se resuelve contra este mapa (lista blanca),
    igual que en Talla.
    """

    TABLAS = {
        'departamento': 'departamentos',
        'ciudad': 'ciudades',
        'ciudad_nacimiento': 'ciudades',
        'departamento_nacimiento': 'departamentos_nacimiento',
        'pais_nacimiento': 'paises_nacimiento',
        'nacionalidad': 'nacionalidades',
        'religion': 'religiones',
        'area': 'areas',
        'fondo_pension': 'fondos_pension',
        'fondo_cesantias': 'fondos_cesantias',
        'caja_compensacion': 'cajas_compensacion',
        'banco': 'bancos',
    }

    ETIQUETAS = {
        'departamento': 'Departamento',
        'ciudad': 'Ciudad',
        'ciudad_nacimiento': 'Ciudad de nacimiento',
        'departamento_nacimiento': 'Departamento de nacimiento',
        'pais_nacimiento': 'País de nacimiento',
        'nacionalidad': 'Nacionalidad',
        'religion': 'Religión',
        'area': 'Área',
        'fondo_pension': 'Fondo de pensión',
        'fondo_cesantias': 'Fondo de cesantías',
        'caja_compensacion': 'Caja de compensación',
        'banco': 'Banco',
    }

    @classmethod
    def _tabla(cls, campo):
        tabla = cls.TABLAS.get((campo or '').strip().lower())
        if not tabla:
            raise ValueError("Catálogo no válido")
        return tabla

    @classmethod
    def get_all(cls, campo, activas_solo=True):
        tabla = cls._tabla(campo)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = f"SELECT id, nombre, activa FROM {tabla}"
                if activas_solo:
                    sql += " WHERE activa = TRUE"
                sql += " ORDER BY nombre"
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    @classmethod
    def get_by_id(cls, campo, registro_id):
        tabla = cls._tabla(campo)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    f"SELECT id, nombre, activa FROM {tabla} WHERE id = %s",
                    (registro_id,)
                )
                return cur.fetchone()
        finally:
            conn.close()

    @classmethod
    def create(cls, campo, nombre, activa=True):
        tabla = cls._tabla(campo)
        etiqueta = cls.ETIQUETAS.get(campo, 'registro')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO {tabla} (nombre, activa)
                        VALUES (%s, %s) RETURNING id""",
                    (nombre.strip().upper(), activa)
                )
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe un registro de {etiqueta} con ese nombre")
            raise
        finally:
            conn.close()

    @classmethod
    def update(cls, campo, registro_id, nombre, activa=True):
        tabla = cls._tabla(campo)
        etiqueta = cls.ETIQUETAS.get(campo, 'registro')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {tabla} SET nombre = %s, activa = %s
                        WHERE id = %s""",
                    (nombre.strip().upper(), activa, registro_id)
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Ya existe un registro de {etiqueta} con ese nombre")
            raise
        finally:
            conn.close()

    @classmethod
    def toggle_activa(cls, campo, registro_id):
        tabla = cls._tabla(campo)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {tabla} SET activa = NOT activa WHERE id = %s RETURNING activa",
                    (registro_id,)
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
        finally:
            conn.close()