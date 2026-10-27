"""Lógica de Consolidados L+P: cálculos sobre datos de producción."""
from collections import Counter
from datetime import date, datetime
from models.consolidados import model
from models.consolidados import guias


def _clase_variedad(variedad) -> str:
    """Clase CSS segun la variedad del lote (para pintar el encabezado).

    LOHMANN -> naranja, HY LINE -> azul, cualquier otra -> sin clase.
    """
    v = (variedad or '').upper()
    if 'LOHMANN' in v:
        return 'lote-lohmann'
    if 'HY LINE' in v:
        return 'lote-hyline'
    return ''


def _aplicar_aves_enc_semana17(filas: list) -> list:
    """Reemplaza aves_enc en cada fila con el saldo_aves de data_diario semana 17.

    El encabezado AVES ENC de todas las vistas de consolidados debe mostrar
    el saldo de aves de la semana 17 (sem = '17') de la tabla DIARIO.
    """
    if not filas:
        return filas
    lotes = [f['lote'] for f in filas if f.get('lote')]
    if not lotes:
        return filas
    aves_enc_map = model.fetch_aves_enc_semana17(lotes)
    for f in filas:
        if f.get('lote') in aves_enc_map:
            f['aves_enc'] = aves_enc_map[f['lote']]
    return filas


def _a_num(valor):
    """Normaliza a float aceptando numeric, texto con coma o punto, o None."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (ValueError, AttributeError):
        return None


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
    # Asegurar que el rango llegue al menos hasta el dia 201
    if dia_max < 201:
        dia_max = 201

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

    # Rellenar dias faltantes en el rango [dia_min, dia_max] para que la tabla
    # muestre todos los dias aunque no haya datos en data_diario
    for d in range(dia_min, dia_max + 1):
        if d not in por_dia:
            por_dia[d] = {'semana': '', 'dia': d, 'celdas': {}}

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

    filas_raw = [por_dia[d] for d in sorted(por_dia.keys())]

    # Agrupar por semana para calcular rowspan y numero de semana
    from collections import OrderedDict
    semanas_ordenadas = OrderedDict()
    for f in filas_raw:
        # Extraer numero de semana entero de "14 + 5/7" -> 14
        sem_str = str(f['semana']) if f['semana'] else ''
        sem_num = int(sem_str.split(' ')[0]) if ' ' in sem_str else (int(sem_str) if sem_str.isdigit() else 0)
        f['sem_num'] = sem_num
        semanas_ordenadas.setdefault(sem_num, []).append(f)

    # Asignar span_sem (rowspan) a la primera fila de cada bloque
    for sem_num, filas_sem in semanas_ordenadas.items():
        filas_sem[0]['span_sem'] = len(filas_sem)

    # Clase de color por variedad (para pintar el nombre del lote)
    variedades = model.fetch_variedades_por_lote(lotes)
    clases = {l: _clase_variedad(variedades.get(l)) for l in lotes}

    # Reglas de color por porcentaje objetivo (fracción), en orden de prioridad.
    # Una celda solo recibe una clase: la primera regla que la "reclame".
    REGLAS_COLOR = [
        (0.01, 'celda-cerca-1pct'),   # 1% amarillo
        (0.05, 'celda-cerca-5pct'),   # 5% rosa
        (0.20, 'celda-cerca-20pct'),  # 20% azul claro
        (0.50, 'celda-cerca-50pct'),  # 50% azul oscuro
        (0.90, 'celda-cerca-90pct'),  # 90% verde claro
    ]

    # Inicializar clase de color vacía en cada celda
    for f in filas_raw:
        for lote in lotes:
            celda = f['celdas'].get(lote)
            if celda:
                celda['color_clase'] = ''

    # Asignar color a cada lote según cada regla (prioridad por orden)
    for target, clase in REGLAS_COLOR:
        for lote in lotes:
            mejor_idx = None
            mejor_diff = None
            for idx, f in enumerate(filas_raw):
                celda = f['celdas'].get(lote)
                if celda and celda.get('valor') is not None and celda.get('color_clase') == '':
                    diff = abs(celda['valor'] - target)
                    if mejor_diff is None or diff < mejor_diff:
                        mejor_diff = diff
                        mejor_idx = idx
            if mejor_idx is not None:
                filas_raw[mejor_idx]['celdas'][lote]['color_clase'] = clase

    return {
        'lotes': lotes,
        'indicadores': indicadores,
        'filas': filas_raw,
        'rango': {'min': dia_min, 'max': dia_max},
        'clases': clases,
    }


def get_huevos_semanal() -> dict:
    """Arma la matriz Semana x Lote de huevos semanales.

    Devuelve lotes ordenados, semanas ordenadas y matriz anidada
    {semana: {lote: valor o None}}.
    """
    filas = model.fetch_huevos_semanal()

    lotes = sorted({f['lote'] for f in filas if f['lote']})
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = f['prod_huevo_sem']

    return {'lotes': lotes, 'semanas': semanas, 'matriz': matriz}


def get_huevos_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote con metadata y totales por semana.

    Devuelve lotes (con fecha_enc y aves_enc), semanas, matriz anidada
    y totales (suma de lotes con dato, sin None).
    """
    filas = model.fetch_huevos_semanal_detalle()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = f['prod_huevo_sem']

    totales = {}
    for s in semanas:
        vals = [matriz[s].get(l) for l in lotes]
        vals = [v for v in vals if v is not None]
        totales[s] = sum(vals) if vals else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'totales': totales,
    }


