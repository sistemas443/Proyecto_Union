"""
Acceso a la base `master_ga` para los indicadores de Gestion Ambiental.

Solo lectura. Las tablas de origen siguen el patron `<sede>_<sufijo>`, por
ejemplo `lourdes_mediciones_in_situ_agua`. Los nombres se validan contra una
lista blanca antes de interpolarlos en el SQL.
"""

import re

import psycopg2
import psycopg2.extras

from models.base import get_ga_connection
from models.gestion_ambiental.indicadores import SEDES

_PATRON_TABLA = re.compile(r'^[a-z0-9_]+$')


def nombre_tabla(sede, sufijo):
    """
    Construye y valida el nombre fisico de la tabla de origen.

    Lanza ValueError si la sede no existe o si el nombre resultante no es
    estrictamente alfanumerico, para evitar inyeccion por interpolacion.
    """
    info = SEDES.get(sede)
    if not info:
        raise ValueError('Sede desconocida: %s' % sede)
    tabla = '%s%s' % (info['prefijo'], sufijo)
    if not _PATRON_TABLA.match(tabla):
        raise ValueError('Nombre de tabla invalido: %s' % tabla)
    return tabla


def tabla_disponible(sede, sufijo):
    """Indica si la tabla de esa sede existe en master_ga."""
    try:
        tabla = nombre_tabla(sede, sufijo)
    except ValueError:
        return False
    conn = None
    try:
        conn = get_ga_connection()
        cur = conn.cursor()
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", ('public.' + tabla,))
        return bool(cur.fetchone()[0])
    except Exception:
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _resolver_columna(indicador, sede):
    """
    Devuelve (columna, expresion) segun la sede.

    Vargas no comparte los nombres de columna con Lourdes, por eso cada
    indicador puede declarar un mapa de equivalencias por sede.
    """
    columna = indicador.get('col_valor')
    expresion = indicador.get('expresion')
    override = (indicador.get('mapa_sedes') or {}).get(sede)
    if override:
        if 'col_valor' in override:
            columna = override['col_valor']
            expresion = None
        if 'expresion' in override:
            expresion = override['expresion']
            columna = None if override.get('col_valor') is None else columna
    return columna, expresion


def _fuente(indicador, sede):
    """
    Resuelve de donde sale el dato para una sede.

    Devuelve la relacion (tabla o vista), la columna de fecha, la columna de
    valor o la expresion. Si el indicador declara una vista para esa sede, se
    lee de ella: es la via que garantiza el mismo numero que Looker Studio.
    """
    vista = (indicador.get('vistas') or {}).get(sede)
    if vista:
        return {
            'relacion': vista[0],
            'col_fecha': vista[2] if len(vista) > 2 else indicador['col_fecha'],
            'col_valor': vista[1],
            'expresion': None,
        }

    columna, expresion = _resolver_columna(indicador, sede)
    return {
        'relacion': nombre_tabla(sede, indicador['tabla']),
        'col_fecha': indicador['col_fecha'],
        'col_valor': columna,
        'expresion': expresion,
    }


def cargar_opcionales(sede, indicador, desde=None, hasta=None):
    """
    Lee las metricas opcionales de un indicador desde su vista.

    Devuelve una lista de {'nombre': etiqueta, 'valores': {fecha_iso: valor}}.
    Se usa, por ejemplo, para las series de cloro PTAP y galpones del
    indicador de cloro de Vargas.
    """
    definicion = (indicador.get('opcionales') or {}).get(sede) or []
    vista = (indicador.get('vistas') or {}).get(sede)
    if not definicion or not vista:
        return []

    nombre_vista, _col_valor, col_fecha = vista[0], vista[1], vista[2]
    columnas = [col for _etiqueta, col in definicion]

    conn = None
    cur = None
    try:
        conn = get_ga_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        seleccion = ', '.join('"%s"' % c for c in columnas)
        condiciones = ['"%s" IS NOT NULL' % col_fecha,
                       '"%s" <= CURRENT_DATE' % col_fecha]
        parametros = []
        if desde:
            condiciones.append('"%s" >= %%s' % col_fecha)
            parametros.append(desde)
        if hasta:
            condiciones.append('"%s" <= %%s' % col_fecha)
            parametros.append(hasta)

        sql = 'SELECT "%s" AS fecha, %s FROM %s WHERE %s ORDER BY "%s"' % (
            col_fecha, seleccion, nombre_vista,
            ' AND '.join(condiciones), col_fecha,
        )
        cur.execute(sql, tuple(parametros))
        filas = cur.fetchall()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return []
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

    salida = []
    for etiqueta, columna in definicion:
        valores = {}
        for fila in filas:
            valor = fila.get(columna)
            if valor is None:
                continue
            valores[fila['fecha'].isoformat()] = float(valor)
        salida.append({'nombre': etiqueta, 'valores': valores})
    return salida


