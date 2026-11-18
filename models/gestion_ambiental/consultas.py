"""
Acceso a la base `master_ga` para los indicadores de Gestion Ambiental.

Solo lectura. Las tablas de origen siguen el patron `<sede>_<sufijo>`, por
ejemplo `lourdes_mediciones_in_situ_agua`. Los nombres se validan contra una
lista blanca antes de interpolarlos en el SQL.

Para reducir llamadas a la base:
- Todas las vistas de una sede se leen en una sola consulta (UNION ALL).
- Las series se guardan en un cache en memoria con vencimiento corto.
"""

import re
import time

import psycopg2
import psycopg2.extras

from models.base import get_ga_connection
from models.gestion_ambiental.indicadores import SEDES

_PATRON_TABLA = re.compile(r'^[a-z0-9_]+$')

# Cache en memoria de las series, por proceso. Evita repetir consultas al
# cambiar de indicador o recargar la pagina.
_CACHE_SERIES = {}
_CACHE_OPCIONALES = {}
_CACHE_TTL = 60.0


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


def cargar_series(sede, indicadores, desde=None, hasta=None):
    """
    Devuelve las series con cache en memoria para no repetir consultas.

    La clave incluye sede, rango e indicadores, de modo que al cambiar de
    indicador dentro del mismo rango no se vuelve a consultar la base.
    """
    clave = (sede, str(desde), str(hasta), tuple(i['id'] for i in indicadores))
    ahora = time.monotonic()
    guardado = _CACHE_SERIES.get(clave)
    if guardado and (ahora - guardado[0]) < _CACHE_TTL:
        return guardado[1]

    resultado = _cargar_series_sin_cache(sede, indicadores, desde, hasta)
    _CACHE_SERIES[clave] = (ahora, resultado)

    # Poda simple para que el cache no crezca sin control.
    if len(_CACHE_SERIES) > 64:
        for vieja in list(_CACHE_SERIES)[:32]:
            _CACHE_SERIES.pop(vieja, None)
    return resultado


def _cargar_series_sin_cache(sede, indicadores, desde=None, hasta=None):
    """
    Carga las series historicas de los indicadores solicitados.

    Devuelve un diccionario {id_indicador: [{'fecha', 'valor', 'tipo'}, ...]}
    ordenado por fecha. Las filas sin valor y las fechas futuras se descartan,
    igual que los registros en cero (salvo los indicadores cuyo valor conforme
    es precisamente cero).
    """
    resultado = {i['id']: [] for i in indicadores}
    if not indicadores:
        return resultado

    directos = []
    con_vista = []
    for ind in indicadores:
        if (ind.get('vistas') or {}).get(sede):
            con_vista.append(ind)
        else:
            directos.append(ind)

    conn = None
    cur = None
    try:
        conn = get_ga_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # --- Indicadores que leen de una tabla propia ---
        grupos = {}
        for ind in directos:
            try:
                fuente = _fuente(ind, sede)
            except ValueError:
                continue
            clave = (fuente['relacion'], fuente['col_fecha'])
            grupos.setdefault(clave, []).append((ind, fuente))

        for (relacion, col_fecha), pares in grupos.items():
            lista = [ind for ind, _ in pares]

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
                col_fecha, ', '.join(partes), relacion,
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

        # --- Indicadores que leen de una vista (una sola consulta) ---
        if con_vista:
            _cargar_desde_vistas(cur, conn, sede, con_vista, resultado, desde, hasta)

        # Filtro pedido: no mostrar registros en cero. Se exceptuan los
        # indicadores cuyo valor conforme es precisamente 0 (microbiologicos),
        # porque ahi el cero es un dato valido.
        for ind in indicadores:
            if ind.get('criterio') == 'cero':
                continue
            resultado[ind['id']] = [
                punto for punto in resultado[ind['id']] if punto['valor'] != 0
            ]

        return resultado
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


