# models/talento_humano/cursos.py
"""
Modelo de Cursos complementarios del colaborador.
Fase actual: lectura para la Hoja de Vida.
"""
import psycopg2.extras

from models.base import get_db_connection


class Curso:
    """Cursos / diplomados registrados para un colaborador."""

    MODALIDADES = ('Presencial', 'Virtual', 'Mixta', 'Otro')

    @staticmethod
    def get_all(colaborador_id: int) -> list:
        """Cursos de un colaborador, del más reciente al más antiguo."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, colaborador_id, nombre_curso, entidad_organizadora,
                           modalidad, horas_duracion, fecha_inicio, fecha_fin,
                           fecha_vencimiento, certificado_ruta, puntaje,
                           aprobado, observaciones, creado_por, creado_en
                    FROM colaborador_cursos
                    WHERE colaborador_id = %s
                    ORDER BY fecha_inicio DESC NULLS LAST
                """, (colaborador_id,))
                return cur.fetchall()
        finally:
            conn.close()