def get_kilos_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote de kilos semanales (kg_sem).

    Misma estructura que huevos: metadata, matriz, totales y NRO
    (lotes incluidos con kilos > 0, calculado en el template por JS).
    """
    filas = model.fetch_kilos_semanal_detalle()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = f['kg_sem']

    totales = {}
    for s in semanas:
        vals = [matriz[s].get(l) for l in lotes]
        vals = [v for v in vals if v is not None]
        totales[s] = sum(vals) if vals else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'totales': totales,
    }


def get_mortalidad_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote de mortalidad semanal (mort_sem).

    Misma estructura que huevos/kilos: metadata, matriz, totales y NRO
    (lotes incluidos con bajas > 0, calculado en el template por JS).
    """
    filas = model.fetch_mortalidad_semanal_detalle()

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = f['mort_sem']

    totales = {}
    for s in semanas:
        vals = [matriz[s].get(l) for l in lotes]
        vals = [v for v in vals if v is not None]
        totales[s] = sum(vals) if vals else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'totales': totales,
    }


def get_peso_aves_detalle() -> dict:
    """Arma la matriz Semana x Lote de peso de aves (peso_ave_real).

    Incluye la columna TABLA (peso_ave_tab, guia de la estirpe por semana).
    El PROM se calcula en el template (promedio de incluidos con valor > 0).
    """
    filas = model.fetch_peso_aves()

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['peso_ave_real'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_PESO_AVE.get(s) for s in semanas},
    }


def get_consumo_agua_detalle() -> dict:
    """Arma la matriz Semana x Lote de consumo de agua (cons_agua_real).

    Igual que H6: columna PROM (promedio de incluidos > 0, calculado
    por JS) y columna TABLA (sin guia en el Excel, queda vacia).
    """
    filas = model.fetch_consumo_agua()

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['cons_agua_real'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {},
    }


def get_saldo_aves_detalle() -> dict:
    """Arma la matriz Semana x Lote de saldo de aves (saldo_ave).

    Misma estructura que huevos/kilos/mortalidad: metadata, matriz,
    totales y NRO (lotes incluidos con saldo > 0, calculado por JS).
    """
    filas = model.fetch_saldo_aves()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['saldo_ave'])

    totales = {}
    for s in semanas:
        vals = [matriz[s].get(l) for l in lotes]
        vals = [v for v in vals if v is not None]
        totales[s] = sum(vals) if vals else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'totales': totales,
    }


# Guia externa de % produccion por semana: ver guias.GUIA_PORC_PROD.


def get_porc_produccion_detalle() -> dict:
    """Arma la matriz Semana x Lote de % produccion (fracciones 0-1).

    Celda = porcentaje_prod_real / 100. PROM = media geometrica de los
    incluidos con valor > 0 (calculada por JS). TABLA = guia estatica.
    """
    filas = model.fetch_porc_produccion()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        v = _a_num(f['porcentaje_prod_real'])
        matriz[f['sem_prod']][f['lote']] = (v / 100.0) if v is not None else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_PORC_PROD.get(s) for s in semanas},
    }


# Guia externa de % mortalidad: ver guias.GUIA_MORT_ACUM.


