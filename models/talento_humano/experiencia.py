# models/talento_humano/experiencia.py
"""
Modelo para Experiencia Laboral Anterior de Colaboradores - Talento Humano
"""
import psycopg2
import psycopg2.extras

from models.base import get_db_connection, parse_empty, to_float_safe


class Experiencia:
    """CRUD para experiencia laboral anterior de colaboradores"""

    MOTIVOS_RETIRO = (
        'Renuncia', 'Despido', 'Fin Contrato', 'Jubilación',
        'Mutuo Acuerdo', 'Salud', 'Estudio', 'Otro'
    )

    @staticmethod
    def get_all(colaborador_id: int) -> list:
        """Obtiene toda la experiencia laboral de un colaborador"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, colaborador_id, empresa, cargo, fecha_inicio, fecha_fin,
                           tiempo_meses, jefe_inmediato, telefono_referencia, motivo_retiro,
                           sector_empresa, funciones_principales, creado_por, creado_en
                    FROM colaborador_experiencia
                    WHERE colaborador_id = %s
                    ORDER BY fecha_inicio DESC
                """, (colaborador_id,))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(experiencia_id: int) -> dict | None:
        """Obtiene una experiencia por ID"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM colaborador_experiencia WHERE id = %s
                """, (experiencia_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def create(data: dict, usuario_id: int) -> int:
        """Crea nueva experiencia laboral. Retorna ID creado."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Validar motivo retiro si hay fecha_fin
                if data.get('fecha_fin') and data.get('motivo_retiro'):
                    if data['motivo_retiro'] not in Experiencia.MOTIVOS_RETIRO:
                        raise ValueError(f"Motivo de retiro no válido: {data['motivo_retiro']}")

                cur.execute("""
                    INSERT INTO colaborador_experiencia (
                        colaborador_id, empresa, cargo, fecha_inicio, fecha_fin,
                        jefe_inmediato, telefono_referencia, motivo_retiro,
                        sector_empresa, funciones_principales, creado_por
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    data['colaborador_id'], data['empresa'], data['cargo'],
                    parse_empty(data.get('fecha_inicio')), parse_empty(data.get('fecha_fin')),
                    parse_empty(data.get('jefe_inmediato')), parse_empty(data.get('telefono_referencia')),
                    parse_empty(data.get('motivo_retiro')),
                    parse_empty(data.get('sector_empresa')), parse_empty(data.get('funciones_principales')),
                    usuario_id
                ))
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def update(experiencia_id: int, data: dict, usuario_id: int) -> bool:
        """Actualiza experiencia laboral. Retorna True si éxito."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Verificar existencia
                cur.execute("SELECT id FROM colaborador_experiencia WHERE id = %s", (experiencia_id,))
                if not cur.fetchone():
                    raise ValueError("Experiencia laboral no encontrada")

                # Validar motivo retiro si hay fecha_fin
                if data.get('fecha_fin') and data.get('motivo_retiro'):
                    if data['motivo_retiro'] not in Experiencia.MOTIVOS_RETIRO:
                        raise ValueError(f"Motivo de retiro no válido: {data['motivo_retiro']}")

                cur.execute("""
                    UPDATE colaborador_experiencia SET
                        empresa = %s, cargo = %s, fecha_inicio = %s, fecha_fin = %s,
                        jefe_inmediato = %s, telefono_referencia = %s, motivo_retiro = %s,
                        sector_empresa = %s, funciones_principales = %s
                    WHERE id = %s
                """, (
                    data.get('empresa'), data.get('cargo'),
                    parse_empty(data.get('fecha_inicio')), parse_empty(data.get('fecha_fin')),
                    parse_empty(data.get('jefe_inmediato')), parse_empty(data.get('telefono_referencia')),
                    parse_empty(data.get('motivo_retiro')),
                    parse_empty(data.get('sector_empresa')), parse_empty(data.get('funciones_principales')),
                    experiencia_id
                ))
                conn.commit()
                return cur.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete(experiencia_id: int) -> bool:
        """Elimina experiencia laboral"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM colaborador_experiencia WHERE id = %s", (experiencia_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()