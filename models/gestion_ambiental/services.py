"""
Calculo de indicadores, semaforos y series para el tablero de Gestion Ambiental.

Toda la logica de presentacion (filtros fisicos, cumplimiento normativo,
formato numerico y minigraficos) vive aqui, de modo que las rutas solo
orquestan y las plantillas solo pintan.
"""

from datetime import date

from models.gestion_ambiental.indicadores import (
    INDICADORES,
    indicador_para_sede,
    indicadores_de_sede,
    indicadores_del_grupo,
    obtener_indicador,
)
from models.gestion_ambiental.consultas import cargar_series

MESES = (
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)


# ----------------------------------------------------------------------
# Formato
# ----------------------------------------------------------------------
def formatear_valor(valor, decimales=2):
    """Numero con separador de miles y decimales fijos. None -> raya."""
    if valor is None:
        return '\u2014'
    return f'{valor:,.{decimales}f}'


def formatear_fecha(fecha):
    """Fecha larga en espanol: '12 de noviembre de 2026'."""
    if not fecha:
        return '\u2014'
    return '%d de %s de %d' % (fecha.day, MESES[fecha.month - 1], fecha.year)


def formatear_fecha_corta(fecha):
    """Fecha compacta para ejes y tablas: '12 nov 2026'."""
    if not fecha:
        return ''
    return '%02d %s %d' % (fecha.day, MESES[fecha.month - 1][:3], fecha.year)


# ----------------------------------------------------------------------
# Cumplimiento y semaforo
# ----------------------------------------------------------------------
def cumple_limite(indicador, valor):
    """Evalua un valor contra el criterio normativo del indicador."""
    if valor is None:
        return None
    criterio = indicador['criterio']
    if criterio == 'rango':
        return indicador['limite_min'] <= valor <= indicador['limite_max']
    if criterio == 'maximo':
        return valor <= indicador['limite_max']
    if criterio == 'cero':
        return valor == 0
    return True


def texto_limite(indicador):
    """Descripcion legible del limite normativo."""
    criterio = indicador['criterio']
    decimales = min(indicador['decimales'], 2)
    if criterio == 'rango':
        return '%s a %s %s' % (
            formatear_valor(indicador['limite_min'], decimales),
            formatear_valor(indicador['limite_max'], decimales),
            indicador['unidad'],
        )
    if criterio == 'maximo':
        return 'max. %s %s' % (
            formatear_valor(indicador['limite_max'], decimales),
            indicador['unidad'],
        )
    if criterio == 'cero':
        return '0 %s' % indicador['unidad']
    return 'sin limite'


def estado_de(indicador, valor):
    """Semaforo a partir del ultimo valor valido."""
    if valor is None:
        return 'sin-datos'
    return 'ok' if cumple_limite(indicador, valor) else 'alerta'


# ----------------------------------------------------------------------
# Minigrafico (SVG generado en el servidor)
# ----------------------------------------------------------------------
def puntos_sparkline(serie, ancho=104, alto=30, max_puntos=48):
    """
    Devuelve los puntos 'x,y x,y' de un poligono normalizado para un SVG.

    Se genera en el servidor para no crear 23 instancias de Chart.js en la
    vista de resumen.
    """
    valores = [p['valor'] for p in serie]
    if len(valores) < 2:
        return ''

    if len(valores) > max_puntos:
        paso = len(valores) / float(max_puntos)
        valores = [valores[int(i * paso)] for i in range(max_puntos)]

    minimo, maximo = min(valores), max(valores)
    rango = maximo - minimo
    margen = 2
    util_alto = alto - margen * 2

    coords = []
    total = len(valores) - 1
    for i, valor in enumerate(valores):
        x = round(i * ancho / float(total), 2)
        if rango == 0:
            y = round(alto / 2.0, 2)
        else:
            y = round(margen + util_alto - ((valor - minimo) / rango) * util_alto, 2)
        coords.append('%s,%s' % (x, y))
    return ' '.join(coords)


