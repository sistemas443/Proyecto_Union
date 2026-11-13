# models/talento_humano/evaluaciones_programadas.py
"""
Evaluaciones de desempeño PROGRAMADAS (vista administradora de pendientes).

Reglas de negocio (GTH):
  * Ciclo de 3 meses  -> cumple a los 3 meses de ingreso.
  * Ciclo de 6 meses  -> cumple a los 6 meses de ingreso.
  * Ciclos anuales    -> cumplen a los 12, 24, 36... meses (solo a partir del año).
  * La evaluación debe realizarse DURANTE el mes anterior al cumplimiento:
        fecha_objetivo   = fecha_cumplimiento - 1 mes   (mes en que se agrupa)
        ventana          = [fecha_objetivo, fecha_cumplimiento]
  * Estados:
        proxima     -> todavía no abre la ventana (falta más de 1 mes).
        en_ventana  -> se puede realizar ya (dentro de la ventana).
        vencida     -> pasó la fecha de cumplimiento y no se hizo (se queda así).
  * No se omite ni se reprograma: la alerta persiste hasta que exista evaluación.

Se consideran solo colaboradores activos (estado='Activo', eliminado_en IS NULL).
El historial se limita a 12 meses hacia atrás y 12 hacia adelante para no listar
ciclos antiquísimos de personas con mucha antigüedad.
"""
import calendar
from datetime import date

import psycopg2.extras

from models.base import get_db_connection

MESES_HISTORIAL = 12   # meses hacia atrás que se revisan
MESES_HORIZONTE = 12   # meses hacia adelante que se muestran

MESES_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

ESTADO_LABEL = {
    'proxima': 'Próxima',
    'en_ventana': 'En ventana',
    'vencida': 'Vencida',
}
ESTADO_ORDEN = {'vencida': 0, 'en_ventana': 1, 'proxima': 2}


def sumar_meses(fecha, meses):
    """Suma meses a una fecha respetando el último día del mes."""
    total = fecha.month - 1 + meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _tipo_label(tipo, numero):
    if tipo == '3M':
        return '3 meses'
    if tipo == '6M':
        return '6 meses'
    return '1 año' if numero == 1 else f'{numero} años'


def _armar_ciclo(tipo, numero, fecha_cumplimiento, hoy):
    objetivo = sumar_meses(fecha_cumplimiento, -1)
    if hoy < objetivo:
        estado = 'proxima'
        dias = (objetivo - hoy).days
    elif hoy <= fecha_cumplimiento:
        estado = 'en_ventana'
        dias = (fecha_cumplimiento - hoy).days
    else:
        estado = 'vencida'
        dias = (hoy - fecha_cumplimiento).days
    return {
        'tipo': tipo,
        'numero': numero,
        'tipo_label': _tipo_label(tipo, numero),
        'fecha_cumplimiento': fecha_cumplimiento,
        'fecha_objetivo': objetivo,
        'estado': estado,
        'estado_label': ESTADO_LABEL[estado],
        'dias': dias,
    }


def ciclos_de(fecha_ingreso, hoy=None, historial_meses=MESES_HISTORIAL,
              horizonte_meses=MESES_HORIZONTE):
    """Genera los ciclos de evaluación de un colaborador dentro del rango de control."""
    if not fecha_ingreso:
        return []
    if isinstance(fecha_ingreso, str):
        fecha_ingreso = date.fromisoformat(fecha_ingreso)

    hoy = hoy or date.today()
    if fecha_ingreso > hoy:
        return []

    desde = sumar_meses(hoy, -historial_meses)
    hasta = sumar_meses(hoy, horizonte_meses)

    ciclos = []

    def en_rango(cumple):
        return desde <= cumple <= hasta

    # Ciclos de 3 y 6 meses (solo primer año).
    for tipo, numero, meses in (('3M', 1, 3), ('6M', 1, 6)):
        cumple = sumar_meses(fecha_ingreso, meses)
        if en_rango(cumple):
            ciclos.append(_armar_ciclo(tipo, numero, cumple, hoy))

    # Ciclos anuales: 12, 24, 36... meses.
    n = 1
    while n <= 120:
        cumple = sumar_meses(fecha_ingreso, 12 * n)
        if cumple > hasta:
            break
        if en_rango(cumple):
            ciclos.append(_armar_ciclo('ANUAL', n, cumple, hoy))
        n += 1

    return ciclos


def _esta_realizado(ciclo, evals):
    """True si el ciclo ya tiene una evaluación vinculada o, para datos antiguos,
    una evaluación con fecha dentro de la ventana del ciclo."""
    for e in evals:
        if e.get('ciclo_tipo') == ciclo['tipo'] and e.get('ciclo_numero') == ciclo['numero']:
            return True
    for e in evals:
        if e.get('ciclo_tipo') is None and e.get('fecha_evaluacion'):
            f = e['fecha_evaluacion']
            if ciclo['fecha_objetivo'] <= f <= ciclo['fecha_cumplimiento']:
                return True
    return False


