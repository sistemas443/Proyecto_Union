"""
Calculo del tablero de General sobre las vistas `general_*` de `master_ga`.

Reutiliza el motor de indicadores de las sedes (KPI, formato y semaforo) y
anade lo propio de General:

- Consolidado "Todas": une Lourdes y Vargas y etiqueta cada punto con su sede.
- Filtro por sede: oculta los parametros que esa planta no mide.
- Tablas con columna de sede cuando se muestra el consolidado.
"""

from datetime import date
import time

import psycopg2.extras

from models.base import get_ga_connection
from models.gestion_ambiental.consultas import cargar_series
from models.gestion_ambiental.general import (
    LINEAS_GENERAL,
    SECCIONES_GENERAL,
    SEDES_GENERAL,
    indicadores_general,
)
from models.gestion_ambiental.indicadores import indicador_para_sede, normalizar_tipo
from models.gestion_ambiental.services import (
    MESES,
    calcular_kpi,
    cumple_limite,
    etiqueta_mes,
    formatear_fecha,
    formatear_fecha_corta,
    formatear_valor,
    recuento_por_periodo,
    registros_detalle as registros_detalle_sede,
    series_mensuales,
    _texto_referencia,
)

# Cache de las tablas consolidadas (sin desglose por sede).
_CACHE_UNICA = {}
_CACHE_UNICA_TTL = 60.0


def _etiqueta_sede(clave):
    """Nombre legible de la sede de un punto."""
    if clave in SEDES_GENERAL:
        return SEDES_GENERAL[clave]['nombre']
    return 'General'


def _cargar_fuente_unica(indicador, desde=None, hasta=None):
    """
    Lee una tabla consolidada que no distingue sede.

    Admite dos modos:
    - directo: una fila por fecha con su valor (serie consolidada histórica).
    - `anio_mes`: una fila por año y mes; se usa para consumo de agua, donde
      la fecha real de la tabla no coincide con el periodo del registro.
    """
    clave = (indicador['id'], str(desde), str(hasta))
    ahora = time.monotonic()
    guardado = _CACHE_UNICA.get(clave)
    if guardado and (ahora - guardado[0]) < _CACHE_UNICA_TTL:
        return guardado[1]

    tabla = indicador.get('fuente_unica')
    modo = indicador.get('modo')
    extra_def = indicador.get('extra') or []

    puntos = []
    conn = None
    cur = None
    try:
        conn = get_ga_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if modo == 'anio_mes':
            col_anio = indicador.get('col_anio', 'ano')
            col_mes_num = indicador.get('col_mes_num', 'numero_mes')
            col_mes = indicador.get('col_mes', 'mes')
            col_valor = indicador.get('col_valor')
            cols_extra = [col for _etiqueta, col in extra_def]

            seleccion = ['"%s"' % c for c in
                         [col_anio, col_mes_num, col_mes, col_valor] + cols_extra]
            condiciones = [
                '"%s" IS NOT NULL' % col_anio,
                '"%s" IS NOT NULL' % col_mes_num,
                '"%s" IS NOT NULL' % col_valor,
                '"%s" <= EXTRACT(YEAR FROM CURRENT_DATE)' % col_anio,
            ]
            if indicador.get('filtro_sql'):
                condiciones.append('(%s)' % indicador['filtro_sql'])

            sql = 'SELECT %s FROM %s WHERE %s ORDER BY "%s", "%s"' % (
                ', '.join(seleccion), tabla, ' AND '.join(condiciones),
                col_anio, col_mes_num,
            )
            cur.execute(sql)
            for fila in cur.fetchall():
                valor = fila[col_valor]
                if valor is None or float(valor) == 0:
                    continue
                anio = int(fila[col_anio])
                mes = int(fila[col_mes_num] or 1)
                mes = min(max(mes, 1), 12)
                fecha = date(anio, mes, 1)
                if desde and fecha < desde:
                    continue
                if hasta and fecha > hasta:
                    continue
                puntos.append({
                    'fecha': fecha,
                    'valor': float(valor),
                    'tipo': (str(fila.get(col_mes) or '').strip().title() or None),
                    'sede': 'general',
                    'extra': {
                        col: (float(fila[col]) if fila.get(col) is not None else None)
                        for col in cols_extra
                    },
                })
        else:
            col_fecha = indicador.get('col_fecha', 'fecha')
            col_valor = indicador.get('col_valor', 'valor_real')
            cols_extra = [col for _etiqueta, col in extra_def]

            seleccion = ['"%s" AS fecha' % col_fecha, '"%s" AS valor' % col_valor]
            seleccion.extend('"%s"' % col for col in cols_extra)

            condiciones = ['"%s" IS NOT NULL' % col_fecha,
                           '"%s" <= CURRENT_DATE' % col_fecha,
                           '"%s" IS NOT NULL' % col_valor]
            if indicador.get('filtro_sql'):
                condiciones.append('(%s)' % indicador['filtro_sql'])
            parametros = []
            if desde:
                condiciones.append('"%s" >= %%s' % col_fecha)
                parametros.append(desde)
            if hasta:
                condiciones.append('"%s" <= %%s' % col_fecha)
                parametros.append(hasta)

            sql = 'SELECT %s FROM %s WHERE %s ORDER BY "%s"' % (
                ', '.join(seleccion), tabla, ' AND '.join(condiciones), col_fecha,
            )
            cur.execute(sql, tuple(parametros))
            for fila in cur.fetchall():
                valor = fila['valor']
                if valor is None or float(valor) == 0:
                    continue
                puntos.append({
                    'fecha': fila['fecha'],
                    'valor': float(valor),
                    'tipo': None,
                    'sede': 'general',
                    'extra': {
                        col: (float(fila[col]) if fila.get(col) is not None else None)
                        for col in cols_extra
                    },
                })
    except Exception as error:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        print('[GESTION AMBIENTAL] Error en %s: %s' % (tabla, error))
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    _CACHE_UNICA[clave] = (ahora, puntos)
    if len(_CACHE_UNICA) > 32:
        for vieja in list(_CACHE_UNICA)[:16]:
            _CACHE_UNICA.pop(vieja, None)
    return puntos


