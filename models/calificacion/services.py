# models/calificacion/services.py
"""Cálculo de la calificación de un lote contra la tabla genética.

Regla de negocio (v1):
    cumplimiento haa  = real / guia * 100        (más huevos es mejor)
    cumplimiento conv = guia / real * 100        (menos alimento es mejor)
    cumplimiento mort = guia / real * 100        (menos mortalidad es mejor)

    indice = suma(peso_i * cumplimiento_i) / suma(peso_i)

Los pesos y la escala cualitativa viven en este módulo para que la
configuración (opción B) solo tenga que leerlos desde la base de datos.
"""

from datetime import date, datetime

from models.calificacion import model
from models.consolidados import guias

# (clave, nombre visible, peso)
PESOS = (
    ('haa', 'HAA', 0.60),
    ('conv', 'Conversión acumulada', 0.30),
    ('mort', 'Mortalidad acumulada', 0.10),
)

# 'guias' = tabla versionada del proyecto; 'bd' = columnas _tab de bd_vargas.
FUENTE_GUIA = 'guias'

# La conversión se guarda en gramos por docena; se muestra y compara en kg.
CONV_ESCALA = 1000.0

# Tope de cumplimiento por variable (evita que un denominador casi nulo infle el índice).
TOPE_CUMPLIMIENTO = 150.0

# Antes de esta semana la conversión acumulada todavía no es representativa.
SEMANA_MINIMA_CONV = 21

# Última semana con referencia genética disponible.
SEMANA_MAX_GUIA = max(guias.GUIA_HAA_TAB)

# (umbral mínimo del índice, etiqueta, tono)
ESCALA = (
    (100.0, 'Excelente', 'ok'),
    (96.0, 'Bueno', 'ok'),
    (92.0, 'Aceptable', 'pendiente'),
    (85.0, 'Bajo', 'critica'),
    (0.0, 'Crítico', 'critica'),
)


