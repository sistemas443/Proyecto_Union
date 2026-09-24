from datetime import datetime
from base import db  # Ajusta la importación según tu estructura

class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_compra'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_orden = db.Column(db.String(30), unique=True, nullable=False)  # Ej: 'OC-2026-001'
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    fecha_emision = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='PENDIENTE')  # 'PENDIENTE', 'RECIBIDA', 'CANCELADA'
    observaciones = db.Column(db.Text, nullable=True)
    
    # Relaciones
    detalles = db.relationship('OrdenCompraDetalle', backref='orden', cascade='all, delete-orphan')

class OrdenCompraDetalle(db.Model):
    __tablename__ = 'ordenes_compra_detalle'
    
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=False)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materia_prima.id'), nullable=False)
    cantidad_solicitada = db.Column(db.Float, nullable=False)
    cantidad_recibida = db.Column(db.Float, default=0.0)
    precio_unitario = db.Column(db.Float, nullable=False)

class RecepcionCompra(db.Model):
    __tablename__ = 'recepciones_compra'
    
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=True)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materia_prima.id'), nullable=False)
    lote_ingreso = db.Column(db.String(50), nullable=False)  # Ej: 'LOT-ING-20260901'
    cantidad_ingresada = db.Column(db.Float, nullable=False)
    costo_unitario = db.Column(db.Float, nullable=False)
    fecha_recepcion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.Date, nullable=True)