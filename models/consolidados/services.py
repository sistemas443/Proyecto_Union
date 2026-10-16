"""Lógica de Consolidados L+P: cálculos sobre datos de producción."""
from collections import Counter
from datetime import date, datetime
from models.consolidados import model


def _a_fecha(valor):
    """Normaliza a date aceptando date, datetime o texto 'YYYY-MM-DD'."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        anio, mes, dia = map(int, str(valor).strip()[:10].split('-'))
        return date(anio, mes, dia)
    except (ValueError, AttributeError):
        return None


def get_distribucion_primer_huevo() -> dict:
    """Calcula la distribución de edad (en semanas de vida) al primer huevo.

    semana = floor(días desde recepción / 7) + 1.
    Devuelve distribución + total + lotes excluidos (sin datos suficientes).
    """
    filas = model.fetch_primer_huevo_por_lote()

    edades = []
    excluidos = []
    for f in filas:
        fecha_huevo = _a_fecha(f['fecha_primer_huevo'])
        fecha_base = _a_fecha(f['fecha_recepcion'])
        if fecha_huevo is None or fecha_base is None:
            excluidos.append(f['lote'])
            continue
        edad_dias = (fecha_huevo - fecha_base).days
        if edad_dias < 0:
            excluidos.append(f['lote'])
            continue
        edades.append((f['lote'], edad_dias // 7 + 1))

    conteo = Counter(semana for _, semana in edades)
    total = sum(conteo.values())
    distribucion = [
        {
            'edad_semana': semana,
            'frecuencia': freq,
            'porcentaje': round(freq / total * 100, 1) if total else 0.0,
        }
        for semana, freq in sorted(conteo.items())
    ]

    return {
        'distribucion': distribucion,
        'total_lotes': total,
        'excluidos': sorted(excluidos),
    }


def get_matriz_primer_huevo() -> dict:
    """Arma la matriz Semana/Dia x Lote para la vista Primer Huevo.

    Rango dinamico de dias: [min_primer - 7, max_primer + 21].
    Celda con valor = produccion/saldo_aves (6 decimales) o None.
    Celda con es_primer = dia de primer huevo del lote.
    Incluye los 4 indicadores por lote (ultimo dato valido).
    """
    primeros = model.fetch_primer_dia_por_lote()
    dia_primer = {p['lote']: p['dia_primer'] for p in primeros if p['dia_primer'] is not None}
    if not dia_primer:
        return {'lotes': [], 'indicadores': [], 'filas': [], 'rango': None}

    dia_min = min(dia_primer.values()) - 7
    dia_max = max(dia_primer.values()) + 21

    filas_db = model.fetch_matriz_dias(dia_min, dia_max)

    por_dia = {}
    for f in filas_db:
        clave = (f['sem'], f['dias'])
        celda = por_dia.setdefault(f['dias'], {'semana': f['sem'], 'dia': f['dias'], 'celdas': {}})
        if f['produccion'] and f['saldo_aves']:
            try:
                celda['celdas'][f['lote']] = {
                    'valor': round(float(f['produccion']) / float(f['saldo_aves']), 6),
                    'es_primer': f['dias'] == dia_primer.get(f['lote']),
                }
            except (TypeError, ValueError, ZeroDivisionError):
                celda['celdas'][f['lote']] = {'valor': None, 'es_primer': False}
        else:
            celda['celdas'][f['lote']] = {
                'valor': None,
                'es_primer': f['dias'] == dia_primer.get(f['lote']),
            }

    indicadores_db = {r['lote']: r for r in model.fetch_ultimos_indicadores_por_lote()}
    lotes = sorted(dia_primer.keys())
    def col_ind(clave):
        return {l: (indicadores_db.get(l) or {}).get(clave) for l in lotes}
    indicadores = [
        {'nombre': 'HAA', 'sufijo': '', 'valores': col_ind('haa_real')},
        {'nombre': 'G/Huevo', 'sufijo': '', 'valores': col_ind('gr_por_huevo')},
        {'nombre': 'G/Ave', 'sufijo': '', 'valores': col_ind('gr_ave_dia_graf')},
        {'nombre': 'Mortalidad', 'sufijo': '%', 'valores': col_ind('porcentaje_mort_acum_graf')},
    ]

    return {
        'lotes': lotes,
        'indicadores': indicadores,
        'filas': [por_dia[d] for d in sorted(por_dia.keys())],
        'rango': {'min': dia_min, 'max': dia_max},
    }
