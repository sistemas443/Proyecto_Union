# models/talento_humano/desempeno.py
"""
Módulo de Evaluación de Desempeño.

Réplica digital del formato GTH F 011: criterios/competencias con indicadores
conductuales, doble calificación (evaluador + autoevaluación) y cálculo
automático de porcentajes (Siempre=100% ... Nunca=0%), mínimo 70% para aprobar.
"""
import psycopg2
import psycopg2.extras
from models.base import get_db_connection

# Escala Likert -> porcentaje
SCORE_A_PCT = {1: 0, 2: 25, 3: 50, 4: 75, 5: 100}
MINIMO_APROBACION = 70.0


def _pct(score):
    return SCORE_A_PCT.get(score, 0)


class Desempeno:
    """CRUD y cálculo de evaluaciones de desempeño."""

    @staticmethod
    def get_criterios(area=None):
        """Devuelve los criterios activos con sus indicadores (filtrados por área).

        - `area` vacía/None: solo indicadores globales (area IS NULL).
        - `area` definida: globales + los específicos de esa área.
        """
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre FROM criterios_evaluacion WHERE activa = TRUE ORDER BY orden, id")
                criterios = [dict(r) for r in cur.fetchall()]
                if area:
                    cur.execute("""
                        SELECT id, criterio_id, descripcion, area FROM indicadores_evaluacion
                        WHERE area IS NULL OR area = %s
                        ORDER BY criterio_id, orden, id
                    """, (area,))
                else:
                    cur.execute("""
                        SELECT id, criterio_id, descripcion, area FROM indicadores_evaluacion
                        WHERE area IS NULL
                        ORDER BY criterio_id, orden, id
                    """)
                indicadores = [dict(r) for r in cur.fetchall()]
                for c in criterios:
                    c['indicadores'] = [i for i in indicadores if i['criterio_id'] == c['id']]
                # Solo criterios que tienen indicadores para el área solicitada
                return [c for c in criterios if c['indicadores']]
        finally:
            conn.close()

    @staticmethod
    def get_areas():
        """Áreas distintas de colaboradores activos (para selects y catálogo)."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT area FROM colaboradores
                    WHERE eliminado_en IS NULL AND area IS NOT NULL AND TRIM(area) <> ''
                    ORDER BY area
                """)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_criterios_catalogo():
        """Criterios con sus indicadores AGRUPADOS por área (para el catálogo)."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, nombre, orden, activa FROM criterios_evaluacion ORDER BY orden, id")
                criterios = [dict(r) for r in cur.fetchall()]
                cur.execute("""
                    SELECT id, criterio_id, descripcion, area, orden
                    FROM indicadores_evaluacion ORDER BY criterio_id, orden, id
                """)
                indicadores = [dict(r) for r in cur.fetchall()]

                for c in criterios:
                    grupos = {}
                    for i in indicadores:
                        if i['criterio_id'] != c['id']:
                            continue
                        area = i['area'] or 'Global'
                        grupos.setdefault(area, []).append(i)
                    c['grupos'] = [
                        {'area': None if k == 'Global' else k,
                         'area_label': k,
                         'indicadores': grupos[k]}
                        for k in sorted(grupos.keys(), key=lambda k: (k != 'Global', k.lower()))
                    ]
                    c['total_indicadores'] = sum(len(g['indicadores']) for g in c['grupos'])
                return criterios
        finally:
            conn.close()

    @staticmethod
    def crear_criterio(nombre):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM criterios_evaluacion")
                orden = cur.fetchone()[0]
                cur.execute("INSERT INTO criterios_evaluacion (nombre, orden) VALUES (%s, %s) RETURNING id",
                            (nombre.strip().upper(), orden))
                conn.commit()
                return cur.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def crear_indicador(criterio_id, descripcion, area):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM indicadores_evaluacion WHERE criterio_id = %s", (criterio_id,))
                orden = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO indicadores_evaluacion (criterio_id, descripcion, area, orden)
                    VALUES (%s, %s, %s, %s) RETURNING id
                """, (criterio_id, descripcion.strip(), area or None, orden))
                conn.commit()
                return cur.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def eliminar_indicador(indicador_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM indicadores_evaluacion WHERE id = %s", (indicador_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def eliminar_criterio(criterio_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM criterios_evaluacion WHERE id = %s", (criterio_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def get_colaboradores_activos():
        """Lista simple de colaboradores activos para selects."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, nombre_completo, cargo, area, num_doc
                    FROM colaboradores
                    WHERE eliminado_en IS NULL AND estado = 'Activo'
                    ORDER BY nombre_completo
                """)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def listar():
        """Lista de evaluaciones con nombre del colaborador."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT e.id, e.colaborador_id, c.nombre_completo, c.cargo, c.area,
                           e.periodo_inicio, e.periodo_fin, e.fecha_evaluacion,
                           e.estado, e.resultado_final, e.aprobada
                    FROM evaluaciones_desempeno e
                    JOIN colaboradores c ON c.id = e.colaborador_id
                    ORDER BY e.fecha_evaluacion DESC NULLS LAST, e.id DESC
                """)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def listar_agrupado():
        """Lista de evaluaciones agrupadas por área del colaborador."""
        evs = Desempeno.listar()
        grupos = {}
        for e in evs:
            area = (e.get('area') or '').strip() or 'Sin área'
            grupos.setdefault(area, []).append(e)
        return [{'area': k, 'evaluaciones': grupos[k]}
                for k in sorted(grupos.keys(), key=lambda x: (x == 'Sin área', x.lower()))]

    @staticmethod
    def get_by_id(evaluacion_id):
        """Devuelve la evaluación completa con criterios, indicadores y promedios."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT e.*, c.nombre_completo AS colaborador_nombre, c.cargo, c.area AS area_colaborador
                    FROM evaluaciones_desempeno e
                    JOIN colaboradores c ON c.id = e.colaborador_id
                    WHERE e.id = %s
                """, (evaluacion_id,))
                row = cur.fetchone()
                if not row:
                    return None
                evaluacion = dict(row)

                cur.execute("""
                    SELECT d.criterio_id, d.indicador_id, d.score_evaluador, d.score_autoevaluacion
                    FROM evaluacion_detalles d WHERE d.evaluacion_id = %s
                """, (evaluacion_id,))
                detalles = [dict(r) for r in cur.fetchall()]
                return Desempeno._armar(evaluacion, detalles)
        finally:
            conn.close()

    @staticmethod
    def _armar(evaluacion, detalles):
        """Calcula promedios por criterio y resultado final."""
        criterios = Desempeno.get_criterios(evaluacion.get('area'))
        det_por_criterio = {}
        for d in detalles:
            det_por_criterio.setdefault(d['criterio_id'], []).append(d)

        lista_criterios = []
        for c in criterios:
            inds = det_por_criterio.get(c['id'], [])
            # mapear indicadores con sus puntajes
            ind_det = {i['indicador_id']: i for i in inds}
            indicadores_out = []
            for ind in c['indicadores']:
                det = ind_det.get(ind['id'])
                indicadores_out.append({
                    'id': ind['id'],
                    'descripcion': ind['descripcion'],
                    'score_evaluador': det['score_evaluador'] if det else None,
                    'score_autoevaluacion': det['score_autoevaluacion'] if det else None,
                })
            ev = [i['score_evaluador'] for i in inds if i.get('score_evaluador') is not None]
            au = [i['score_autoevaluacion'] for i in inds if i.get('score_autoevaluacion') is not None]
            promedio_evaluador = round(sum(_pct(x) for x in ev) / len(ev), 1) if ev else 0.0
            promedio_autoevaluacion = round(sum(_pct(x) for x in au) / len(au), 1) if au else 0.0
            lista_criterios.append({
                'id': c['id'],
                'nombre': c['nombre'],
                'indicadores': indicadores_out,
                'promedio_evaluador': promedio_evaluador,
                'promedio_autoevaluacion': promedio_autoevaluacion,
                'promedio': round((promedio_evaluador + promedio_autoevaluacion) / 2, 1),
            })

        final = round(sum(c['promedio'] for c in lista_criterios) / len(lista_criterios), 1) if lista_criterios else 0.0
        evaluacion['criterios'] = lista_criterios
        evaluacion['resultado_calculado'] = final
        evaluacion['aprobada_calculada'] = final >= MINIMO_APROBACION
        return evaluacion

    @staticmethod
    def crear(data):
        """Crea evaluación (cabecera + detalles) y retorna el ID."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO evaluaciones_desempeno
                    (colaborador_id, evaluador_id, evaluador_nombre, periodo_inicio, periodo_fin,
                     fecha_evaluacion, estado, aspectos_positivos, aspectos_fortalecer, objetivos,
                     area, creado_por, actualizado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data['colaborador_id'],
                    data.get('evaluador_id'),
                    data.get('evaluador_nombre'),
                    data.get('periodo_inicio'),
                    data.get('periodo_fin'),
                    data.get('fecha_evaluacion'),
                    data.get('estado', 'Finalizada'),
                    data.get('aspectos_positivos'),
                    data.get('aspectos_fortalecer'),
                    data.get('objetivos'),
                    data.get('area'),
                    data.get('creado_por'),
                    data.get('creado_por'),
                ))
                evaluacion_id = cur.fetchone()[0]

                for d in data.get('detalles', []):
                    cur.execute("""
                        INSERT INTO evaluacion_detalles
                        (evaluacion_id, criterio_id, indicador_id, score_evaluador, score_autoevaluacion)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (evaluacion_id, d['criterio_id'], d['indicador_id'],
                          d.get('score_evaluador'), d.get('score_autoevaluacion')))

                # Calcular y persistir resultado
                Desempeno._persistir_resultado(cur, evaluacion_id)
                conn.commit()
                return evaluacion_id
        finally:
            conn.close()

    @staticmethod
    def _persistir_resultado(cur, evaluacion_id):
        """Calcula el resultado final y lo guarda en la cabecera."""
        cur.execute("""
            SELECT criterio_id, score_evaluador, score_autoevaluacion
            FROM evaluacion_detalles WHERE evaluacion_id = %s
        """, (evaluacion_id,))
        filas = cur.fetchall()  # tuplas (criterio_id, score_evaluador, score_autoevaluacion)

        por_criterio = {}
        for criterio_id, score_ev, score_au in filas:
            g = por_criterio.setdefault(criterio_id, {'ev': [], 'au': []})
            if score_ev is not None:
                g['ev'].append(score_ev)
            if score_au is not None:
                g['au'].append(score_au)

        promedios = []
        for g in por_criterio.values():
            ev = g['ev']; au = g['au']
            p_ev = sum(_pct(x) for x in ev) / len(ev) if ev else 0.0
            p_au = sum(_pct(x) for x in au) / len(au) if au else 0.0
            promedios.append((p_ev + p_au) / 2)

        final = round(sum(promedios) / len(promedios), 1) if promedios else 0.0
        cur.execute("""
            UPDATE evaluaciones_desempeno
            SET resultado_final = %s, aprobada = %s
            WHERE id = %s
        """, (final, final >= MINIMO_APROBACION, evaluacion_id))

    @staticmethod
    def eliminar(evaluacion_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM evaluaciones_desempeno WHERE id = %s", (evaluacion_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()