def _cargar_desde_vistas(cur, conn, sede, indicadores, resultado, desde, hasta):
    """
    Carga en una sola consulta todos los indicadores que leen de vistas.

    Se arma un UNION ALL con todas las vistas de la sede. Las vistas que no
    existan se omiten: el resto sigue funcionando.
    """
    nombres = []
    ramas_por_vista = []
    for ind in indicadores:
        vista = (ind.get('vistas') or {}).get(sede)
        if not vista:
            continue
        nombres.append(vista[0])
        ramas_por_vista.append((ind, vista))

    if not ramas_por_vista:
        return

    try:
        cur.execute("""
            SELECT table_name FROM information_schema.views
            WHERE table_schema = 'public' AND table_name = ANY(%s)
        """, (nombres,))
        disponibles = {fila['table_name'] for fila in cur.fetchall()}
    except Exception:
        conn.rollback()
        disponibles = set()

    ramas = []
    for ind, vista in ramas_por_vista:
        nombre_vista, col_valor, col_fecha = vista[0], vista[1], vista[2]
        if nombre_vista not in disponibles:
            continue
        col_tipo = ind.get('col_tipo')
        tipo_sql = '"%s"' % col_tipo if col_tipo else 'NULL::text'
        ramas.append(
            "SELECT '%s'::text AS indicador, \"%s\" AS fecha, %s AS tipo, "
            "\"%s\"::numeric AS valor FROM %s"
            % (ind['id'], col_fecha, tipo_sql, col_valor, nombre_vista)
        )

    if not ramas:
        return

    condiciones = ['fecha IS NOT NULL', 'fecha <= CURRENT_DATE']
    parametros = []
    if desde:
        condiciones.append('fecha >= %s')
        parametros.append(desde)
    if hasta:
        condiciones.append('fecha <= %s')
        parametros.append(hasta)

    sql = 'SELECT indicador, fecha, tipo, valor FROM (%s) t WHERE %s ORDER BY fecha' % (
        ' UNION ALL '.join(ramas), ' AND '.join(condiciones),
    )

    try:
        cur.execute(sql, tuple(parametros))
        filas = cur.fetchall()
    except Exception:
        conn.rollback()
        return

    for fila in filas:
        valor = fila['valor']
        if valor is None:
            continue
        resultado[fila['indicador']].append({
            'fecha': fila['fecha'],
            'valor': float(valor),
            'tipo': fila['tipo'],
        })


def cargar_opcionales(sede, indicador, desde=None, hasta=None):
    """
    Lee las metricas opcionales de un indicador desde su vista.

    Devuelve una lista de {'nombre': etiqueta, 'valores': {fecha_iso: valor}}.
    Se usa, por ejemplo, para las series de cloro PTAP y galpones del
    indicador de cloro de Vargas. Tambien usa cache en memoria.
    """
    definicion = (indicador.get('opcionales') or {}).get(sede) or []
    vista = (indicador.get('vistas') or {}).get(sede)
    if not definicion or not vista:
        return []

    clave = (sede, indicador['id'], str(desde), str(hasta))
    ahora = time.monotonic()
    guardado = _CACHE_OPCIONALES.get(clave)
    if guardado and (ahora - guardado[0]) < _CACHE_TTL:
        return guardado[1]

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
            if valor is None or float(valor) == 0:
                continue
            valores[fila['fecha'].isoformat()] = float(valor)
        salida.append({'nombre': etiqueta, 'valores': valores})

    _CACHE_OPCIONALES[clave] = (ahora, salida)
    if len(_CACHE_OPCIONALES) > 32:
        for vieja in list(_CACHE_OPCIONALES)[:16]:
            _CACHE_OPCIONALES.pop(vieja, None)
    return salida


def rango_historico(sede):
    """
    Devuelve (primera_fecha, ultima_fecha) con datos reales de la sede.
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

    if not primeras or not ultimas:
        return None, None
    return min(primeras), max(ultimas)
