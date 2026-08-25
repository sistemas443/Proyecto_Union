import os
import psycopg2

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    DB_HOST = os.environ.get('DB_HOST', '136.114.241.97')
    DB_NAME = os.environ.get('DB_NAME', 'data_vargas')
    DB_USER = os.environ.get('DB_USER', 'admin_app')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'TuClaveSegura123')
    DB_PORT = os.environ.get('DB_PORT', '5432')

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