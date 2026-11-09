"""Lógica de Consolidados L+P: cálculos sobre datos de producción."""
import functools
from collections import Counter
from datetime import date, datetime
from models.consolidados import model
from models.consolidados import guias
from models.lotes import clasificacion as lotes_clasificacion


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


def _aves_enc_haa(filas: list) -> dict:
    """Base de aves encasetadas para H12, H16 y H17.

    Prioridad:
    1. no_aves_encasetadas de la ficha del lote (el AVES ENC editable).
    2. saldo de aves de la semana 17 en data_diario.
    3. no_pollitas_recibidas de la ficha.
    """
    if not filas:
        return {}
    lotes = [f['lote'] for f in filas if f.get('lote')]
    if not lotes:
        return {}
    aves17 = model.fetch_aves_enc_semana17(lotes)
    mapa = {}
    for f in filas:
        lote = f.get('lote')
        if not lote or lote in mapa:
            continue
        base = _a_num(f.get('aves_enc_lote'))
        if not base:
            base = _a_num(aves17.get(lote))
        if not base:
            base = _a_num(f.get('aves_enc'))
        mapa[lote] = base
    return mapa


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


# ---------------------------------------------------------------------------
# Depuración común de las matrices de consolidados
# ---------------------------------------------------------------------------

def _meta_todos_los_lotes() -> dict:
    """Metadata de todos los lotes registrados, tengan o no datos."""
    meta = {}
    for f in model.fetch_todos_los_lotes():
        fecha = f['fecha_recepcion']
        meta[f['lote']] = {
            'nombre': f['lote'],
            'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
            'aves_enc': f['aves_enc'],
        }
    return meta


def _cortes_produccion() -> dict:
    """{lote: última semana con producción real} para recortar las series."""
    return {f['lote']: f['sem'] for f in model.fetch_ultima_semana_por_lote()}


def _limpiar_matriz(matriz: dict, nombres: list, cortes: dict) -> None:
    """Pone en blanco los ceros y corta después de la última fila con datos."""
    for clave, fila in matriz.items():
        for nombre in nombres:
            if nombre not in fila:
                continue
            valor = fila[nombre]
            if valor is None:
                continue
            if valor == 0:
                fila[nombre] = None
                continue
            corte = cortes.get(nombre)
            if corte is not None and isinstance(clave, (int, float)) and clave > corte:
                fila[nombre] = None


def _depurar(datos: dict, cortes: dict = None, eje: str = 'semanas') -> dict:
    """Deja las matrices de consolidados listas para mostrar.

    - Agrega todos los lotes registrados, aunque no tengan datos cargados.
    - Un 0 significa "sin dato": se muestra vacío.
    - Recorta cada lote en su última semana (o día) con datos reales, para que
      no se repitan los valores que quedaron arrastrados en el Excel.
    - Recalcula los totales y ajusta las guías a las filas que quedan.
    """
    if not isinstance(datos, dict) or 'lotes' not in datos:
        return datos

    cortes = cortes or {}

    # 1. Todos los lotes
    meta_cabecera = _meta_todos_los_lotes()
    meta = {l['nombre']: l for l in datos['lotes']}
    for nombre, datos_lote in meta_cabecera.items():
        meta.setdefault(nombre, datos_lote)
    nombres = sorted(meta.keys())
    datos['lotes'] = [meta[n] for n in nombres]

    # 2. Matrices: la principal y las anidadas de primera semana
    matrices = []
    if isinstance(datos.get('matriz'), dict):
        matrices.append(datos['matriz'])
    for clave in ('peso', 'unif', 'consumo', 'mort'):
        bloque = datos.get(clave)
        if isinstance(bloque, dict) and isinstance(bloque.get('matriz'), dict):
            matrices.append(bloque['matriz'])
    for matriz in matrices:
        _limpiar_matriz(matriz, nombres, cortes)

    # 3. Se recortan las filas del final. Si hay corte de producción se usa ese
    #    límite (así todas las vistas muestran el mismo rango de semanas); si no,
    #    se corta en la última fila con datos de la propia vista.
    claves = datos.get(eje)
    if isinstance(claves, list) and matrices:
        if cortes:
            limite = max(cortes.values())
            datos[eje] = [c for c in claves
                          if not isinstance(c, (int, float)) or c <= limite]
        else:
            principal = matrices[0]
            ultima = None
            for clave in claves:
                fila = principal.get(clave) or {}
                if any(fila.get(n) is not None for n in nombres):
                    ultima = clave
            datos[eje] = [c for c in claves if ultima is not None and c <= ultima] if ultima is not None else []

    # 4. Guías y totales alineados a las filas que quedan
    claves = datos.get(eje) or []
    if isinstance(datos.get('tabla'), dict):
        datos['tabla'] = {c: datos['tabla'].get(c) for c in claves}
    for clave in ('peso', 'unif', 'consumo', 'mort'):
        bloque = datos.get(clave)
        if isinstance(bloque, dict) and isinstance(bloque.get('tabla'), dict):
            bloque['tabla'] = {c: bloque['tabla'].get(c) for c in claves}

    if isinstance(datos.get('totales'), dict) and matrices:
        principal = matrices[0]
        totales = {}
        for clave in claves:
            fila = principal.get(clave) or {}
            valores = [fila.get(n) for n in nombres if fila.get(n) is not None]
            totales[clave] = sum(valores) if valores else None
        datos['totales'] = totales

    return datos


