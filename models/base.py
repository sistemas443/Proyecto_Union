# models/base.py
import re
import subprocess
import psycopg2
import psycopg2.extras
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

def get_db_connection():
    return psycopg2.connect(
        host=Config.DB_HOST,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        port=Config.DB_PORT,
        client_encoding='utf8'
    )


def get_master_sst_connection():
    """Conexión de solo lectura a la base de Seguridad y Salud en el Trabajo."""
    return psycopg2.connect(
        host=Config.MASTER_SST_HOST,
        database=Config.MASTER_SST_NAME,
        user=Config.MASTER_SST_USER,
        password=Config.MASTER_SST_PASSWORD,
        port=Config.MASTER_SST_PORT,
        client_encoding='utf8'
    )

def parse_empty(value):
    return value if value and str(value).strip() != '' else None

def to_float_safe(val):
    if val is None or str(val).strip() == '': 
        return 0.0
    try:
        val_str = str(val).replace(',', '.')
        return float(val_str)
    except:
        return 0.0


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