# ----------------------------------------------------------------------
# KPI por indicador
# ----------------------------------------------------------------------
def recuento_por_periodo(puntos, granularidad='mes'):
    """
    Convierte los puntos en recuentos distintos por periodo y tipo de agua.

    Se usa cuando Looker grafica la metrica como CTD (recuento distinto), por
    ejemplo en turbiedad de Vargas.
    """
    grupos = {}
    for punto in puntos:
        fecha = punto['fecha']
        if granularidad == 'mes':
            fecha = date(fecha.year, fecha.month, 1)
        clave = (fecha, punto.get('tipo'))
        grupos.setdefault(clave, set()).add(round(punto['valor'], 6))

    salida = []
    for (fecha, tipo), valores in sorted(
        grupos.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))
    ):
        salida.append({
            'fecha': fecha,
            'valor': float(len(valores)),
            'tipo': tipo,
        })
    return salida


def calcular_kpi(indicador, serie):
    """Resume la serie de un indicador: ultimo valor, promedio y cumplimiento."""
    fisico_min, fisico_max = indicador['fisico']
    validos = [p for p in serie if fisico_min <= p['valor'] <= fisico_max]
    excluidos = len(serie) - len(validos)

    kpi = {
        'indicador': indicador,
        'serie': validos,
        'n': len(validos),
        'excluidos': excluidos,
        'ultimo': None,
        'ultima_fecha': None,
        'promedio': None,
        'minimo': None,
        'maximo': None,
        'cumplen': 0,
        'porc_cumplimiento': None,
        'estado': 'sin-datos',
        'limite': texto_limite(indicador),
        'sparkline': '',
        'tendencia': 'flat',
    }

    if not validos:
        kpi['ultimo_txt'] = '\u2014'
        kpi['promedio_txt'] = '\u2014'
        kpi['minimo_txt'] = '\u2014'
        kpi['maximo_txt'] = '\u2014'
        kpi['porc_txt'] = '\u2014'
        kpi['fecha_txt'] = 'Sin registros'
        return kpi

    valores = [p['valor'] for p in validos]
    kpi['ultimo'] = valores[-1]
    kpi['ultima_fecha'] = validos[-1]['fecha']
    kpi['promedio'] = sum(valores) / float(len(valores))
    kpi['minimo'] = min(valores)
    kpi['maximo'] = max(valores)
    kpi['cumplen'] = sum(
        1 for v in valores if cumple_limite(indicador, v)
    )
    kpi['porc_cumplimiento'] = kpi['cumplen'] * 100.0 / len(valores)
    kpi['estado'] = estado_de(indicador, valores[-1])
    kpi['sparkline'] = puntos_sparkline(validos)

    decimales = indicador['decimales']
    kpi['ultimo_txt'] = formatear_valor(kpi['ultimo'], decimales)
    kpi['promedio_txt'] = formatear_valor(kpi['promedio'], decimales)
    kpi['minimo_txt'] = formatear_valor(kpi['minimo'], decimales)
    kpi['maximo_txt'] = formatear_valor(kpi['maximo'], decimales)
    kpi['porc_txt'] = '%.0f%%' % kpi['porc_cumplimiento']
    kpi['fecha_txt'] = formatear_fecha_corta(kpi['ultima_fecha'])

    if len(valores) >= 2:
        if valores[-1] > valores[-2]:
            kpi['tendencia'] = 'up'
        elif valores[-1] < valores[-2]:
            kpi['tendencia'] = 'down'

    return kpi


