# models/reporte_diario/sync_diario.py
"""Lleva los datos operativos del Reporte Diario al módulo Diario.

El Reporte Diario es la primera captura del día; el Diario es la fuente que
alimenta los consolidados. Para no digitar dos veces, cada celda que se guarda
en el Reporte Diario se replica en `data_diario` reutilizando la misma cascada
de cálculo del Diario (`update_registro_diario_field`), de modo que el saldo,
los porcentajes y los módulos derivados queden idénticos.
"""

from models.base import a_numero, get_db_connection

# Campo del Reporte Diario -> columna de data_diario
CAMPOS_DIARIO = {
    'produccion': 'produccion',
    'alimento': 'consumo_kg',
    'muertas': 'mortalidad',
    'agua': 'consumo_agua',
    'otras': 'otros',
}


def _sin_cambios(actual, nuevo):
    """True si el valor que ya tiene el Diario es el mismo que se va a enviar."""
    actual_num = a_numero(actual)
    if actual_num is None:
        return False
    return abs(actual_num - nuevo) < 0.000001


def sincronizar_diario(id_lote, fecha, campo, valor, afecta_saldo=True):
    """Replica un valor del Reporte Diario en el día equivalente del Diario.

    Reglas:
      - Un valor vacío no borra lo que ya tenga el Diario.
      - "otras" solo se envía cuando afecta el saldo (en el Diario `otros`
        siempre descuenta aves).
      - Si el día no existe en `data_diario`, no se escribe nada.
      - Si el valor ya es el mismo, no se recalcula.

    Devuelve un dict con `sincronizado` (bool) y `motivo`.
    """
    columna = CAMPOS_DIARIO.get(campo)
    if not columna:
        return {'sincronizado': False, 'motivo': 'campo_fuera_de_alcance'}

    texto = '' if valor is None else str(valor).strip()
    if texto == '':
        return {'sincronizado': False, 'motivo': 'valor_vacio'}

    if campo == 'otras' and afecta_saldo is False:
        return {'sincronizado': False, 'motivo': 'afecta_saldo_no'}

    nuevo = a_numero(texto)
    if nuevo is None:
        return {'sincronizado': False, 'motivo': 'valor_invalido'}

    # Se envía un texto numérico limpio: entero para las columnas enteras y
    # decimal para el resto (evita comas de miles y formatos del navegador).
    if columna in ('mortalidad', 'otros', 'consumo_kg'):
        texto_db = str(int(round(nuevo)))
    else:
        texto_db = str(nuevo)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # `fecha_dia` es texto ISO (YYYY-MM-DD) en data_diario.
        fecha_txt = fecha.isoformat() if hasattr(fecha, 'isoformat') else str(fecha)
        # `columna` sale de CAMPOS_DIARIO (lista blanca), nunca del request.
        cur.execute(
            f'SELECT id_diario, "{columna}" FROM data_diario '
            'WHERE id_lote = %s AND fecha_dia = %s '
            'ORDER BY dias ASC LIMIT 1',
            (id_lote, fecha_txt),
        )
        fila = cur.fetchone()
        if not fila:
            return {'sincronizado': False, 'motivo': 'sin_dia_en_diario'}

        id_diario, actual = fila
        if _sin_cambios(actual, nuevo):
            return {'sincronizado': True, 'sin_cambios': True, 'motivo': 'sin_cambios'}
    finally:
        cur.close()
        conn.close()

    # Importación diferida: models.diario.services carga pandas/numpy.
    from models.diario.services import update_registro_diario_field

    ok, _campos, mensaje = update_registro_diario_field(id_diario, columna, texto_db)
    if not ok:
        return {
            'sincronizado': False,
            'motivo': 'error',
            'detalle': mensaje or 'No se pudo actualizar el Diario',
        }

    return {'sincronizado': True, 'sin_cambios': False, 'motivo': 'ok'}