def cargar_series_general(indicadores, sede='todas', desde=None, hasta=None):
    """
    Carga las series de General y etiqueta cada punto con su sede.

    Con sede 'todas' se leen las vistas de Lourdes y de Vargas y se unen. Con
    una sede concreta solo se lee la suya.
    """
    resultado = {i['id']: [] for i in indicadores}
    por_sede = {}

    for ind in indicadores:
        if ind.get('fuente_unica'):
            resultado[ind['id']] = _cargar_fuente_unica(ind, desde, hasta)
            continue
        for clave in (ind.get('vistas') or {}):
            if clave not in ('lourdes', 'vargas'):
                continue
            if sede != 'todas' and clave != sede:
                continue
            por_sede.setdefault(clave, []).append(ind)

    for clave, lista in por_sede.items():
        series = cargar_series(clave, lista, desde=desde, hasta=hasta)
        for ind in lista:
            for punto in series.get(ind['id'], []):
                copia = dict(punto)
                copia['sede'] = clave
                resultado[ind['id']].append(copia)

    for puntos in resultado.values():
        puntos.sort(key=lambda p: (p['fecha'], str(p.get('sede') or '')))
    return resultado


def construir_tablero_general(linea='produccion', tema='agua', desde=None,
                              hasta=None, indicador_id=None, indicadores=None):
    """
    Prepara los datos del tablero de una línea de General.

    Producción trabaja con Vargas y Levante con Lourdes. `indicadores` permite
    limitar el tablero a un submódulo (laboratorio, residuales, pH...). Devuelve
    los KPI, las secciones de la barra lateral y el indicador enfocado.
    """
    desde = desde if isinstance(desde, date) else None
    hasta = hasta if isinstance(hasta, date) else None

    info = LINEAS_GENERAL.get(linea) or LINEAS_GENERAL['produccion']
    sede = info['sede']

    base = indicadores if indicadores is not None else indicadores_general(linea, tema)
    lista = [indicador_para_sede(dict(i), sede) for i in base]
    series = cargar_series_general(lista, sede=sede, desde=desde, hasta=hasta)

    kpis = {}
    for ind in lista:
        puntos = series.get(ind['id'], [])
        if ind.get('agregacion') == 'ctd':
            puntos = recuento_por_periodo(puntos, ind.get('granularidad', 'mes'))
        kpis[ind['id']] = calcular_kpi(ind, puntos)

    ind_foco = None
    if indicador_id:
        ind_foco = next((i for i in lista if i['id'] == indicador_id), None)
    if ind_foco is None:
        ind_foco = lista[0] if lista else None

    kpi_foco = kpis.get(ind_foco['id']) if ind_foco else None

    con_datos = [k for k in kpis.values() if k['n'] > 0]
    resumen = {
        'total_indicadores': len(lista),
        'con_datos': len(con_datos),
        'sin_datos': len(lista) - len(con_datos),
        'total_registros': sum(k['n'] for k in kpis.values()),
        'primera_fecha': min((k['serie'][0]['fecha'] for k in con_datos), default=None),
        'ultima_fecha': max((k['ultima_fecha'] for k in con_datos if k['ultima_fecha']),
                            default=None),
    }

    secciones = []
    for clave, info in SECCIONES_GENERAL.items():
        items = [kpis[i['id']] for i in lista if i['grupo'] == clave]
        if items:
            secciones.append({
                'clave': clave,
                'nombre': info['nombre'],
                'icono': info['icono'],
                'indicadores': items,
            })

    return {
        'kpis': kpis,
        'secciones': secciones,
        'kpi_foco': kpi_foco,
        'resumen': resumen,
    }