# ----------------------------------------------------------------------
# Armado del tablero
# ----------------------------------------------------------------------
def construir_tablero(sede, desde=None, hasta=None, grupo=None, indicador_id=None):
    """
    Prepara todos los datos que consume la plantilla del tablero.

    Devuelve un diccionario con los KPI de cada grupo, el resumen global y el
    indicador enfocado (el que se grafica en grande).
    """
    desde = desde if isinstance(desde, date) else None
    hasta = hasta if isinstance(hasta, date) else None

    lista = [indicador_para_sede(i, sede) for i in indicadores_de_sede(sede)]

    series = cargar_series(sede, lista, desde=desde, hasta=hasta)

    kpis = {}
    for ind in lista:
        puntos = series.get(ind['id'], [])
        if ind.get('agregacion') == 'ctd':
            puntos = recuento_por_periodo(puntos, ind.get('granularidad', 'mes'))
        kpis[ind['id']] = calcular_kpi(ind, puntos)

    grupo_actual = grupo if grupo in ('resumen', 'diario', 'laboratorio') else 'resumen'

    ind_foco = None
    if indicador_id:
        ind_foco = next((i for i in lista if i['id'] == indicador_id), None)

    if ind_foco is None:
        ind_foco = lista[0]
        if grupo_actual in ('diario', 'laboratorio'):
            del_grupo = [i for i in lista if i['grupo'] == grupo_actual]
            if del_grupo:
                ind_foco = del_grupo[0]
    elif not grupo:
        grupo_actual = ind_foco['grupo']

    kpi_foco = kpis[ind_foco['id']]

    # Resumen global (solo indicadores con datos)
    con_datos = [k for k in kpis.values() if k['n'] > 0]
    en_ok = [k for k in con_datos if k['estado'] == 'ok']
    en_alerta = [k for k in con_datos if k['estado'] == 'alerta']
    sin_datos = [k for k in kpis.values() if k['n'] == 0]
    total_registros = sum(k['n'] for k in kpis.values())
    total_excluidos = sum(k['excluidos'] for k in kpis.values())

    resumen = {
        'total_indicadores': len(lista),
        'con_datos': len(con_datos),
        'en_ok': len(en_ok),
        'en_alerta': len(en_alerta),
        'sin_datos': len(sin_datos),
        'total_registros': total_registros,
        'total_excluidos': total_excluidos,
        'porc_cumplimiento': (len(en_ok) * 100.0 / len(con_datos)) if con_datos else 0.0,
        'primera_fecha': min((k['serie'][0]['fecha'] for k in con_datos), default=None),
        'ultima_fecha': max((k['ultima_fecha'] for k in con_datos if k['ultima_fecha']), default=None),
    }

    return {
        'kpis': kpis,
        'grupos': {
            'diario': [kpis[i['id']] for i in lista if i['grupo'] == 'diario'],
            'laboratorio': [kpis[i['id']] for i in lista if i['grupo'] == 'laboratorio'],
        },
        'grupo_actual': grupo_actual,
        'kpi_foco': kpi_foco,
        'resumen': resumen,
    }


MESES_CORTOS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
                'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


def etiqueta_mes(anio, mes):
    """Etiqueta de periodo para el eje X: 'ene 2024'."""
    return '%s %d' % (MESES_CORTOS[mes - 1], anio)


def series_mensuales(puntos, decimales, usa_tipo, nombre_base='Valor real'):
    """
    Agrupa los registros por anio-mes y, cuando aplica, por tipo de agua.

    Devuelve (periodos, series). Cada serie trae su nombre y sus valores
    alineados al eje de periodos, con None en los meses sin dato. Las series
    se ordenan por su valor real promedio, de mayor a menor.
    """
    from models.gestion_ambiental.indicadores import normalizar_tipo

    periodos = set()
    acumulado = {}

    for punto in puntos:
        clave = (punto['fecha'].year, punto['fecha'].month)
        periodos.add(clave)
        tipo = normalizar_tipo(punto.get('tipo')) if usa_tipo else None
        acumulado.setdefault(tipo, {}).setdefault(clave, []).append(punto['valor'])

    periodos = sorted(periodos)
    if not periodos:
        return [], []

    # Se completa la linea de tiempo mes a mes para que el eje X sea
    # proporcional: un hueco de dos anos no puede verse igual que uno de un mes.
    completo = []
    anio, mes = periodos[0]
    fin_anio, fin_mes = periodos[-1]
    while (anio, mes) <= (fin_anio, fin_mes):
        completo.append((anio, mes))
        mes += 1
        if mes > 12:
            mes = 1
            anio += 1
    periodos = completo

    series = []
    for tipo, por_periodo in acumulado.items():
        valores = []
        for periodo in periodos:
            grupo = por_periodo.get(periodo)
            if grupo:
                valores.append(round(sum(grupo) / float(len(grupo)), decimales))
            else:
                valores.append(None)
        presentes = [v for v in valores if v is not None]
        series.append({
            'nombre': tipo if tipo else nombre_base,
            'valores': valores,
            'promedio': (sum(presentes) / float(len(presentes))) if presentes else None,
            'ultimo': presentes[-1] if presentes else None,
        })

    series.sort(key=lambda s: (s['promedio'] is None, -(s['promedio'] or 0)))
    return periodos, series


def opcionales_para_grafico(indicador, sede, desde, hasta, fechas):
    """
    Alinea las metricas opcionales al eje de fechas del grafico principal.

    Devuelve [{'nombre': ..., 'valores': [...]}] con None en las fechas sin
    dato, listo para convertirse en series adicionales desactivadas.
    """
    from models.gestion_ambiental.consultas import cargar_opcionales

    datos = cargar_opcionales(sede, indicador, desde=desde, hasta=hasta)
    if not datos:
        return []

    salida = []
    for item in datos:
        salida.append({
            'nombre': item['nombre'],
            'valores': [item['valores'].get(fecha) for fecha in fechas],
        })
    return salida


