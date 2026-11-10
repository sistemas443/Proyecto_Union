# models/base.py
import atexit
import os
import re
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
DB_POOL_VALIDAR = float(os.environ.get('DB_POOL_VALIDAR_SEGUNDOS', '120'))

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

            ahora = time.monotonic()
            ultimo = self._ultimo_uso.get(id(conn))
            if ultimo is None:
                # Conexion nueva: no necesita ping; se registra desde ya.
                self._ultimo_uso[id(conn)] = ahora
                ultimo = ahora

            inactiva = ahora - ultimo
            if inactiva > DB_POOL_VALIDAR:
                try:
                    with conn.cursor() as cur:
                        cur.execute('SELECT 1')
                    conn.rollback()
                    self._ultimo_uso[id(conn)] = time.monotonic()
                except Exception:
                    self._ultimo_uso.pop(id(conn), None)
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


def a_numero(valor):
    """Convierte a float aceptando coma decimal; devuelve None si no es numérico."""
    if valor is None or str(valor).strip() == '':
        return None
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None


def redondear(valor, decimales=2):
    """Redondea un valor numérico; conserva None para celdas vacías."""
    numero = a_numero(valor)
    return None if numero is None else round(numero, decimales)


def formatear_decimal(valor, decimales=2):
    """Devuelve el número como texto con los decimales fijos; None si está vacío."""
    numero = a_numero(valor)
    return None if numero is None else f'{numero:.{decimales}f}'


def respaldar_tabla_lote(tabla, id_lote):
    """Guarda un CSV con las filas actuales del lote antes de reemplazarlas.

    Se usa antes de los borrados masivos de las cargas de Excel. Si el respaldo
    falla no interrumpe la carga: solo deja el aviso en consola.
    """
    import csv
    from datetime import datetime

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "%s" WHERE id_lote = %%s' % tabla, (id_lote,))
        filas = cur.fetchall()
        columnas = [desc[0] for desc in cur.description]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        carpeta = os.path.join(base_dir, 'respaldos')
        os.makedirs(carpeta, exist_ok=True)
        nombre = f'{tabla}_{id_lote}_{datetime.now():%Y%m%d_%H%M%S}.csv'
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, 'w', newline='', encoding='utf-8') as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(columnas)
            escritor.writerows(filas)
        return ruta
    except Exception as e:
        print(f'[RESPALDO] No se pudo respaldar {tabla} del lote {id_lote}: {e}')
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# Traducción de errores técnicos a texto que el usuario entiende.
# Cada entrada es (patrones en minúsculas, mensaje amigable).
_TRADUCCIONES_ERRORES = (
    (('duplicate key value violates unique constraint', 'uniqueviolation'),
     'Ya existe un registro con ese mismo dato. Use un valor distinto o edite el que ya existe.'),
    (('foreign key violation', 'violates foreign key constraint'),
     'No se puede completar porque el registro está relacionado con información que todavía existe en el sistema.'),
    (('null value in column', 'notnullviolation', 'violates not-null constraint'),
     'Faltan datos obligatorios. Complete todos los campos requeridos antes de guardar.'),
    (('could not connect', 'connection refused', 'connection to server',
      'server closed the connection', 'could not translate host name',
      'no route to host', 'connection already closed', 'interfaceerror',
      'connection unexpectedly closed'),
     'No se pudo conectar con la base de datos. Verifique la conexión e intente de nuevo en unos segundos.'),
    (('could not obtain lock', 'lock not available', 'deadlock detected', 'lock_not_available'),
     'Otro usuario está guardando los mismos datos en este momento. Espere unos segundos e intente de nuevo.'),
    (('statement timeout', 'query canceled', 'canceling statement', 'statement was canceled'),
     'La operación tardó demasiado y fue cancelada. Intente de nuevo.'),
    (('invalid input syntax', 'invalidtextrepresentation'),
     'Uno de los valores digitados no tiene el formato que se espera en ese campo.'),
    (('numeric field overflow', 'numeric value out of range', 'numericvaluetoobig'),
     'El valor digitado es demasiado grande para ese campo.'),
    (('date/time field value out of range', 'invalid date format', 'invalid datetime format'),
     'La fecha digitada no es válida.'),
    (('check violation', 'violates check constraint'),
     'El valor no cumple con las reglas permitidas para ese campo.'),
    (('out-of-bounds', 'out of bounds', 'usecols'),
     'El archivo trae menos columnas de las que el sistema espera. Verifique que sea el archivo correcto.'),
    (('undefinedcolumn', 'does not exist', 'no such column'),
     'No se encontró algo que el sistema necesita (una columna de la base de datos o un archivo). '
     'Revise que el archivo y la información sean los correctos; si persiste, repórtelo al administrador.'),
    (('syntax error', 'programmingerror'),
     'Error interno del sistema al ejecutar la operación. Repórtelo al administrador.'),
    (('list index out of range', 'index out of range'),
     'El archivo no trae la información en la posición que el sistema espera. Verifique que sea el archivo correcto.'),
    (('nonetype', 'has no attribute', 'is not defined', 'is not iterable', 'not all arguments converted',
      'keyerror', 'indexerror', 'nameerror', 'importerror', 'modulenotfounderror',
      'unboundlocalerror', 'attributeerror'),
     'Falta información necesaria para completar la operación. Verifique el archivo o el registro e intente de nuevo.'),
    (('valueerror', 'typeerror', 'zerodivisionerror'),
     'Uno de los valores digitados no es válido para esa operación. Revise los datos e intente de nuevo.'),
    (('codec can', 'unicodeDecodeError', 'invalid start byte', 'unexpected end of data'),
     'El archivo contiene caracteres que el sistema no puede leer. Vuelva a guardarlo en formato UTF-8.'),
    (('permission denied', 'not the owner', 'must be owner of relation'),
     'No tienes permisos para realizar esta operación. Contacte al administrador.'),
    (('read-only', 'cannot execute insert', 'cannot execute update', 'too many connections'),
     'La base de datos no acepta escrituras en este momento. Intente de nuevo en unos segundos.'),
)