def _depurar_vista(eje: str = 'semanas', con_cortes: bool = True):
    """Decorador que aplica `_depurar` al resultado de una vista."""
    def decorador(func):
        @functools.wraps(func)
        def envoltura(*args, **kwargs):
            datos = func(*args, **kwargs)
            cortes = _cortes_produccion() if con_cortes else {}
            return _depurar(datos, cortes=cortes, eje=eje)
        return envoltura
    return decorador


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
    """Arma la matriz Semana x Lote de consumo de agua por ave (Excel H7).

    H7 = INDEX(DIARIO!N:N, dia + 7): toma el consumo de agua del ultimo dia
    de la semana (dia = semana * 7), lo divide entre el saldo de aves y lo
    multiplica por 1000, igual que la columna N del DIARIO.
    La columna TABLA esta vacia en el Excel y PROM es el promedio de los
    lotes incluidos con valor > 0 (calculado por JS).
    """
    filas = model.fetch_masa_semanal()
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

    # Consumo por ave del ultimo dia de cada semana (dia = semana x 7)
    for f in model.fetch_masa_semanal_agua(lotes):
        semana = f['dias'] // 7
        consumo = _a_num(f['consumo_agua'])
        saldo = _a_num(f['saldo_aves'])
        if not consumo or not saldo:
            continue
        if semana in matriz and f['lote'] in meta:
            matriz[semana][f['lote']] = round(consumo * 1000.0 / saldo, 4)

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
    """Arma la matriz Semana x Lote de huevos ave alojada (Excel H12).

    - Semana 18: huevos de la semana 18 / aves encasetadas.
    - Semana 19 en adelante: si los huevos de la semana son 0 queda vacio;
      si no, huevos acumulados desde la semana 18 / aves encasetadas.

    Las aves encasetadas son el AVES ENC de la ficha del lote y, si está
    vacío, el saldo de aves de la semana 17. TABLA = guia de la estirpe.
    PROM = promedio aritmetico de incluidos (calculado por JS).
    """
    filas = model.fetch_haa()
    aves_enc = _aves_enc_haa(filas)

    meta = {}
    for f in filas:
        if not f['lote'] or f['lote'] in meta:
            continue
        fecha = f['fecha_recepcion']
        meta[f['lote']] = {
            'nombre': f['lote'],
            'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
            'aves_enc': aves_enc.get(f['lote']),
        }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})

    # Huevos producidos por lote y semana
    huevos_por_lote = {}
    for f in filas:
        if f['lote'] and f['sem_prod'] is not None:
            huevos_por_lote.setdefault(f['lote'], {})[f['sem_prod']] = _a_num(f['huevos']) or 0.0

    matriz = {s: {} for s in semanas}

    for lote in lotes:
        base = aves_enc.get(lote) or 0
        acum_huevos = 0.0
        for sem in sorted(huevos_por_lote.get(lote, {})):
            huevos = huevos_por_lote[lote][sem]
            acum_huevos += huevos

            if not base:
                valor = None
            elif sem == 18:
                # Semana 18: solo los huevos de esa semana
                valor = huevos / base
            elif huevos == 0:
                # Semana sin produccion: la celda queda vacia
                valor = None
            else:
                # Semana 19 en adelante: acumulado desde la semana 18
                valor = acum_huevos / base

            matriz[sem][lote] = valor

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
    """Arma la matriz Semana x Lote de conversion acumulada, igual que el Excel H15.

    - Semana 18: el mismo valor de la conversion semanal (hoja H14).
    - Semana 19 en adelante: si los kilos de esa semana son 0 queda vacio; si no,
      (kilos acumulados desde la semana 18) / (huevos acumulados) * 12.
    TABLA = guia de estirpe (guias.py). PROM = promedio de incluidos (JS).
    """
    filas = model.fetch_conversion_acumulada()
    filas = _aplicar_aves_enc_semana17(filas)

    meta = {}
    por_lote = {}
    for f in filas:
        if not f['lote']:
            continue
        if f['lote'] not in meta:
            fecha = f['fecha_recepcion']
            meta[f['lote']] = {
                'nombre': f['lote'],
                'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
                'aves_enc': f['aves_enc'],
            }
        por_lote.setdefault(f['lote'], []).append(f)

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})
    matriz = {s: {} for s in semanas}

    for lote, lista in por_lote.items():
        lista = sorted(lista, key=lambda x: x['sem_prod'])
        acum_kg = 0.0
        acum_huevos = 0.0
        primera = True

        for f in lista:
            sem = f['sem_prod']
            if sem is None:
                continue

            kg = _a_num(f['kg_sem']) or 0.0
            huevos = _a_num(f['prod_huevo_sem']) or 0.0
            acum_kg += kg
            acum_huevos += huevos

            if primera:
                # La primera semana (18) es la conversion semanal
                valor = _a_num(f['conv_sem_real'])
                primera = False
            elif kg == 0 or acum_huevos <= 0:
                # Sin kilos en la semana, o sin huevos acumulados: queda vacio
                valor = None
            else:
                valor = round((acum_kg / acum_huevos) * 12, 3)

            matriz[sem][lote] = valor

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_CONV_ACUM_TAB.get(s) for s in semanas},
    }


