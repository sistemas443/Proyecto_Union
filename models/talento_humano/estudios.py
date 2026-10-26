# models/talento_humano/estudios.py
"""
Modelo de Estudios (formación académica) del colaborador.
Fase actual: lectura para la Hoja de Vida.
"""
import psycopg2.extras

from models.base import get_db_connection


class Estudio:
    """Formación académica registrada para un colaborador."""

    NIVELES = (
        'Primaria', 'Secundaria', 'Técnico', 'Tecnólogo',
        'Pregrado', 'Especialización', 'Maestría', 'Doctorado', 'Otro'
    )

    @staticmethod
    def get_all(colaborador_id: int) -> list:
        """Estudios de un colaborador, del más reciente al más antiguo."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, colaborador_id, nivel, titulo, institucion,
                           ciudad_institucion, fecha_inicio, fecha_fin,
                           fecha_graduacion, esta_cursando, certificado_ruta,
                           observaciones, creado_por, creado_en
                    FROM colaborador_estudios
                    WHERE colaborador_id = %s
                    ORDER BY fecha_inicio DESC NULLS LAST
                """, (colaborador_id,))
                return cur.fetchall()
        finally:
            conn.close()
