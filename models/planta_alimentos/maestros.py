import psycopg2
import psycopg2.extras
from models.base import get_db_connection


class MateriaPrima:

    @staticmethod
    def get_all():
        """Obtiene las materias primas calculando las columnas financieras del Excel."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id, 
                        nombre, 
                        COALESCE(proveedor, '') AS proveedor, 
                        precio_actual_kg, 
                        COALESCE(iva, 1.00) AS iva, 
                        COALESCE(flete, 0.00) AS flete,
                        COALESCE(es_maquila, FALSE) AS es_maquila,
                        
                        -- Cálculos de Columnas Financieras
                        (precio_actual_kg * COALESCE(iva, 1.00)) AS p_iva,
                        ((precio_actual_kg * COALESCE(iva, 1.00)) + COALESCE(flete, 0.00)) AS p_iva_flete,
                        precio_actual_kg AS precio_neto,
                        (precio_actual_kg + COALESCE(flete, 0.00)) AS p_flete,
                        
                        fecha_actualizacion
                    FROM materias_primas
                    ORDER BY nombre ASC;
                """)
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(nombre, precio_actual_kg, proveedor='', iva=1.00, flete=0.00, es_maquila=False):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO materias_primas (nombre, precio_actual_kg, proveedor, iva, flete, es_maquila, fecha_actualizacion)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW());
                """, (nombre, precio_actual_kg, proveedor, iva, flete, es_maquila))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update(id_mp, nombre, precio_actual_kg, proveedor='', iva=1.00, flete=0.00, es_maquila=False):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE materias_primas
                    SET nombre = %s, 
                        precio_actual_kg = %s, 
                        proveedor = %s, 
                        iva = %s, 
                        flete = %s, 
                        es_maquila = %s,
                        fecha_actualizacion = NOW()
                    WHERE id = %s;
                """, (nombre, precio_actual_kg, proveedor, iva, flete, es_maquila, id_mp))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def delete(id_mp):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM materias_primas WHERE id = %s;", (id_mp,))
                conn.commit()
        finally:
            conn.close()

# ==========================================
# 2. CATÁLOGO DE ALIMENTOS (DIETAS)
# ==========================================YY
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
            


# ==========================================
# 3. PROVEEDORES
# ==========================================

class Proveedor:

    @staticmethod
    def get_all():
        """Obtiene todos los proveedores ordenados alfabéticamente."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre ASC;")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(nombre):
        """Registra un nuevo proveedor."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO proveedores (nombre) VALUES (%s) ON CONFLICT DO NOTHING;",
                    (nombre.strip().upper(),)
                )
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update(id_prov, nombre):
        """Actualiza el nombre de un proveedor."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE proveedores SET nombre = %s WHERE id = %s;",
                    (nombre.strip().upper(), id_prov)
                )
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def delete(id_prov):
        """Elimina un proveedor por ID."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM proveedores WHERE id = %s;", (id_prov,))
                conn.commit()
        finally:
            conn.close()