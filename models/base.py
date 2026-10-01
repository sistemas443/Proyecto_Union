# models/base.py
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