# models/cabecera/services.py
from models.cabecera.model import insert_lote_if_not_exists, fetch_cabecera_by_lote, update_cabecera_column

def get_cabecera_info(lote: str):
    """ Lógica para obtener la información de la cabecera """
    if not lote or lote == 'VACIO': 
        return {}
    
    # Llamamos a la capa de datos (model.py)
    insert_lote_if_not_exists(lote)
    return fetch_cabecera_by_lote(lote)

def update_cabecera_unificada(lote: str, columna: str, valor: str) -> tuple[bool, str]:
    """ Lógica y validación antes de actualizar """
    COLUMNAS_PERMITIDAS = {
        'fecha_recepcion', 'granja_prod', 'granja_lev', 'no_pollitas_recibidas',
        'responsable_tecnico', 'ciudad', 'tipo_galpon', 'clima', 'uniformidad',
        'peso', 'unidad_peso', 'coeficiente_variacion', 'fecha_encasetamiento',
        'no_aves_encasetadas', 'unidad_medida', 'cliente', 'variedad',
        'marca_galpon', 'nutricionista', 'validacion'
    }
    
    # 1. Validación (Regla de negocio)
    if columna not in COLUMNAS_PERMITIDAS: 
        return False, f"Columna '{columna}' no permitida"
    
    # 2. Limpieza de datos
    valor_db = valor if valor.strip() != '' else None
    
    # 3. Llamada a la capa de datos para guardar
    return update_cabecera_column(lote, columna, valor_db)