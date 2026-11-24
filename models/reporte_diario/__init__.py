# models/reporte_diario/__init__.py
from .sync_diario import sincronizar_diario
from .model import (
    CAMPOS_NUMERICOS,
    CAMPOS_TEXTO,
    MESES,
    cabecera_lote,
    crear_desinfectante,
    crear_proceso,
    estado_mes,
    guardar_campo,
    guardar_modulos_entrada,
    guardar_procesos,
    listar_desinfectantes,
    listar_mes,
    listar_procesos,
    modulos_entrada,
    mort_total_de,
    saldo_inicial,
    tabla_disponible,
)