def serie_para_grafico(kpi):
    """
    Estructura la serie del indicador enfocado para Chart.js.

    Eje X: fecha. En los indicadores de laboratorio se agrupa por anio y mes y
    se desglosa por tipo de agua. En los diarios se conserva el dato por fecha.
    Eje Y: la metrica del indicador.
    """
    indicador = kpi['indicador']
    decimales = indicador['decimales']
    usa_tipo = bool(indicador.get('col_tipo'))
    granularidad = indicador.get('granularidad', 'mes')

    if granularidad == 'dia':
        puntos = kpi['serie']
        periodos = None
        series = [{
            'nombre': indicador.get('etiqueta_y', 'Valor real'),
            'valores': [round(p['valor'], decimales) for p in puntos],
            'promedio': None,
            'ultimo': None,
        }]
        etiquetas = [formatear_fecha_corta(p['fecha']) for p in puntos]
        fechas = [p['fecha'].isoformat() for p in puntos]
    else:
        periodos, series = series_mensuales(
            kpi['serie'], decimales, usa_tipo,
            indicador.get('etiqueta_y', 'Valor real'),
        )
        etiquetas = [etiqueta_mes(a, m) for a, m in periodos]
        fechas = ['%04d-%02d-01' % (a, m) for a, m in periodos]

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
        'eje_x': 'Fecha' if granularidad == 'dia' else 'Fecha (año y mes)',
        'eje_y': indicador.get('etiqueta_y', 'Valor real'),
        'dimension': 'Tipo de agua' if usa_tipo else None,
        'tipo_grafico': indicador.get('tipo_grafico', 'line'),
        'granularidad': granularidad,
        'mostrar_valores': bool(indicador.get('mostrar_valores')),
        'etiquetas': etiquetas,
        'fechas': fechas,
        'series': series,
    }


def registros_tabla(kpi):
    """Filas de la tabla de detalle, de la mas reciente a la mas antigua."""
    from models.gestion_ambiental.indicadores import normalizar_tipo

    indicador = kpi['indicador']
    decimales = indicador['decimales']
    usa_tipo = bool(indicador.get('col_tipo'))
    filas = []
    for punto in reversed(kpi['serie']):
        filas.append({
            'fecha': formatear_fecha(punto['fecha']),
            'valor': formatear_valor(punto['valor'], decimales),
            'tipo': normalizar_tipo(punto.get('tipo')) if usa_tipo else '',
            'cumple': cumple_limite(indicador, punto['valor']),
        })
    return filas


def datos_exportacion(tablero_datos, sede_nombre, rango_texto):
    """
    Estructura plana para la exportacion a Excel.

    Incluye el resumen de los 23 indicadores y la serie completa del indicador
    enfocado. Se serializa a JSON y la construccion del archivo se hace en el
    navegador con SheetJS.
    """
    from models.gestion_ambiental.indicadores import GRUPOS

    resumen = []
    for clave in ('diario', 'laboratorio'):
        for kpi in tablero_datos['grupos'][clave]:
            ind = kpi['indicador']
            resumen.append({
                'Grupo': GRUPOS[clave]['nombre'],
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

    foco = tablero_datos['kpi_foco']
    ind_foco = foco['indicador']
    usa_tipo = bool(ind_foco.get('col_tipo'))
    from models.gestion_ambiental.indicadores import normalizar_tipo

    serie = {
        'Indicador': ind_foco['nombre'],
        'Unidad': ind_foco['unidad'],
        'Límite': foco['limite'],
        'Fechas': [p['fecha'].isoformat() for p in foco['serie']],
        'Tipos': [normalizar_tipo(p.get('tipo')) if usa_tipo else '' for p in foco['serie']],
        'Valores': [round(p['valor'], ind_foco['decimales']) for p in foco['serie']],
        'Cumple': ['Sí' if cumple_limite(ind_foco, p['valor']) else 'No' for p in foco['serie']],
    }

    return {
        'meta': {
            'sede': sede_nombre,
            'rango': rango_texto,
            'generado': date.today().isoformat(),
        },
        'resumen': resumen,
        'serie': serie,
    }