class EvaluacionesProgramadas:
    """Consulta y agrupación de ciclos de evaluación pendientes."""

    @staticmethod
    def get_pendientes(hoy=None, historial_meses=MESES_HISTORIAL,
                       horizonte_meses=MESES_HORIZONTE, area=None, solo_lideres=False):
        """Devuelve una lista plana de ciclos pendientes.

        - area: restringe a un área (líder de proceso).
        - solo_lideres: restringe a cargos que empiezan por "Lider" (coordinador).
        """
        hoy = hoy or date.today()
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT id, nombre_completo, num_doc, cargo, area, fecha_ingreso
                    FROM colaboradores
                    WHERE eliminado_en IS NULL AND estado = 'Activo'
                """
                params = []
                if area:
                    sql += " AND area = %s"
                    params.append(area)
                if solo_lideres:
                    sql += " AND (cargo ILIKE 'lider%' OR cargo ILIKE 'líder%')"
                sql += " ORDER BY area NULLS LAST, nombre_completo"
                cur.execute(sql, params or None)
                cols = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT colaborador_id, ciclo_tipo, ciclo_numero, fecha_evaluacion
                    FROM evaluaciones_desempeno
                """)
                evals = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        evals_por_col = {}
        for e in evals:
            evals_por_col.setdefault(e['colaborador_id'], []).append(e)

        items = []
        for c in cols:
            evs = evals_por_col.get(c['id'], [])
            for ciclo in ciclos_de(c['fecha_ingreso'], hoy, historial_meses, horizonte_meses):
                if _esta_realizado(ciclo, evs):
                    continue
                item = dict(ciclo)
                item.update({
                    'colaborador_id': c['id'],
                    'nombre_completo': c['nombre_completo'],
                    'num_doc': c['num_doc'],
                    'cargo': c['cargo'],
                    'area': c['area'],
                })
                items.append(item)
        return items

    @staticmethod
    def agrupar(items):
        """Agrupa por año (el actual primero), luego por área y luego por mes."""
        actual = date.today().year

        por_anio = {}
        for it in items:
            anio = it['fecha_objetivo'].year
            area = (it.get('area') or '').strip() or 'Sin área'
            por_anio.setdefault(anio, {}).setdefault(area, []).append(it)

        def orden_anio(a):
            if a == actual:
                return (0, 0)
            if a < actual:
                return (1, -a)   # años pasados: el más reciente primero
            return (2, a)        # años futuros: el más cercano primero

        anios = []
        for anio in sorted(por_anio.keys(), key=orden_anio):
            areas_dict = por_anio[anio]

            areas = []
            for area in sorted(areas_dict.keys(), key=lambda a: (a == 'Sin área', a.lower())):
                its = areas_dict[area]

                por_mes = {}
                for it in its:
                    clave = it['fecha_objetivo'].strftime('%Y-%m')
                    por_mes.setdefault(clave, []).append(it)

                meses = []
                for clave in sorted(por_mes.keys()):
                    its_mes = por_mes[clave]
                    its_mes.sort(key=lambda x: (
                        ESTADO_ORDEN.get(x['estado'], 9),
                        x['fecha_cumplimiento'],
                        (x['nombre_completo'] or '').lower(),
                    ))
                    ref = its_mes[0]['fecha_objetivo']
                    resumen = {'total': len(its_mes), 'en_ventana': 0,
                               'vencidas': 0, 'proximas': 0}
                    for x in its_mes:
                        if x['estado'] == 'vencida':
                            resumen['vencidas'] += 1
                        elif x['estado'] == 'en_ventana':
                            resumen['en_ventana'] += 1
                        else:
                            resumen['proximas'] += 1
                    meses.append({
                        'clave': clave,
                        'label': MESES_ES[ref.month - 1],
                        'filas': its_mes,
                        'resumen': resumen,
                    })

                totales = {'total': len(its), 'en_ventana': 0,
                           'vencidas': 0, 'proximas': 0}
                for x in its:
                    if x['estado'] == 'vencida':
                        totales['vencidas'] += 1
                    elif x['estado'] == 'en_ventana':
                        totales['en_ventana'] += 1
                    else:
                        totales['proximas'] += 1

                areas.append({'area': area, 'meses': meses, 'totales': totales})

            anio_items = [it for its in areas_dict.values() for it in its]
            totales_anio = {'total': len(anio_items), 'en_ventana': 0,
                            'vencidas': 0, 'proximas': 0}
            for x in anio_items:
                if x['estado'] == 'vencida':
                    totales_anio['vencidas'] += 1
                elif x['estado'] == 'en_ventana':
                    totales_anio['en_ventana'] += 1
                else:
                    totales_anio['proximas'] += 1

            anios.append({
                'anio': anio,
                'actual': anio == actual,
                'areas': areas,
                'totales': totales_anio,
            })
        return anios

    @staticmethod
    def totales(items):
        tot = {'total': len(items), 'en_ventana': 0, 'vencidas': 0, 'proximas': 0}
        for x in items:
            if x['estado'] == 'vencida':
                tot['vencidas'] += 1
            elif x['estado'] == 'en_ventana':
                tot['en_ventana'] += 1
            else:
                tot['proximas'] += 1
        return tot

    @staticmethod
    def ciclo_de(colaborador_id, tipo, numero, hoy=None):
        """Devuelve el ciclo concreto de un colaborador (para precargar/validar)."""
        hoy = hoy or date.today()
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fecha_ingreso FROM colaboradores "
                    "WHERE id = %s AND eliminado_en IS NULL",
                    (colaborador_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                fecha_ingreso = row[0]
        finally:
            conn.close()

        for ciclo in ciclos_de(fecha_ingreso, hoy):
            if ciclo['tipo'] == tipo and ciclo['numero'] == numero:
                return ciclo
        return None

    @staticmethod
    def esta_realizado(colaborador_id, tipo, numero):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM evaluaciones_desempeno
                    WHERE colaborador_id = %s AND ciclo_tipo = %s AND ciclo_numero = %s
                    LIMIT 1
                """, (colaborador_id, tipo, numero))
                return cur.fetchone() is not None
        finally:
            conn.close()