def get_mort_acumulada_detalle() -> dict:
    """Arma la matriz Semana x Lote de % mortalidad acumulada.

    Celda = percent_mort_acum / 100 (fraccion). PROM = promedio
    aritmetico de incluidos (calculado por JS). TABLA = guia estatica.
    """
    filas = model.fetch_mort_acumulada()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        v = _a_num(f['percent_mort_acum'])
        matriz[f['sem_prod']][f['lote']] = (v / 100.0) if v is not None else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_MORT_ACUM.get(s) for s in semanas},
    }


# Serie de referencia de H10: ver guias.GUIA_MORT_SEM.


def get_mort_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote de mortalidad semanal.

    Celda = mort_sem de bd_vargas (numero de aves muertas, NO porcentaje).
    PROM = promedio aritmetico de incluidos (calculado por JS). TABLA = serie estatica.
    """
    filas = model.fetch_mort_semanal()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        v = _a_num(f['percent_mort_sem'])
        matriz[f['sem_prod']][f['lote']] = (v / 100.0) if v is not None else None

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_MORT_SEM.get(s) for s in semanas},
    }


def get_haa_detalle() -> dict:
    """Arma la matriz Semana x Lote de huevos ave alojada (h_av_aloj_real).

    TABLA = h_av_aloj_tab de BD (guia de la estirpe). PROM = promedio
    aritmetico de incluidos (calculado por JS).
    """
    filas = model.fetch_haa()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    tabla = {}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['h_av_aloj_real'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_HAA_TAB.get(s) for s in semanas},
    }


def _gramos_ave_dia(kg_sem, saldo_ave):
    """Gramos por ave por dia: (kg_sem / 7) / saldo_ave * 1000, a 1 decimal. None si no se puede calcular."""
    kg = _a_num(kg_sem)
    saldo = _a_num(saldo_ave)
    if kg is None or not saldo:
        return None
    return round((kg / 7.0) / saldo * 1000.0, 1)


def get_gramos_aves_detalle() -> dict:
    """Arma la matriz Semana x Lote de gramos/ave/dia.

    Celda = (kg_sem / 7) / saldo_ave * 1000 (misma formula de la hoja H13 del Excel).
    Si falta kg_sem o saldo_ave, o el saldo es 0, la celda queda vacia.
    PROM = promedio aritmetico de incluidos (calculado por JS).
    TABLA = guia estatica externa.
    """
    filas = model.fetch_gramos_aves()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _gramos_ave_dia(f['kg_sem'], f['saldo_ave'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_GRAMOS_AVES.get(s) for s in semanas},
    }


def get_conv_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote de conversion semanal.

    Celda = conv_sem_real. TABLA = guia de estirpe (guias.py).
    PROM = promedio aritmetico de incluidos (calculado por JS).
    """
    filas = model.fetch_conv_semanal()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['conv_sem_real'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_CONV_SEM_TAB.get(s) for s in semanas},
    }


def get_conv_acumulada_detalle() -> dict:
    """Arma la matriz Semana x Lote de conversion acumulada.

    Celda = conv_acum_real. TABLA = guia de estirpe (guias.py).
    PROM = promedio aritmetico de incluidos (calculado por JS).
    """
    filas = model.fetch_conversion_acumulada()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    tabla = {}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['conv_acum_real'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_CONV_ACUM_TAB.get(s) for s in semanas},
    }