def _promedio(valores):
    """Promedio ignorando los huecos."""
    presentes = [v for v in valores if v is not None]
    if not presentes:
        return None
    return sum(presentes) / float(len(presentes))


def _mostrar_valores(indicador, etiquetas, series):
    """
    Decide si se muestran las etiquetas de cada punto.

    En las lineas se muestran siempre que la serie no sea gigantesca; en las
    barras se mantiene el criterio anterior para no saturar.
    """
    es_linea = indicador.get('tipo_grafico', 'line') != 'bar'
    if es_linea:
        return len(etiquetas) <= 200 and len(series) <= 8
    return (bool(indicador.get('mostrar_valores'))
            and len(etiquetas) <= 30
            and len(series) <= 6)


def serie_para_grafico_general(kpi, sede='todas'):
    """
    Estructura la serie del indicador para Chart.js.

    En el consolidado el desglose es la sede (Lourdes vs Vargas); al filtrar
    una sede se usa el tipo de agua, igual que en el tablero de cada planta.
    """
    indicador = kpi['indicador']
    decimales = indicador['decimales']
    granularidad = indicador.get('granularidad', 'mes')
    etiqueta = indicador.get('etiqueta_y', 'Valor real')
    consolidado = sede == 'todas'

    if granularidad == 'dia':
        puntos = kpi['serie']
        if consolidado:
            fechas = sorted({p['fecha'] for p in puntos})
            agrupado = {}
            for punto in puntos:
                clave = _etiqueta_sede(punto.get('sede'))
                agrupado.setdefault(clave, {})[punto['fecha']] = round(
                    punto['valor'], decimales)
            series = []
            for nombre in sorted(agrupado):
                valores = [agrupado[nombre].get(f) for f in fechas]
                series.append({
                    'nombre': nombre,
                    'valores': valores,
                    'promedio': _promedio(valores),
                    'ultimo': next((v for v in reversed(valores) if v is not None), None),
                })
        else:
            series = [{
                'nombre': etiqueta,
                'valores': [round(p['valor'], decimales) for p in puntos],
                'promedio': None,
                'ultimo': None,
            }]
            fechas = [p['fecha'] for p in puntos]
        etiquetas = [formatear_fecha_corta(f) for f in fechas]
        fechas_iso = [f.isoformat() for f in fechas]
        claves_periodo = [f.isoformat() for f in fechas]
        eje_x = 'Fecha'
        dimension = 'Sede' if consolidado else None
    elif granularidad == 'anio':
        # Eje X: año. Cada mes es una serie (vista de Looker del consumo
        # doméstico). Los puntos traen fecha = primer día del mes.
        puntos = kpi['serie']
        anios = sorted({p['fecha'].year for p in puntos})
        nombres_mes = {}
        for punto in puntos:
            mes = punto['fecha'].month
            nombres_mes[mes] = punto.get('tipo') or MESES[mes - 1].capitalize()

        agrupado = {}
        for punto in puntos:
            clave = (punto['fecha'].year, punto['fecha'].month)
            agrupado.setdefault(clave, []).append(punto['valor'])

        series = []
        for mes in sorted(nombres_mes):
            valores = []
            for anio in anios:
                grupo = agrupado.get((anio, mes))
                valores.append(round(sum(grupo) / float(len(grupo)), decimales)
                               if grupo else None)
            series.append({
                'nombre': nombres_mes[mes],
                'valores': valores,
                'promedio': _promedio(valores),
                'ultimo': next((v for v in reversed(valores) if v is not None), None),
            })

        etiquetas = [str(a) for a in anios]
        fechas_iso = ['%04d-01-01' % a for a in anios]
        claves_periodo = list(anios)
        eje_x = 'Año'
        dimension = 'Mes'
    else:
        if consolidado:
            puntos = [
                dict(p, tipo=_etiqueta_sede(p.get('sede')))
                for p in kpi['serie']
            ]
            usa_tipo = True
        else:
            puntos = kpi['serie']
            usa_tipo = bool(indicador.get('col_tipo'))
        periodos, series = series_mensuales(
            puntos, decimales, usa_tipo, etiqueta,
            indicador.get('agregacion_mensual', 'promedio'),
        )
        etiquetas = [etiqueta_mes(a, m) for a, m in periodos]
        fechas_iso = ['%04d-%02d-01' % (a, m) for a, m in periodos]
        claves_periodo = list(periodos)
        eje_x = 'Fecha (año y mes)'
        if consolidado:
            dimension = 'Sede'
        elif usa_tipo:
            dimension = 'Tipo de agua'
        else:
            dimension = None

    # Métricas adicionales de la tabla de origen (número de aves, etc.).
    opcionales = []
    for nombre_extra, columna in (indicador.get('extra') or []):
        acumulado = {}
        for punto in kpi['serie']:
            valor = (punto.get('extra') or {}).get(columna)
            if valor is None:
                continue
            if granularidad == 'dia':
                clave = punto['fecha'].isoformat()
            elif granularidad == 'anio':
                clave = punto['fecha'].year
            else:
                clave = (punto['fecha'].year, punto['fecha'].month)
            acumulado.setdefault(clave, []).append(valor)
        valores = []
        for clave in claves_periodo:
            grupo = acumulado.get(clave)
            valores.append(round(sum(grupo) / float(len(grupo)), decimales)
                           if grupo else None)
        opcionales.append({'nombre': nombre_extra, 'valores': valores})

    return {
        'id': indicador['id'],
        'nombre': indicador['nombre'],
        'unidad': indicador['unidad'],
        'decimales': decimales,
        'criterio': indicador['criterio'],
        'limite_min': indicador['limite_min'],
        'limite_max': indicador['limite_max'],
        'etiqueta_limite_min': indicador.get('etiqueta_limite_min'),
        'etiqueta_limite_max': indicador.get('etiqueta_limite_max'),
        'limite_texto': kpi['limite'],
        'eje_x': eje_x,
        'eje_y': etiqueta,
        'dimension': dimension,
        'tipo_grafico': indicador.get('tipo_grafico', 'line'),
        'granularidad': granularidad,
        'mostrar_valores': _mostrar_valores(indicador, etiquetas, series),
        'decimales_etiqueta': (2 if indicador.get('tipo_grafico', 'line') != 'bar'
                               else None),
        'etiquetas': etiquetas,
        'fechas': fechas_iso,
        'series': series,
        'opcionales': opcionales,
        'referencia_valor': indicador.get('referencia_valor'),
        'referencia_texto': indicador.get('referencia_texto'),
    }


