from models.base import get_db_connection
import psycopg2.extras

class ComprasModel:
    @staticmethod
    def crear_orden_compra(proveedor_id, observaciones, num_orden):
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO ordenes_compra (numero_orden, proveedor_id, observaciones, estado, fecha_emision)
            VALUES (%s, %s, %s, 'PENDIENTE', CURRENT_TIMESTAMP)
            RETURNING id;
        """
        cursor.execute(query, (num_orden, proveedor_id, observaciones))
        orden_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return orden_id

    @staticmethod
    def registrar_recepcion_e_inventario(materia_prima_id, lote_ingreso, cantidad, costo_unitario, fecha_vencimiento):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Registrar Recepción
            cursor.execute("""
                INSERT INTO recepciones_compra (materia_prima_id, lote_ingreso, cantidad_ingresada, costo_unitario, fecha_vencimiento)
                VALUES (%s, %s, %s, %s, %s);
            """, (materia_prima_id, lote_ingreso, cantidad, costo_unitario, fecha_vencimiento))
            
            # 2. Registrar en Stock
            cursor.execute("""
                INSERT INTO stock_materia_prima (materia_prima_id, lote_recepcion, cantidad_actual, costo_unitario, fecha_vencimiento)
                VALUES (%s, %s, %s, %s, %s);
            """, (materia_prima_id, lote_ingreso, cantidad, costo_unitario, fecha_vencimiento))
            
            # 3. Registrar en Kárdex / Movimientos
            cursor.execute("""
                INSERT INTO movimientos_inventario (materia_prima_id, tipo_movimiento, cantidad, observacion)
                VALUES (%s, 'ENTRADA_COMPRA', %s, %s);
            """, (materia_prima_id, cantidad, f'Ingreso directo Lote: {lote_ingreso}'))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()