def get_masa_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote de masa de huevo semanal.

    Calculado segun Excel H16:
    - Semana 18: masa = produccion * huevo_acum (misma semana)
    - Semana n > 18: si produccion=0 -> None; si no: masa = produccion * (huevo_acum_n - huevo_acum_{n-1})
    TABLA = guia de estirpe (guias.py). PROM = promedio aritmetico (calculado por JS).
    """
    filas = model.fetch_masa_semanal()
    filas = _aplicar_aves_enc_semana17(filas)

    # Organizar por lote y semana para calcular diferencias de huevo_acum
    lotes_data = {}
    for f in filas:
        lote = f['lote']
        sem = f['sem_prod']
        if lote is None or sem is None:
            continue
        lotes_data.setdefault(lote, {})[sem] = {
            'produccion': _a_num(f['prod_huevo_real']),
            'huevo_acum': _a_num(f['huevo_acum']),
        }

    # Calcular masa semanal por lote y semana
    masa_por_lote_semana = {}
    for lote, semanas_data in lotes_data.items():
        semanas_ordenadas = sorted(semanas_data.keys())
        masa_por_lote_semana[lote] = {}
        for i, sem in enumerate(semanas_ordenadas):
            datos = semanas_data[sem]
            prod = datos['produccion']
            haa = datos['huevo_acum']
            if prod is None or haa is None:
                masa_por_lote_semana[lote][sem] = None
                continue
            if sem == 18:
                # Semana 18: masa = produccion * huevo_acum (misma semana)
                masa_por_lote_semana[lote][sem] = prod * haa
            else:
                # Semana n > 18: si produccion=0 -> None
                if prod == 0:
                    masa_por_lote_semana[lote][sem] = None
                else:
                    # Buscar huevo_acum de la semana anterior
                    semana_anterior = None
                    for s_prev in semanas_ordenadas[:i]:
                        if isinstance(s_prev, int) and s_prev == sem - 1:
                            semana_anterior = s_prev
                            break
                    # Si no hay semana anterior numerica exacta, buscar la anterior disponible
                    if semana_anterior is None:
                        # Buscar cualquier semana anterior disponible
                        semanas_numericas = [s for s in semanas_ordenadas[:i] if isinstance(s, int)]
                        if semanas_numericas:
                            semana_anterior = semanas_numericas[-1]
                    if semana_anterior is not None:
                        haa_anterior = semanas_data[semana_anterior]['huevo_acum']
                        if haa_anterior is not None:
                            masa_por_lote_semana[lote][sem] = prod * (haa - haa_anterior)
                        else:
                            masa_por_lote_semana[lote][sem] = None
                    else:
                        masa_por_lote_semana[lote][sem] = None

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for sem in semanas:
        for lote in lotes:
            matriz[sem][lote] = masa_por_lote_semana.get(lote, {}).get(sem)

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_MASA_SEM.get(s) for s in semanas},
    }


def get_masa_acumulada_detalle() -> dict:
    """Arma la matriz Semana x Lote de masa de huevo acumulada.

    Celda = masa_huevo_real_acum. TABLA = masa_huevo_tab_acum de BD.
    PROM = promedio aritmetico de incluidos (calculado por JS).
    """
    filas = model.fetch_masa_acumulada()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    tabla = {}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['masa_huevo_real_acum'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_MASA_ACUM.get(s) for s in semanas},
    }


def get_primera_semana_levante_detalle() -> dict:
    """Arma las 4 matrices Dia (0-7) x Lote de H18.

    peso (con TABLA viva), uniformidad, consumo (con guia estatica)
    y mortalidad diaria. PROM aritmetico por JS en las 4.
    """
    filas = model.fetch_primera_semana_levante()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    dias = sorted({f['dia'] for f in filas if f['dia'] is not None})

    def matriz_de(clave):
        m = {d: {} for d in dias}
        for f in filas:
            if f['dia'] is None or not f['lote']:
                continue
            m[f['dia']][f['lote']] = _a_num(f[clave])
        return m

    tabla_peso = {d: guias.GUIA_PESO_DIA.get(d) for d in dias}

    return {
        'lotes': [meta[l] for l in lotes],
        'dias': dias,
        'peso': {'matriz': matriz_de('peso_real'), 'tabla': tabla_peso},
        'unif': {'matriz': matriz_de('porc_uniformidad'), 'tabla': {}},
        'consumo': {'matriz': matriz_de('consumo_gr_a_d'), 'tabla': dict(guias.GUIA_CONSUMO_DIA)},
        'mort': {'matriz': matriz_de('mortalidad'), 'tabla': {}},
        # Compatibilidad con el template actual (usa matriz/tabla de peso)
        'matriz': matriz_de('peso_real'),
        'tabla': tabla_peso,
    }


def _pct(real, tab):
    if real is None or tab is None:
        return None
    try:
        if float(tab) == 0:
            return None
        return round(float(real) / float(tab) * 100, 1)
    except (TypeError, ValueError):
        return None


def get_datos_levante(lotes_param=None) -> dict:
    """Arma la vista Datos de Levante.

    lotes_param: lista de lotes a incluir (None = todos).
    Devuelve lotes (con ON/OFF), serie consolidada semanal y
    matriz de consumo Semana x Lote.
    """
    todos = model.fetch_levante_lotes()
    todos = _aplicar_aves_enc_semana17(todos)
    nombres = [t['lote'] for t in todos]
    # Sin parametro (primera visita): ningun lote seleccionado.
    if not lotes_param:
        lotes = []
    else:
        sel = [l for l in lotes_param if l in nombres]
        lotes = sel

    iniciales = 0
    for t in todos:
        if t['lote'] in lotes:
            v = _a_num(t['aves_enc'])
            if v:
                iniciales += v

    serie = []
    for f in model.fetch_levante_consolidado(lotes):
        sem = f['sem']
        peso_tab = guias.GUIA_LEV_PESO_TAB.get(sem)
        grad_tab = guias.GUIA_LEV_GRAD_TAB.get(sem)
        serie.append({
            'sem': sem,
            'peso_real': _a_num(f['peso_real']),
            'peso_tab': peso_tab,
            'pct_peso': _pct(f['peso_real'], peso_tab),
            'ganancia': _a_num(f['ganancia_ave']),
            'ganancia_tab': guias.GUIA_LEV_GAN_TAB.get(sem),
            'unif': _a_num(f['unif']),
            'grad_real': _a_num(f['grad_real']),
            'grad_tab': grad_tab,
            'pct_grad': _pct(f['grad_real'], grad_tab),
            'cons_acum': _a_num(f['cons_acum']),
            'cons_tab': guias.GUIA_LEV_CONS_TAB.get(sem),
            'conv_real': _a_num(f['conv_real']),
            'conv_tab': guias.GUIA_LEV_CONV_TAB.get(sem),
            'mort': _a_num(f['mort']),
            'mort_acum': _a_num(f['mort_acum']),
            'saldo': _a_num(f['saldo']),
            'nro': f['nro'],
            'viab': round(f['saldo'] / iniciales * 100, 2) if f['saldo'] is not None and iniciales else None,
        })

    consumo_filas = model.fetch_levante_consumo(lotes)
    semanas = sorted({f['sem'] for f in consumo_filas if f['sem'] is not None})
    matriz = {s: {} for s in semanas}
    for f in consumo_filas:
        if f['sem'] is None or not f['lote']:
            continue
        matriz[f['sem']][f['lote']] = _a_num(f['consumo'])

    return {
        'todos': [{'nombre': t['lote'], 'activo': t['lote'] in lotes} for t in todos],
        'lotes': lotes,
        'serie': serie,
        'consumo': {'semanas': semanas, 'matriz': matriz},
    }


def get_peso_huevo_detalle() -> dict:
    """Arma la matriz Semana x Lote de peso de huevo (peso_huevo_real).

    Sin columna TABLA (la hoja no trae guia). PROM = promedio
    aritmetico de incluidos (calculado por JS).
    """
    filas = model.fetch_peso_huevo()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['peso_huevo_real'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
    }


def get_rotura_huevo_detalle() -> dict:
    """Arma la matriz Semana x Lote de % rotura (columna roto, ya en %).

    Sin TABLA (la hoja no trae guia). PROM = promedio de incluidos.
    Incluye solo lotes con al menos un dato no nulo.
    """
    filas = model.fetch_rotura_huevo()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    con_dato = {f['lote'] for f in filas if f['lote'] and _a_num(f['roto']) is not None}
    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['roto'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'con_dato': sorted(con_dato),
    }


def get_acumulados_clasificadora_detalle(categoria: str = 'SEGUNDAS') -> dict:
    """Arma la matriz Semana x Lote del % de la categoria elegida.

    Categoria validada contra whitelist de model. Sin TABLA.
    PROM = promedio de incluidos (calculado por JS).
    """
    from models.consolidados.model import CATEGORIAS_CLASIFICACION
    if categoria not in CATEGORIAS_CLASIFICACION:
        categoria = 'SEGUNDAS'
    filas = model.fetch_acumulados_clasificadora(categoria)
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    con_dato = {f['lote'] for f in filas if f['lote'] and _a_num(f['valor']) is not None}
    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['valor'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'con_dato': sorted(con_dato),
        'categoria': categoria,
        'categorias': sorted(CATEGORIAS_CLASIFICACION.keys()),
    }


def get_uniformidad_detalle() -> dict:
    """Arma la matriz Semana x Lote de % uniformidad (columna unif).

    Sin TABLA (la hoja no trae guia). PROM = promedio de incluidos.
    """
    filas = model.fetch_uniformidad()

    meta = {}
    for f in filas:
        if f['lote'] and f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}
    for f in filas:
        if f['sem_prod'] is None or not f['lote']:
            continue
        matriz[f['sem_prod']][f['lote']] = _a_num(f['unif'])

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
    }