def get_masa_semanal_detalle() -> dict:
    """Arma la matriz Semana x Lote de masa de huevo semanal (Excel H16).

    - Semana 18: consumo de agua por ave de la semana x huevos por ave alojada
      de esa misma semana.
    - Semana 19 en adelante: si el consumo de agua de la semana es 0 queda vacío;
      si no, consumo de agua por ave x (huevos por ave alojada de la semana).

    El consumo de agua y los huevos por ave salen del día 7 de cada semana:
    agua del día / saldo de aves para el agua, y huevos acumulados desde la
    semana 18 entre el AVES ENC de la ficha del lote (o el saldo de aves de
    la semana 17 si está vacío). Si tampoco hay, se usa no_pollitas_recibidas.
    """
    filas = model.fetch_masa_semanal()
    aves_enc = _aves_enc_haa(filas)

    meta = {}
    for f in filas:
        if not f['lote'] or f['lote'] in meta:
            continue
        fecha = f['fecha_recepcion']
        meta[f['lote']] = {
            'nombre': f['lote'],
            'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
            'aves_enc': aves_enc.get(f['lote']),
        }

    lotes = sorted(meta.keys())
    semanas = sorted({f['sem_prod'] for f in filas if f['sem_prod'] is not None})

    # Consumo de agua por ave del último día de cada semana (día = semana x 7)
    agua = {}
    for f in model.fetch_masa_semanal_agua(lotes):
        semana = f['dias'] // 7
        consumo = _a_num(f['consumo_agua'])
        saldo = _a_num(f['saldo_aves'])
        if consumo and saldo:
            agua.setdefault(f['lote'], {})[semana] = round(consumo * 1000.0 / saldo, 4)

    # Huevos producidos por lote y semana
    huevos_por_lote = {}
    for f in filas:
        if f['lote'] and f['sem_prod'] is not None:
            huevos_por_lote.setdefault(f['lote'], {})[f['sem_prod']] = _a_num(f['huevos']) or 0.0

    matriz = {s: {} for s in semanas}

    for lote in lotes:
        total_aves = aves_enc.get(lote) or 0
        por_semana = huevos_por_lote.get(lote, {})
        acum_huevos = 0.0
        haa_anterior = None
        primera = True

        for sem in sorted(por_semana.keys()):
            acum_huevos += por_semana[sem]
            haa = (acum_huevos / total_aves) if total_aves else None
            h7 = agua.get(lote, {}).get(sem)

            if primera:
                masa = (h7 * haa) if (h7 is not None and haa is not None) else None
                primera = False
            elif h7 in (None, 0) or haa is None or haa_anterior is None:
                masa = None
            else:
                masa = h7 * (haa - haa_anterior)

            matriz[sem][lote] = masa
            haa_anterior = haa

    return {
        'lotes': [meta[l] for l in lotes],
        'semanas': semanas,
        'matriz': matriz,
        'tabla': {s: guias.GUIA_MASA_SEM.get(s) for s in semanas},
    }