# Marcas de que el texto es la descripción cruda de una excepción de Python
_MARCAS_EXCEPCION = (
    'traceback', 'psycopg2', 'exception', 'violation', 'file "', 'line ',
    'noneType', 'has no attribute', 'is not defined', 'is not iterable',
    'unexpected end of input', 'indexError', 'KeyError', 'TypeError',
    'ValueError', 'AttributeError', 'NameError', 'ImportError', 'RuntimeError',
    'ZeroDivisionError', 'out of range', 'not all arguments converted',
)


def traducir_error(mensaje):
    """
    Convierte un error técnico en un texto claro para el usuario.

    Si reconoce el error (base de datos, archivo malformado, excepción de Python)
    devuelve una explicación en lenguaje sencillo. Si el texto ya es un mensaje
    claro, lo devuelve sin tocar. Si no logra identificarlo, encabeza el detalle
    técnico para que se entienda que algo falló sin ocultar la información.
    """
    texto = str(mensaje if mensaje is not None else '').strip()
    if not texto:
        return 'Ocurrió un error sin detalle. Intente de nuevo.'

    try:
        bajo = texto.lower()

        for patrones, amigable in _TRADUCCIONES_ERRORES:
            if any(patron.lower() in bajo for patron in patrones):
                return amigable

        es_excepcion = any(marca.lower() in bajo for marca in _MARCAS_EXCEPCION)
        es_clase_excepcion = re.search(r'\b[A-Za-z_]*(?:Error|Exception|Violation)\s*:', texto) is not None

        if es_excepcion or es_clase_excepcion:
            return f'Ocurrió un error inesperado. Detalle técnico: {texto}'

        return texto
    except Exception:
        return texto
