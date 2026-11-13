# models/eventualidades/services.py
"""Reglas de negocio de las eventualidades del lote."""

from datetime import date

from models.base import get_db_connection
from models.eventualidades import model

# ámbito -> (semana mínima, semana máxima, nombre visible)
AMBITOS = {
    'PRODUCCION': (0, 130, 'Producción'),
    'LEVANTE': (1, 18, 'Levante'),
    'PRIMERA_SEMANA': (0, 7, 'Primera semana'),
}

TIPOS_POR_DEFECTO = ['Otro']


def _limpiar(valor, limite=200):
    texto = (valor or '').strip()
    return texto[:limite] if texto else None


def _auditar(usuario_id, usuario_nombre, id_evento, campo, anterior, nuevo, accion):
    """Registra el movimiento en el historial; nunca rompe la operación."""
    try:
        from models.auditoria.services import registrar_cambio
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                registrar_cambio(
                    usuario_id or 0,
                    usuario_nombre or 'Sistema',
                    'eventualidades_lote',
                    id_evento,
                    campo,
                    anterior,
                    nuevo,
                    accion,
                    cur,
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[AVISO AUDITORIA EVENTUALIDADES]: {e}")


def _serializable(fila):
    fecha = fila.get('fecha')
    creado = fila.get('creado_en')
    if hasattr(fecha, 'isoformat'):
        fila['fecha'] = fecha.isoformat()
    if hasattr(creado, 'isoformat'):
        fila['creado_en'] = creado.isoformat(timespec='minutes')
    return fila


def listar(lote, ambito):
    if ambito not in AMBITOS:
        raise ValueError('El ámbito indicado no es válido.')

    id_lote = model.fetch_id_lote(lote)
    if not id_lote:
        raise ValueError(f'El lote {lote} no existe.')

    filas = model.fetch_eventualidades(id_lote, ambito)
    return {
        'status': 'ok',
        'lote': lote,
        'ambito': ambito,
        'eventualidades': [_serializable(f) for f in filas],
    }


def crear(datos, usuario_id=None, usuario_nombre=None):
    lote = (datos.get('lote') or '').strip()
    ambito = (datos.get('ambito') or '').strip().upper()
    titulo = _limpiar(datos.get('titulo'))

    if not lote:
        raise ValueError('Falta el lote.')
    if ambito not in AMBITOS:
        raise ValueError('El ámbito indicado no es válido.')
    if not titulo:
        raise ValueError('Escribe un título para la eventualidad.')

    try:
        semana = int(datos.get('semana'))
    except (TypeError, ValueError):
        raise ValueError('La semana indicada no es válida.')

    minimo, maximo, _ = AMBITOS[ambito]
    if not (minimo <= semana <= maximo):
        raise ValueError(f'La semana debe estar entre {minimo} y {maximo}.')

    id_lote = model.fetch_id_lote(lote)
    if not id_lote:
        raise ValueError(f'El lote {lote} no existe.')

    tipo_id = datos.get('tipo_id')
    try:
        tipo_id = int(tipo_id) if tipo_id else None
    except (TypeError, ValueError):
        tipo_id = None

    registro = {
        'id_lote': id_lote,
        'lote': lote,
        'ambito': ambito,
        'semana': semana,
        # La fecha del registro se guarda sola si no viene indicada
        'fecha': datos.get('fecha') or date.today().isoformat(),
        'tipo_id': tipo_id,
        'titulo': titulo,
        'detalle': _limpiar(datos.get('detalle'), 1000),
        'impacto': _limpiar(datos.get('impacto'), 200),
        'creado_por': usuario_id,
        'creado_por_nombre': usuario_nombre,
    }

    id_evento = model.insert_eventualidad(registro)
    _auditar(usuario_id, usuario_nombre, id_evento, 'crear', None,
             f'{ambito} semana {semana}: {titulo}', 'INSERT')

    return {'status': 'ok', 'id': id_evento, 'semana': semana}


def actualizar(id_evento, datos, usuario_id=None, usuario_nombre=None):
    existente = model.fetch_eventualidad(id_evento)
    if not existente:
        raise ValueError('La eventualidad no existe.')
    if existente.get('eliminado_en'):
        raise ValueError('La eventualidad está eliminada.')

    titulo = _limpiar(datos.get('titulo'))
    if not titulo:
        raise ValueError('Escribe un título para la eventualidad.')

    tipo_id = datos.get('tipo_id')
    try:
        tipo_id = int(tipo_id) if tipo_id else None
    except (TypeError, ValueError):
        tipo_id = None

    cambios = {
        'tipo_id': tipo_id,
        'titulo': titulo,
        'detalle': _limpiar(datos.get('detalle'), 1000),
        'impacto': _limpiar(datos.get('impacto'), 200),
        'fecha': datos.get('fecha') or None,
    }

    model.actualizar_eventualidad(id_evento, cambios)
    _auditar(usuario_id, usuario_nombre, id_evento, 'editar',
             existente.get('titulo'), titulo, 'UPDATE')

    return {'status': 'ok', 'id': id_evento}


def eliminar(id_evento, usuario_id=None, usuario_nombre=None):
    existente = model.fetch_eventualidad(id_evento)
    if not existente:
        raise ValueError('La eventualidad no existe.')
    if existente.get('eliminado_en'):
        raise ValueError('La eventualidad ya estaba eliminada.')

    model.eliminar_eventualidad(id_evento)
    _auditar(usuario_id, usuario_nombre, id_evento, 'eliminar',
             existente.get('titulo'), 'eliminada', 'DELETE')
    return {'status': 'ok'}


def tipos():
    return {'status': 'ok', 'tipos': model.fetch_tipos()}


def crear_tipo(nombre, color=None, usuario_id=None, usuario_nombre=None):
    nombre = _limpiar(nombre, 60)
    if not nombre:
        raise ValueError('Escribe el nombre del tipo.')

    color = _limpiar(color, 20) or '#6c757d'
    fila = model.insert_tipo(nombre, color)
    _auditar(usuario_id, usuario_nombre, fila['id'], 'tipo',
             None, nombre, 'INSERT')
    return {'status': 'ok', 'tipo': fila}