def _num(valor):
    """Convierte a float de forma tolerante (None si no hay dato)."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(',', '.')
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _fecha(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return str(valor) if valor else None


def _referencia(clave, semana, fila):
    """Valor de la tabla genética para una variable, en la unidad del dato real."""
    if FUENTE_GUIA == 'bd':
        columna = {
            'haa': fila.get('h_av_aloj_tab'),
            'conv': fila.get('conv_acum_tab'),
            'mort': fila.get('mort_tab'),
        }[clave]
        valor = _num(columna)
    else:
        valor = {
            'haa': guias.GUIA_HAA_TAB.get(semana),
            'conv': guias.GUIA_CONV_ACUM_TAB.get(semana),
            'mort': guias.GUIA_MORT_ACUM.get(semana),
        }[clave]

    if valor is None:
        return None
    if clave == 'conv':
        return valor / CONV_ESCALA
    return valor


def _real(clave, fila):
    columna = {
        'haa': 'haa_real',
        'conv': 'conv_acum_real',
        'mort': 'percent_mort_acum',
    }[clave]
    return _num(fila.get(columna))


def _cumplimiento(clave, real, guia):
    """Porcentaje de cumplimiento respecto a la tabla (sin aplicar el tope)."""
    if real is None or guia is None:
        return None

    if clave == 'haa':
        if guia <= 0:
            return None
        return real / guia * 100.0

    # Conversión y mortalidad: menor es mejor.
    if real <= 0:
        return None
    if guia <= 0:
        # Sin referencia utilizable (p. ej. mortalidad 0 en la semana 18).
        return 100.0
    return guia / real * 100.0


def _unidad(clave):
    return {'haa': 'huevos/ave', 'conv': 'kg/docena', 'mort': '%'}[clave]


def _etiqueta(indice):
    for umbral, texto, tono in ESCALA:
        if indice >= umbral:
            return {'etiqueta': texto, 'tono': tono}
    return {'etiqueta': 'Crítico', 'tono': 'critica'}


def escala_visible():
    """Escala con el rango de cada nivel, para la leyenda de la pantalla."""
    filas = []
    for indice, (umbral, texto, tono) in enumerate(ESCALA):
        if indice == 0:
            rango = f'≥ {int(umbral)}'
        elif umbral <= 0:
            rango = f'< {int(ESCALA[indice - 1][0])}'
        else:
            techo = f'{ESCALA[indice - 1][0] - 0.1:.1f}'.replace('.', ',')
            rango = f'{int(umbral)} – {techo}'
        filas.append({'texto': texto, 'tono': tono, 'rango': rango})
    return filas


def _mensaje_sin_datos(semana):
    if FUENTE_GUIA == 'guias' and semana > SEMANA_MAX_GUIA:
        return (f'La tabla genética solo tiene referencia hasta la semana '
                f'{SEMANA_MAX_GUIA}.')
    return f'La semana {semana} no tiene datos suficientes para calificar el lote.'


def evaluar(lote_id, semana, lote=None):
    """Devuelve la calificación del lote en esa semana."""
    fila = model.fetch_fila_lote_semana(lote_id, semana)
    if not fila:
        return {
            'status': 'sin_datos',
            'mensaje': f'El lote no tiene registro de la semana {semana}.',
        }

    variables = []
    avisos = []
    peso_disponible = 0.0
    acumulado = 0.0

    for clave, nombre, peso in PESOS:
        real = _real(clave, fila)
        guia = _referencia(clave, semana, fila)
        base = {
            'clave': clave,
            'nombre': nombre,
            'peso': round(peso * 100),
            'real': round(real, 2) if real is not None else None,
            'guia': round(guia, 2) if guia is not None else None,
            'unidad': _unidad(clave),
            'cumplimiento': None,
            'aporte': None,
        }

        # Las tres variables son acumuladas: un cero significa "sin registro".
        if real is None or real <= 0:
            variables.append({**base, 'estado': 'sin_dato', 'motivo': 'sin_real'})
            avisos.append(f'El lote no registra {nombre.lower()} en la semana {semana}.')
            continue

        if guia is None:
            variables.append({**base, 'estado': 'sin_dato', 'motivo': 'sin_guia'})
            avisos.append(
                f'La tabla genética no tiene {nombre.lower()} para la semana {semana}.'
            )
            continue

        bruto = _cumplimiento(clave, real, guia)
        if bruto is None:
            variables.append({**base, 'estado': 'sin_dato', 'motivo': 'sin_referencia'})
            avisos.append(f'No se pudo comparar {nombre.lower()} con la tabla genética.')
            continue

        cumplimiento = min(bruto, TOPE_CUMPLIMIENTO)
        if bruto > TOPE_CUMPLIMIENTO:
            avisos.append(
                f'{nombre}: el cumplimiento superó el tope de '
                f'{int(TOPE_CUMPLIMIENTO)} % y se ajustó.'
            )

        peso_disponible += peso
        acumulado += peso * cumplimiento

        if cumplimiento > 100.5:
            estado = 'mejor'
        elif cumplimiento < 99.5:
            estado = 'peor'
        else:
            estado = 'igual'

        variables.append({
            **base,
            'cumplimiento': round(cumplimiento, 1),
            'aporte': round(peso * cumplimiento, 2),
            'estado': estado,
        })

    if semana < SEMANA_MINIMA_CONV:
        return {
            'status': 'sin_datos',
            'mensaje': (
                f'La calificación se calcula a partir de la semana {SEMANA_MINIMA_CONV}: '
                'antes la conversión acumulada no es representativa.'
            ),
            'avisos': avisos,
        }

    # Sin HAA (la variable de mayor peso) el índice no es representativo.
    if peso_disponible < 0.60:
        return {
            'status': 'sin_datos',
            'mensaje': _mensaje_sin_datos(semana),
            'avisos': avisos,
        }

    indice = acumulado / peso_disponible
    parcial = any(v['estado'] == 'sin_dato' for v in variables)

    if parcial:
        avisos.append('El índice se calculó solo con las variables disponibles.')

    return {
        'status': 'ok',
        'lote': lote or {'id': lote_id},
        'semana': semana,
        'variables': variables,
        'indice': round(indice, 1),
        'calificacion': _etiqueta(indice),
        'parcial': parcial,
        'pesos_aplicados': round(peso_disponible * 100),
        'avisos': avisos,
        'fuente_guia': FUENTE_GUIA,
    }


def serie_general(lote_id):
    """
    Serie semanal del lote con los mismos datos del 'gráfico general'
    (producción, consumo, peso huevo y peso ave, real y tabla).
    """
    from models.semanal.services import get_data_grafico_general

    nombre = model.fetch_nombre_lote(lote_id)
    if not nombre:
        return {'semanas': [], 'series': {}}

    datos = get_data_grafico_general(nombre)
    if not datos or not datos.get('semanas'):
        return {'semanas': [], 'series': {}}

    semanas = []
    for texto in datos['semanas']:
        digitos = ''.join(c for c in str(texto) if c.isdigit())
        semanas.append(int(digitos) if digitos else None)

    series = {clave: valores for clave, valores in datos.items() if clave != 'semanas'}
    return {'lote': nombre, 'semanas': semanas, 'series': series}


def listar_lotes():
    """Lotes evaluables, en formato listo para el selector."""
    return [{
        'id': fila['id'],
        'lote': fila['lote'],
        'variedad': fila['variedad'] or '—',
        'aves': fila['no_aves_encasetadas'],
        'fecha_encasetamiento': _fecha(fila['fecha_encasetamiento']),
        'primera_semana': fila['primera_semana'],
        'ultima_semana': fila['ultima_semana'],
        'semanas': fila['semanas'],
    } for fila in model.fetch_lotes_evaluables()]


def listar_semanas(lote_id):
    """Semanas del lote que se pueden calificar con la tabla disponible."""
    semanas = [
        semana for semana in model.fetch_semanas_lote(lote_id)
        if semana >= SEMANA_MINIMA_CONV
    ]
    if FUENTE_GUIA == 'guias':
        return [semana for semana in semanas if semana <= SEMANA_MAX_GUIA]
    return semanas


def buscar_lote(lotes, lote_id):
    for fila in lotes:
        if fila['id'] == lote_id:
            return fila
    return None
