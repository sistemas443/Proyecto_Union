from models.base import get_db_connection

conn = get_db_connection()
cur = conn.cursor()
cur.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name', ('public',))
for row in cur.fetchall():
    print(row[0])
conn.close()