from datetime import datetime
from base import db  # Ajusta según tu importación de SQLAlchemy

class StockMateriaPrima(db.Model):
    __tablename__ = 'stock_materia_prima'
    
    id = db.Column(db.Integer, primary_key=True)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materia_prima.id'), nullable=False)
    lote_recepcion = db.Column(db.String(50), nullable=False)  # Ej: 'LOT-2026-001'
    cantidad_actual = db.Column(db.Float, nullable=False, default=0.0)
    costo_unitario = db.Column(db.Float, nullable=False, default=0.0)
    fecha_ingreso = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.Date, nullable=True)

class MovimientoInventario(db.Model):
    __tablename__ = 'movimientos_inventario'
    
    id = db.Column(db.Integer, primary_key=True)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materia_prima.id'), nullable=False)
    tipo_movimiento = db.Column(db.String(20), nullable=False)  # 'ENTRADA_COMPRA', 'SALIDA_PRODUCCION', 'AJUSTE'
    cantidad = db.Column(db.Float, nullable=False)  # Positivo para entradas, negativo para salidas
    referencia_id = db.Column(db.Integer, nullable=True)  # ID de la Recepción o del RegistroProduccion
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    observacion = db.Column(db.String(255), nullable=True)
    
    @staticmethod
def reabrir_mes(mes_origen, anio_origen):
    # Calcular cuál es el mes destino que se debe limpiar
    if mes_origen == 12:
        mes_destino, anio_destino = 1, anio_origen + 1
    else:
        mes_destino, anio_destino = mes_origen + 1, anio_origen

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Eliminar los registros de inventario_inicial del mes destino
            cur.execute("""
                DELETE FROM inventario_inicial
                WHERE EXTRACT(MONTH FROM fecha_registro) = %s
                  AND EXTRACT(YEAR FROM fecha_registro) = %s;
            """, (mes_destino, anio_destino))
            
            conn.commit()
            return True, f"El cierre del mes {mes_origen}/{anio_origen} fue anulado. Se eliminaron los saldos iniciales de {mes_destino}/{anio_destino}."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()