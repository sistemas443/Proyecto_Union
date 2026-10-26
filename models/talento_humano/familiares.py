# models/talento_humano/familiares.py
"""
Modelo para Familiares/Dependientes de Colaboradores - Talento Humano
"""
import psycopg2
import psycopg2.extras

from models.base import get_db_connection, parse_empty, to_float_safe


class Familiar:
    """CRUD para familiares/dependientes de colaboradores"""

    TIPOS_FAMILIAR = (
        'Cónyuge', 'Compañero(a)', 'Hijo(a)', 'Padre', 'Madre', 'Hermano(a)', 'Otro'
    )
    TIPOS_DOC = ('CC', 'CE', 'PAS', 'TI', 'NIT', 'RC')

    @staticmethod
    def get_all(colaborador_id: int, solo_dependientes: bool = False) -> list:
        """Obtiene todos los familiares de un colaborador"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT id, colaborador_id, tipo_familiar, nombre_completo,
                           tipo_documento, numero_documento, fecha_nacimiento, edad,
                           vive_con_colaborador, dependiente_economico, estudia,
                           institucion_educativa, nivel_educativo, trabaja,
                           empresa_trabajo, cargo_trabajo, ingresos_mensuales,
                           telefono, correo, eps_familiar, observaciones,
                           creado_por, creado_en
                    FROM colaborador_familiares
                    WHERE colaborador_id = %s
                """
                if solo_dependientes:
                    sql += " AND dependiente_economico = TRUE"
                sql += " ORDER BY tipo_familiar, nombre_completo"
                cur.execute(sql, (colaborador_id,))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(familiar_id: int) -> dict | None:
        """Obtiene un familiar por ID"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM colaborador_familiares WHERE id = %s
                """, (familiar_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def create(data: dict, usuario_id: int) -> int:
        """Crea nuevo familiar. Retorna ID creado."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Validar tipo familiar
                if data.get('tipo_familiar') not in Familiar.TIPOS_FAMILIAR:
                    raise ValueError(f"Tipo de familiar no válido: {data.get('tipo_familiar')}")

                # Validar tipo documento
                if data.get('tipo_documento') and data['tipo_documento'] not in Familiar.TIPOS_DOC:
                    raise ValueError(f"Tipo de documento no válido: {data['tipo_documento']}")

                cur.execute("""
                    INSERT INTO colaborador_familiares (
                        colaborador_id, tipo_familiar, nombre_completo,
                        tipo_documento, numero_documento, fecha_nacimiento,
                        vive_con_colaborador, dependiente_economico, estudia,
                        institucion_educativa, nivel_educativo, trabaja,
                        empresa_trabajo, cargo_trabajo, ingresos_mensuales,
                        telefono, correo, eps_familiar, observaciones, creado_por
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    data['colaborador_id'], data['tipo_familiar'], data['nombre_completo'],
                    parse_empty(data.get('tipo_documento')), parse_empty(data.get('numero_documento')),
                    parse_empty(data.get('fecha_nacimiento')),
                    data.get('vive_con_colaborador', False), data.get('dependiente_economico', False),
                    data.get('estudia', False),
                    parse_empty(data.get('institucion_educativa')), parse_empty(data.get('nivel_educativo')),
                    data.get('trabaja', False),
                    parse_empty(data.get('empresa_trabajo')), parse_empty(data.get('cargo_trabajo')),
                    to_float_safe(data.get('ingresos_mensuales')),
                    parse_empty(data.get('telefono')), parse_empty(data.get('correo')),
                    parse_empty(data.get('eps_familiar')), parse_empty(data.get('observaciones')),
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
    def update(familiar_id: int, data: dict, usuario_id: int) -> bool:
        """Actualiza familiar. Retorna True si éxito."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Verificar existencia
                cur.execute("SELECT id FROM colaborador_familiares WHERE id = %s", (familiar_id,))
                if not cur.fetchone():
                    raise ValueError("Familiar no encontrado")

                # Validar tipo familiar
                if data.get('tipo_familiar') and data['tipo_familiar'] not in Familiar.TIPOS_FAMILIAR:
                    raise ValueError(f"Tipo de familiar no válido: {data['tipo_familiar']}")

                # Validar tipo documento
                if data.get('tipo_documento') and data['tipo_documento'] not in Familiar.TIPOS_DOC:
                    raise ValueError(f"Tipo de documento no válido: {data['tipo_documento']}")

                cur.execute("""
                    UPDATE colaborador_familiares SET
                        tipo_familiar = %s, nombre_completo = %s,
                        tipo_documento = %s, numero_documento = %s, fecha_nacimiento = %s,
                        vive_con_colaborador = %s, dependiente_economico = %s, estudia = %s,
                        institucion_educativa = %s, nivel_educativo = %s, trabaja = %s,
                        empresa_trabajo = %s, cargo_trabajo = %s, ingresos_mensuales = %s,
                        telefono = %s, correo = %s, eps_familiar = %s, observaciones = %s
                    WHERE id = %s
                """, (
                    data.get('tipo_familiar'), data.get('nombre_completo'),
                    parse_empty(data.get('tipo_documento')), parse_empty(data.get('numero_documento')),
                    parse_empty(data.get('fecha_nacimiento')),
                    data.get('vive_con_colaborador', False), data.get('dependiente_economico', False),
                    data.get('estudia', False),
                    parse_empty(data.get('institucion_educativa')), parse_empty(data.get('nivel_educativo')),
                    data.get('trabaja', False),
                    parse_empty(data.get('empresa_trabajo')), parse_empty(data.get('cargo_trabajo')),
                    to_float_safe(data.get('ingresos_mensuales')),
                    parse_empty(data.get('telefono')), parse_empty(data.get('correo')),
                    parse_empty(data.get('eps_familiar')), parse_empty(data.get('observaciones')),
                    familiar_id
                ))
                conn.commit()
                return cur.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete(familiar_id: int) -> bool:
        """Elimina familiar"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM colaborador_familiares WHERE id = %s", (familiar_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def get_dependientes(colaborador_id: int) -> list:
        """Obtiene solo dependientes económicos"""
        return Familiar.get_all(colaborador_id, solo_dependientes=True)

    @staticmethod
    def get_conteo_por_tipo(colaborador_id: int) -> dict:
        """Obtiene conteo de familiares agrupados por tipo"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT tipo_familiar, COUNT(*) as total
                    FROM colaborador_familiares
                    WHERE colaborador_id = %s
                    GROUP BY tipo_familiar
                """, (colaborador_id,))
                return {row['tipo_familiar']: row['total'] for row in cur.fetchall()}
        finally:
            conn.close()