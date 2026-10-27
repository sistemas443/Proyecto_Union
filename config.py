import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    APP_VERSION = '1.0.0'

    DB_HOST = os.environ.get('DB_HOST', '136.114.241.97')
    DB_NAME = os.environ.get('DB_NAME', 'data_vargas')
    DB_USER = os.environ.get('DB_USER', 'admin_app')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_PORT = os.environ.get('DB_PORT', '5432')

    # Segunda base (seguridad y salud en el trabajo). Reutiliza las credenciales
    # principales salvo que se definan variables MASTER_SST_* propias.
    MASTER_SST_HOST = os.environ.get('MASTER_SST_HOST', DB_HOST)
    MASTER_SST_PORT = os.environ.get('MASTER_SST_PORT', DB_PORT)
    MASTER_SST_NAME = os.environ.get('MASTER_SST_DB_NAME', 'master_sst')
    MASTER_SST_USER = os.environ.get('MASTER_SST_USER', DB_USER)
    MASTER_SST_PASSWORD = os.environ.get('MASTER_SST_PASSWORD', DB_PASSWORD)

try:
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        dbname=Config.DB_NAME,
        connect_timeout=5
    )

    # --- INICIO DE SILENCIO DE BASE DE DATOS ---
    # Comentamos las siguientes líneas para que la terminal no se llene de texto 
    # cada vez que el servidor se reinicia o detecta un cambio.
    # print("✅ Conectado correctamente a PostgreSQL")
    # print(f"Host: {Config.DB_HOST}")
    # print(f"Base de datos: {Config.DB_NAME}")
    # print(f"Usuario: {Config.DB_USER}")
    # --- FIN DE SILENCIO ---

    conn.close()

except Exception as e:
    print("❌ Error al conectar:")
    print(e)