def get_masa_acumulada_detalle() -> dict:
    """Arma la matriz Semana x Lote de masa de huevo acumulada (Excel H17).

    Es la suma de la masa semanal desde la semana 18. Si la semana no tiene
    masa, la acumulada también queda vacía.
    """
    semanal = get_masa_semanal_detalle()
    lotes = semanal['lotes']
    semanas = semanal['semanas']
    nombres = [l['nombre'] for l in lotes]

    matriz = {}
    acumulados = {}
    for sem in semanas:
        matriz[sem] = {}
        for lote in nombres:
            valor = semanal['matriz'].get(sem, {}).get(lote)
            if valor is None:
                matriz[sem][lote] = None
                continue
            acumulados[lote] = acumulados.get(lote, 0.0) + valor
            matriz[sem][lote] = acumulados[lote]

    return {
        'lotes': lotes,
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


def _sin_cero(valor):
    """Un 0 significa "sin dato": se devuelve None para que salga vacío."""
    if valor is None:
        return None
    try:
        return None if float(valor) == 0 else valor
    except (TypeError, ValueError):
        return valor


# Variables de la serie semanal de levante (hoja H19).
VARIABLES_LEVANTE = (
    {'id': 'grad', 'titulo': 'Gr.A.D.', 'clave': 'grad_real',
     'decimales': 1, 'tabla': guias.GUIA_LEV_GRAD_TAB},
    {'id': 'peso', 'titulo': 'Peso', 'clave': 'peso_real',
     'decimales': 1, 'tabla': guias.GUIA_LEV_PESO_TAB},
    {'id': 'unif', 'titulo': 'Uniformidad', 'clave': 'unif',
     'decimales': 2, 'tabla': {}},
    {'id': 'mort_acum', 'titulo': '% Mort. acumulada', 'clave': 'mort_acum',
     'decimales': 2, 'tabla': {}},
    {'id': 'mort_sem', 'titulo': 'Mortalidad semanal', 'clave': 'mort_sem',
     'decimales': 2, 'tabla': {}},
    {'id': 'aves', 'titulo': 'N.° aves', 'clave': 'aves',
     'decimales': 0, 'tabla': {}},
)


def get_datos_levante(variables_param=None, lotes_param=None) -> dict:
    """Arma la vista Datos de Levante con una matriz Semana x Lote por variable.

    variables_param: ids de las variables a mostrar (None = todas).
    lotes_param: lotes de la matriz de consumo (None = todos).
    La serie semanal siempre muestra todos los lotes como columnas.
    """
    todos = model.fetch_levante_lotes()

    # Se agregan los lotes registrados que todavía no tienen datos de levante,
    # para que aparezcan como columnas aunque estén vacíos.
    existentes = {t['lote'] for t in todos}
    for nombre, meta in _meta_todos_los_lotes().items():
        if nombre not in existentes:
            todos.append({
                'lote': nombre,
                'fecha_recepcion': meta.get('fecha_enc'),
                'aves_enc': meta.get('aves_enc'),
            })
    todos.sort(key=lambda t: t['lote'])
    todos = _aplicar_aves_enc_semana17(todos)

    nombres = [t['lote'] for t in todos]

    # Serie semanal de cada lote por separado, sin consolidar
    filas_por_lote = {}
    for f in model.fetch_levante_por_lote(nombres):
        filas_por_lote.setdefault(f['lote'], []).append(f)

    # Fila del día 0 de cada lote (viene de primera_semana)
    dia0_por_lote = {f['lote']: f for f in model.fetch_primera_semana_dia0(nombres)}

    filas_lote = {}
    for nombre in nombres:
        filas = []

        # Día 0: día de recepción, tomado de la tabla primera_semana
        dia0 = dia0_por_lote.get(nombre)
        if dia0:
            filas.append({
                'sem': 0,
                'grad_real': None,
                'peso_real': _sin_cero(_a_num(dia0['peso_real'])),
                'unif': _sin_cero(_a_num(dia0['unif'])),
                'mort_acum': _sin_cero(_a_num(dia0['mort_acum'])),
                'mort_sem': None,
                'aves': _sin_cero(_a_num(dia0['saldo'])),
            })

        # La mortalidad semanal sale de la diferencia del % acumulado:
        # la semana 1 repite el acumulado y de la 2 en adelante se resta la anterior.
        acum_anterior = None
        es_primera_semana = True

        for f in filas_por_lote.get(nombre, []):
            acum = _a_num(f['mort_acum'])

            if es_primera_semana:
                mort_sem = acum
            elif acum is not None and acum_anterior is not None:
                mort_sem = round(acum - acum_anterior, 2)
            else:
                mort_sem = None

            es_primera_semana = False
            if acum is not None:
                acum_anterior = acum

            filas.append({
                'sem': f['sem'],
                'grad_real': _sin_cero(_a_num(f['grad_real'])),
                'peso_real': _sin_cero(_a_num(f['peso_real'])),
                'unif': _sin_cero(_a_num(f['unif'])),
                'mort_acum': _sin_cero(acum),
                'mort_sem': _sin_cero(mort_sem),
                'aves': _sin_cero(_a_num(f['saldo'])),
            })

        # Se recortan las semanas del final que quedaron sin ningún dato
        claves = ('grad_real', 'peso_real', 'unif', 'mort_acum', 'aves')
        ultima = None
        for i, fila in enumerate(filas):
            if any(fila[k] is not None for k in claves):
                ultima = i
        if ultima is not None:
            filas = filas[:ultima + 1]
        else:
            filas = []

        filas_lote[nombre] = filas

    semanas = sorted({fila['sem'] for filas in filas_lote.values() for fila in filas})

    # Variables seleccionadas (None = todas; lista vacía = ninguna)
    if variables_param is None:
        seleccion = [v['id'] for v in VARIABLES_LEVANTE]
    else:
        pedidas = set(variables_param)
        seleccion = [v['id'] for v in VARIABLES_LEVANTE if v['id'] in pedidas]

    variables = []
    for definicion in VARIABLES_LEVANTE:
        if definicion['id'] not in seleccion:
            continue
        matriz = {sem: {lote: None for lote in nombres} for sem in semanas}
        for lote in nombres:
            for fila in filas_lote.get(lote, []):
                matriz[fila['sem']][lote] = fila[definicion['clave']]
        variables.append({
            'id': definicion['id'],
            'titulo': definicion['titulo'],
            'decimales': definicion['decimales'],
            'matriz': matriz,
            'tabla': {sem: definicion['tabla'].get(sem) for sem in semanas},
        })

    # Consumo en granja: se conserva tal cual, con los lotes indicados o todos.
    lotes_consumo = [l for l in (lotes_param or nombres) if l in nombres]
    consumo_filas = model.fetch_levante_consumo(lotes_consumo)
    semanas_consumo = sorted({f['sem'] for f in consumo_filas if f['sem'] is not None})
    matriz_consumo = {s: {} for s in semanas_consumo}
    for f in consumo_filas:
        if f['sem'] is None or not f['lote']:
            continue
        matriz_consumo[f['sem']][f['lote']] = _sin_cero(_a_num(f['consumo']))

    lotes_meta = []
    for t in todos:
        fecha = t.get('fecha_recepcion')
        lotes_meta.append({
            'nombre': t['lote'],
            'fecha_enc': fecha.isoformat() if hasattr(fecha, 'isoformat') else (str(fecha) if fecha else ''),
            'aves_enc': t.get('aves_enc'),
        })

    return {
        'todas_variables': [
            {'id': v['id'], 'titulo': v['titulo'], 'activo': v['id'] in seleccion}
            for v in VARIABLES_LEVANTE
        ],
        'activas': seleccion,
        'variables': variables,
        'semanas': semanas,
        'lotes': lotes_consumo,
        'lotes_meta': lotes_meta,
        'consumo': {'semanas': semanas_consumo, 'matriz': matriz_consumo},
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


# ---------------------------------------------------------------------------
# Se aplica la depuración común a todas las vistas de matriz.
# Así todas traen todos los lotes, dejan los ceros en blanco y no repiten
# los valores arrastrados hasta la última semana.
# ---------------------------------------------------------------------------
VISTAS_MATRIZ = (
    'get_huevos_semanal_detalle',
    'get_kilos_semanal_detalle',
    'get_mortalidad_semanal_detalle',
    'get_peso_aves_detalle',
    'get_consumo_agua_detalle',
    'get_saldo_aves_detalle',
    'get_porc_produccion_detalle',
    'get_mort_acumulada_detalle',
    'get_mort_semanal_detalle',
    'get_haa_detalle',
    'get_gramos_aves_detalle',
    'get_conv_semanal_detalle',
    'get_conv_acumulada_detalle',
    'get_masa_semanal_detalle',
    'get_masa_acumulada_detalle',
    'get_peso_huevo_detalle',
    'get_rotura_huevo_detalle',
    'get_uniformidad_detalle',
    'get_acumulados_clasificadora_detalle',
)

for _nombre_vista in VISTAS_MATRIZ:
    globals()[_nombre_vista] = _depurar_vista()(globals()[_nombre_vista])

# La primera semana se mide en días y no lleva recorte de semanas
_primera_semana_depurada = _depurar_vista(eje='dias', con_cortes=False)(
    get_primera_semana_levante_detalle
)


def get_primera_semana_levante_detalle():
    """Agrega el estado ACTIVO/CONCLUIDO a cada lote del panel."""
    datos = _primera_semana_depurada()
    nombres = [l['nombre'] for l in datos.get('lotes', [])]
    estados = lotes_clasificacion.fetch_clasificacion_lotes(nombres)
    for lote in datos.get('lotes', []):
        info = estados.get(lote['nombre'], {})
        lote['estado'] = info.get('estado', 'ACTIVO')
        lote['empresa'] = info.get('empresa')
        lote['levante_externo'] = info.get('levante_externo', False)
        lote['variedad'] = info.get('variedad')
    return datos

del _nombre_vista