def registros_detalle_general(kpi, sede='todas', desde=None, hasta=None):
    """
    Tabla de registros del indicador, de la más reciente a la más antigua.

    Los indicadores diarios con columnas propias (cloro, pH, hierro) delegan
    en el mismo armador del módulo de la sede para mostrar exactamente las
    mismas columnas. En laboratorio se respeta el orden de cada sede: Vargas
    por fecha y Lourdes por valor.
    """
    indicador = kpi['indicador']
    decimales = indicador.get('decimales', 2)
    consolidado = sede == 'todas'
    grupo = indicador.get('grupo')

    definidas = (indicador.get('columnas_tabla') or {}).get(sede)
    if definidas:
        return registros_detalle_sede(kpi, sede, desde, hasta)

    if grupo == 'laboratorio':
        columnas = ['Fecha']
        if consolidado:
            columnas.append('Sede')
        columnas.extend(['Valor referencia', 'Valor real'])
        if indicador.get('col_tipo'):
            columnas.append('Tipo de agua')
        referencia = _texto_referencia(indicador)

        if sede == 'vargas':
            puntos = sorted(kpi['serie'], key=lambda p: p['fecha'])
        else:
            puntos = sorted(kpi['serie'], key=lambda p: p['valor'], reverse=True)

        filas = []
        for punto in puntos:
            celdas = [formatear_fecha(punto['fecha'])]
            if consolidado:
                celdas.append(_etiqueta_sede(punto.get('sede')))
            celdas.append(referencia)
            celdas.append(formatear_valor(punto['valor'], decimales))
            if indicador.get('col_tipo'):
                celdas.append(normalizar_tipo(punto.get('tipo')))
            filas.append(celdas)
        return {'columnas': columnas, 'filas': filas}

    if grupo == 'diario':
        columnas = ['Fecha']
        if consolidado:
            columnas.append('Sede')
        columnas.extend(['Año', indicador.get('etiqueta_y', 'Valor')])
        filas = []
        for punto in sorted(kpi['serie'], key=lambda p: p['fecha'], reverse=True):
            celdas = [formatear_fecha(punto['fecha'])]
            if consolidado:
                celdas.append(_etiqueta_sede(punto.get('sede')))
            celdas.append(str(punto['fecha'].year))
            celdas.append(formatear_valor(punto['valor'], decimales))
            filas.append(celdas)
        return {'columnas': columnas, 'filas': filas}

    if indicador.get('modo') == 'anio_mes' or indicador.get('extra'):
        extras = indicador.get('extra') or []
        por_anio = indicador.get('modo') == 'anio_mes'
        if por_anio:
            columnas = ['Año', 'Mes', indicador.get('etiqueta_y', 'Valor')]
        else:
            columnas = ['Fecha', 'Año', 'Mes', indicador.get('etiqueta_y', 'Valor')]
        columnas.extend(titulo for titulo, _col in extras)

        filas = []
        for punto in sorted(kpi['serie'], key=lambda p: p['fecha'], reverse=True):
            valores_extra = punto.get('extra') or {}
            mes = punto.get('tipo') or MESES[punto['fecha'].month - 1].capitalize()
            if por_anio:
                celdas = [str(punto['fecha'].year), mes]
            else:
                celdas = [formatear_fecha(punto['fecha']),
                          str(punto['fecha'].year), mes]
            celdas.append(formatear_valor(punto['valor'], decimales))
            for _titulo, col in extras:
                celdas.append(formatear_valor(valores_extra.get(col), decimales))
            filas.append(celdas)
        return {'columnas': columnas, 'filas': filas}

    columnas = ['Fecha', 'Año', indicador.get('etiqueta_y', 'Valor')]
    filas = []
    for punto in sorted(kpi['serie'], key=lambda p: p['fecha'], reverse=True):
        filas.append([
            formatear_fecha(punto['fecha']),
            str(punto['fecha'].year),
            formatear_valor(punto['valor'], decimales),
        ])
    return {'columnas': columnas, 'filas': filas}


