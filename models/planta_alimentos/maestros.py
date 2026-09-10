from models.base import get_db_connection
import psycopg2.extras

# ==========================================
# 1. MATERIAS PRIMAS
# ==========================================
class MateriaPrima:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre, precio_actual_kg, fecha_actualizacion FROM materias_primas ORDER BY nombre;")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(nombre, precio_actual_kg):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO materias_primas (nombre, precio_actual_kg) VALUES (%s, %s)",
                    (nombre, precio_actual_kg)
                )
                conn.commit()
        finally:
            conn.close()

# ==========================================
# 2. CATÁLOGO DE ALIMENTOS (DIETAS)
# ==========================================
class CatalogoAlimento:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT item_id, nombre, rango_semanas FROM catalogo_alimentos ORDER BY item_id;")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(item_id, nombre, rango_semanas):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO catalogo_alimentos (item_id, nombre, rango_semanas) VALUES (%s, %s, %s)",
                    (item_id, nombre, rango_semanas)
                )
                conn.commit()
        finally:
            conn.close()

# ==========================================
# 3. EMPRESAS (CLIENTES / MAQUILAS)
# ==========================================
class Empresa:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre, costo_maquila FROM empresas ORDER BY nombre;")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(nombre, costo_maquila):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO empresas (nombre, costo_maquila) VALUES (%s, %s)",
                    (nombre, costo_maquila)
                )
                conn.commit()
        finally:
            conn.close()