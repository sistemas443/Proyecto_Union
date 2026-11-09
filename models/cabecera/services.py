# models/cabecera/services.py
from models.cabecera.model import (
    insert_lote_if_not_exists,
    insert_y_obtener_cabecera,
    fetch_cabecera_by_lote,
    update_cabecera_column,
)

def get_cabecera_info(lote: str):
    """ Lógica para obtener la información de la cabecera """
    if not lote or lote == 'VACIO': 
        return {}
    
    # Crea el lote si falta y devuelve la cabecera en una sola consulta
    return insert_y_obtener_cabecera(lote)

def _auditar_cabecera(lote, columna, valor_db, usuario_id=None, usuario_nombre=None):
    """Registra la edición inline en auditoría para que consolidados se refresque."""
    try:
        from models.base import get_db_connection
        from models.auditoria.services import registrar_cambio

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM cabecera_lotes WHERE lote = %s", (lote,))
            fila = cur.fetchone()
            registrar_cambio(
                usuario_id=usuario_id,
                usuario_nombre=usuario_nombre or 'Sistema',
                tabla='cabecera_lotes',
                id_registro=fila[0] if fila else None,
                campo=columna,
                valor_anterior=None,
                valor_nuevo=valor_db,
                accion='UPDATE',
                cursor=cur,
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"[AUDITORIA CABECERA] {e}")


def update_cabecera_unificada(lote: str, columna: str, valor: str,
                              usuario_id=None, usuario_nombre=None) -> tuple[bool, str]:
    """ Lógica y validación antes de actualizar la tabla """
    
    # Agregamos la columna 'nutricionista_prod' a la lista de palabras aceptadas por la BD
    COLUMNAS_PERMITIDAS = {
        'fecha_recepcion', 'granja_prod', 'granja_lev', 'no_pollitas_recibidas',
        'responsable_tecnico', 'ciudad', 'tipo_galpon', 'clima', 'uniformidad',
        'peso', 'unidad_peso', 'coeficiente_variacion', 'fecha_encasetamiento',
        'no_aves_encasetadas', 'unidad_medida', 'variedad',
        'marca_galpon', 'nutricionista', 'nutricionista_prod', 'validacion'
    }
    COLUMNAS_RECALCULO = {
        'fecha_recepcion', 'no_pollitas_recibidas', 'no_aves_encasetadas',
        'peso', 'unidad_peso', 'fecha_encasetamiento',
    }
    
    # 1. Validación (Regla de negocio) para evitar hackeos a la BD
    if columna not in COLUMNAS_PERMITIDAS: 
        return False, f"Columna '{columna}' no permitida"
    
    # 2. Limpieza de datos (convierte espacios vacíos en datos nulos reales)
    valor_db = valor if valor.strip() != '' else None
    
    # 3. Llamada a la capa de datos para inyectar en PostgreSQL
    ok, msg = update_cabecera_column(lote, columna, valor_db)

    if ok:
        # 4. Recalcular las tablas derivadas si el campo alimenta consolidados
        if columna in COLUMNAS_RECALCULO:
            from models.lotes.services import recalcular_lote_por_nombre
            rec_ok, rec_msg = recalcular_lote_por_nombre(lote)
            if not rec_ok:
                print(f"[RECALCULO CABECERA] {lote}: {rec_msg}")

        # 5. Auditar para que el refresco en vivo de consolidados detecte el cambio
        _auditar_cabecera(lote, columna, valor_db, usuario_id, usuario_nombre)

    return ok, msg