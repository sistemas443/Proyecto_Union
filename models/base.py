# models/base.py
import atexit
import os
import subprocess
import threading
import time

import psycopg2
import psycopg2.extensions
import psycopg2.extras
import psycopg2.pool

from config import Config


def obtener_hash_git():
    """Obtiene el hash corto del commit actual de Git."""
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
    except Exception:
        return 'unknown'


# ============================================================================
# POOL DE CONEXIONES
# ----------------------------------------------------------------------------
# La base esta en un servidor remoto: abrir una conexion nueva cuesta ~0.5-0.7s
# y cada pantalla abria entre 5 y 8. Con el pool se reutilizan las conexiones
# ya autenticadas, sin cambiar la forma en que los modelos las usan:
# cada modelo sigue pidiendo su conexion y llamando a close() al terminar,
# pero close() ahora devuelve la conexion al pool en lugar de cerrarla.
# ============================================================================

DB_POOL_MIN = int(os.environ.get('DB_POOL_MIN', '1'))
DB_POOL_MAX = int(os.environ.get('DB_POOL_MAX', '10'))

# Segundos de inactividad tras los cuales se comprueba que la conexion sigue viva
DB_POOL_VALIDAR = float(os.environ.get('DB_POOL_VALIDAR_SEGUNDOS', '30'))

PARAMETROS_CONEXION = dict(
    host=Config.DB_HOST,
    database=Config.DB_NAME,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    port=Config.DB_PORT,
    client_encoding='utf8',
    connect_timeout=10,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=3,
)

PARAMETROS_SST = dict(
    host=Config.MASTER_SST_HOST,
    database=Config.MASTER_SST_NAME,
    user=Config.MASTER_SST_USER,
    password=Config.MASTER_SST_PASSWORD,
    port=Config.MASTER_SST_PORT,
    client_encoding='utf8',
    connect_timeout=10,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=3,
)


class ConexionPool:
    """
    Envoltura transparente de una conexion psycopg2.

    Se comporta igual que la conexion original (cursor, commit, rollback,
    atributos) pero close() la devuelve al pool en vez de cerrarla.
    """

    __slots__ = ('_conn', '_pool', '_cerrada')

    def __init__(self, conn, pool=None):
        object.__setattr__(self, '_conn', conn)
        object.__setattr__(self, '_pool', pool)
        object.__setattr__(self, '_cerrada', False)

    def __getattr__(self, nombre):
        return getattr(object.__getattribute__(self, '_conn'), nombre)

    def __setattr__(self, nombre, valor):
        setattr(object.__getattribute__(self, '_conn'), nombre, valor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def close(self):
        if object.__getattribute__(self, '_cerrada'):
            return
        object.__setattr__(self, '_cerrada', True)

        conn = object.__getattribute__(self, '_conn')
        pool = object.__getattribute__(self, '_pool')

        if pool is None:
            try:
                conn.close()
            except Exception:
                pass
            return

        pool.devolver(conn)


class PoolConexiones:
    """Administra el pool de conexiones a la base principal."""

    def __init__(self, minimo, maximo, parametros):
        self._minimo = minimo
        self._maximo = maximo
        self._parametros = parametros
        self._pool = None
        self._lock = threading.Lock()
        self._ultimo_uso = {}

    def _crear_pool(self):
        return psycopg2.pool.ThreadedConnectionPool(
            self._minimo, self._maximo, **self._parametros
        )

    def _pool_actual(self):
        pool = self._pool
        if pool is None:
            with self._lock:
                if self._pool is None:
                    self._pool = self._crear_pool()
                pool = self._pool
        return pool

    def _conexion_directa(self):
        """Ultimo recurso: si el pool falla o esta agotado, se conecta igual que antes."""
        return ConexionPool(psycopg2.connect(**self._parametros))

    def obtener(self):
        try:
            pool = self._pool_actual()
        except Exception as e:
            print(f"[POOL] No se pudo crear el pool, se usa conexion directa: {e}")
            return self._conexion_directa()

        for _ in range(2):
            try:
                conn = pool.getconn()
            except psycopg2.pool.PoolError:
                # Pool agotado: se responde igual que antes en vez de fallar
                return self._conexion_directa()
            except Exception as e:
                print(f"[POOL] Error obteniendo conexion: {e}")
                break

            if conn.closed:
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass
                continue

            inactiva = time.monotonic() - self._ultimo_uso.pop(id(conn), 0.0)
            if inactiva > DB_POOL_VALIDAR:
                try:
                    with conn.cursor() as cur:
                        cur.execute('SELECT 1')
                    conn.rollback()
                except Exception:
                    try:
                        pool.putconn(conn, close=True)
                    except Exception:
                        pass
                    continue

            return ConexionPool(conn, self)

        return self._conexion_directa()

    def devolver(self, conn):
        if conn.closed:
            return

        # No devolver al pool una conexion con transaccion abierta o en error
        try:
            if conn.status != psycopg2.extensions.STATUS_READY:
                conn.rollback()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            return

        pool = self._pool
        if pool is None:
            try:
                conn.close()
            except Exception:
                pass
            return

        self._ultimo_uso[id(conn)] = time.monotonic()
        try:
            pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def cerrar(self):
        with self._lock:
            if self._pool is not None:
                try:
                    self._pool.closeall()
                except Exception:
                    pass
                self._pool = None


_pool_principal = PoolConexiones(DB_POOL_MIN, DB_POOL_MAX, PARAMETROS_CONEXION)
atexit.register(_pool_principal.cerrar)


def get_db_connection():
    """
    Devuelve una conexion a la base principal, reutilizada del pool.

    Se usa exactamente igual que antes: conn = get_db_connection() ... conn.close()
    """
    return _pool_principal.obtener()


def get_master_sst_connection():
    """Conexión de solo lectura a la base de Seguridad y Salud en el Trabajo."""
    return psycopg2.connect(**PARAMETROS_SST)


def parse_empty(value):
    return value if value and str(value).strip() != '' else None


def to_float_safe(val):
    if val is None or str(val).strip() == '':
        return 0.0
    try:
        val_str = str(val).replace(',', '.')
        return float(val_str)
    except Exception:
        return 0.0