def cargar_series(sede, indicadores, desde=None, hasta=None):
    """
    Carga las series historicas de los indicadores solicitados.

    Devuelve un diccionario {id_indicador: [{'fecha': date, 'valor': float}, ...]}
    con los puntos ordenados por fecha. Las filas sin valor se omiten y las
    fechas posteriores a hoy (filas pre-creadas por AppSheet) se descartan.

    El filtro por rango fisico de cada indicador se aplica despues, en
    services.py, para poder informar cuantos registros se excluyeron.
    """
    resultado = {i['id']: [] for i in indicadores}
    if not indicadores:
        return resultado

    # Agrupa por relacion (tabla o vista) + columna de fecha para hacer una
    # sola consulta por grupo.
    grupos = {}
    for ind in indicadores:
        try:
            fuente = _fuente(ind, sede)
        except ValueError:
            continue
        clave = (fuente['relacion'], fuente['col_fecha'])
        grupos.setdefault(clave, []).append((ind, fuente))

    conn = None
    cur = None
    try:
        conn = get_ga_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        for (relacion, col_fecha), pares in grupos.items():
            lista = [ind for ind, _ in pares]

            # Si una columna no existe en esta sede, se devuelve NULL para ese
            # indicador en lugar de romper toda la consulta del grupo.
            try:
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                """, (relacion,))
                existentes = {fila['column_name'] for fila in cur.fetchall()}
            except Exception:
                conn.rollback()
                existentes = set()

            partes = []
            for ind in lista:
                fuente = _fuente(ind, sede)
                columna = fuente['col_valor']
                expresion = fuente['expresion']
                if expresion:
                    partes.append('(%s) AS "%s"' % (expresion, ind['id']))
                elif columna and columna in existentes:
                    partes.append('"%s" AS "%s"' % (columna, ind['id']))
                else:
                    partes.append('NULL AS "%s"' % ind['id'])

            col_tipo = next((i['col_tipo'] for i in lista if i.get('col_tipo')), None)
            if col_tipo:
                partes.append('"%s" AS "__tipo"' % col_tipo)

            select_cols = ', '.join(partes)

            condiciones = ['"%s" IS NOT NULL' % col_fecha,
                           '"%s" <= CURRENT_DATE' % col_fecha]
            parametros = []
            if desde:
                condiciones.append('"%s" >= %s' % (col_fecha, '%s'))
                parametros.append(desde)
            if hasta:
                condiciones.append('"%s" <= %s' % (col_fecha, '%s'))
                parametros.append(hasta)

            sql = 'SELECT "%s" AS fecha, %s FROM %s WHERE %s ORDER BY "%s"' % (
                col_fecha, select_cols, relacion,
                ' AND '.join(condiciones), col_fecha,
            )

            try:
                cur.execute(sql, tuple(parametros))
                filas = cur.fetchall()
            except Exception:
                conn.rollback()
                filas = []

            for fila in filas:
                fecha = fila['fecha']
                tipo = fila.get('__tipo') if col_tipo else None
                for ind in lista:
                    valor = fila.get(ind['id'])
                    if valor is None:
                        continue
                    resultado[ind['id']].append({
                        'fecha': fecha,
                        'valor': float(valor),
                        'tipo': tipo,
                    })

        return resultado
    finally:
        if conn is not None:
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass


def rango_historico(sede):
    """
    Devuelve (primera_fecha, ultima_fecha) con datos reales de la sede.

    Se apoya en las dos tablas del modulo y descarta fechas futuras.
    """
    primeras, ultimas = [], []
    conn = None
    cur = None
    try:
        conn = get_ga_connection()
        cur = conn.cursor()
        for sufijo, col in (('mediciones_in_situ_agua', 'fecha_registro'),
                            ('analisis_agua_laboratorio', 'fecha_toma')):
            try:
                tabla = nombre_tabla(sede, sufijo)
                cur.execute(
                    'SELECT MIN("%s"), MAX("%s") FROM %s WHERE "%s" <= CURRENT_DATE'
                    % (col, col, tabla, col)
                )
                fila = cur.fetchone()
            except Exception:
                conn.rollback()
                fila = (None, None)
            if fila and fila[0]:
                primeras.append(fila[0])
            if fila and fila[1]:
                ultimas.append(fila[1])
    except Exception:
        return None, None
    finally:
        if conn is not None:
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    if not primeras or not ultimas:
        return None, None
    return min(primeras), max(ultimas)
