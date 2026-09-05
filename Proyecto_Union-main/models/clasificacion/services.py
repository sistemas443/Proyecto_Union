# models/clasificacion/services.py
from models.base import parse_empty
from models.clasificacion.schemas import COLUMNAS_PERMITIDAS
from models.clasificacion import model
from models.cabecera.model import fetch_cabecera_by_lote

def generar_estructura_clasificacion(lote_nombre, id_lote):
    if not id_lote or not lote_nombre: return
    if model.count_clasificacion(id_lote) > 0: return

    valores = [(lote_nombre, id_lote, sv) for sv in range(18, 110)]
    model.insert_estructura(valores)

def get_clasificacion_all(lote_nombre: str = ''):
    if not lote_nombre or lote_nombre == 'VACIO': return []
    
    cabecera = fetch_cabecera_by_lote(lote_nombre)
    if not cabecera: return []
    
    id_lote = cabecera['id']
    rows = model.fetch_clasificacion_all(id_lote)
    
    if len(rows) == 0:
        generar_estructura_clasificacion(lote_nombre, id_lote)
        rows = model.fetch_clasificacion_all(id_lote)
        
    return rows

def update_clasificacion_field(id_reg: int, columna: str, valor: str) -> bool:
    if columna not in COLUMNAS_PERMITIDAS: return False
    valor_db = parse_empty(valor)
    return model.update_columna(id_reg, columna, valor_db)