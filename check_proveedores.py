import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.DB_HOST,
    port=Config.DB_PORT,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    dbname=Config.DB_NAME
)
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", ('proveedores',))
cols = cur.fetchall()
for c in cols:
    print(c[0])
cur.close()
conn.close()