def datos_exportacion_general(kpi_foco, kpis, sede='todas', rango_texto='',
                              etiqueta=None):
    """
    Estructura plana para la exportacion a Excel de General.

    Mantiene el mismo contrato que el tablero de sedes para reutilizar ga.js.
    """
    resumen = []
    for kpi in kpis:
        ind = kpi['indicador']
        resumen.append({
            'Indicador': ind['nombre'],
            'Unidad': ind['unidad'],
            'Último valor': kpi['ultimo'],
            'Fecha último': kpi['ultima_fecha'].isoformat() if kpi['ultima_fecha'] else '',
            'Promedio': round(kpi['promedio'], ind['decimales']) if kpi['promedio'] is not None else '',
            'Mínimo': round(kpi['minimo'], ind['decimales']) if kpi['minimo'] is not None else '',
            'Máximo': round(kpi['maximo'], ind['decimales']) if kpi['maximo'] is not None else '',
            'Registros': kpi['n'],
            'Excluidos': kpi['excluidos'],
            '% cumplimiento': round(kpi['porc_cumplimiento'], 1) if kpi['porc_cumplimiento'] is not None else '',
            'Límite': kpi['limite'],
            'Estado': {'ok': 'En norma', 'alerta': 'Fuera de norma',
                       'sin-datos': 'Sin datos'}.get(kpi['estado'], kpi['estado']),
        })

    ind_foco = kpi_foco['indicador']
    consolidado = sede == 'todas'
    tipos = []
    dimension = 'Tipo de agua'
    for punto in kpi_foco['serie']:
        if consolidado:
            tipos.append(_etiqueta_sede(punto.get('sede')))
        elif ind_foco.get('granularidad') == 'anio':
            tipos.append((punto.get('tipo') or '').strip())
            dimension = 'Mes'
        elif ind_foco.get('col_tipo'):
            tipos.append(normalizar_tipo(punto.get('tipo')))
        else:
            tipos.append('')

    serie = {
        'Indicador': ind_foco['nombre'],
        'Unidad': ind_foco['unidad'],
        'Límite': kpi_foco['limite'],
        'Dimension': dimension,
        'Fechas': [p['fecha'].isoformat() for p in kpi_foco['serie']],
        'Tipos': tipos,
        'Valores': [round(p['valor'], ind_foco['decimales']) for p in kpi_foco['serie']],
        'Cumple': ['Sí' if cumple_limite(ind_foco, p['valor']) else 'No'
                   for p in kpi_foco['serie']],
    }

    return {
        'meta': {
            'sede': etiqueta or ('General - %s' % _etiqueta_sede(sede)),
            'rango': rango_texto,
            'generado': date.today().isoformat(),
        },
        'resumen': resumen,
        'serie': serie,
    }
