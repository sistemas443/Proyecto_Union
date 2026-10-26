# models/talento_humano/capacitaciones.py
"""
Modelo para Capacitaciones de Colaboradores - Talento Humano
Cursos obligatorios avícola: Altura, Espacios Confinados, HACCP, Bioseguridad, etc.
"""
import psycopg2
import psycopg2.extras

from models.base import get_db_connection, parse_empty, to_float_safe
from models.talento_humano.colaborador import Colaborador


def _to_int(val):
    """Convierte a entero de forma segura (None si está vacío)."""
    if val is None or str(val).strip() == '':
        return None
    try:
        return int(round(float(str(val).replace(',', '.'))))
    except (TypeError, ValueError):
        return None


class Capacitacion:
    """CRUD para capacitaciones de colaboradores"""

    # Tipos de capacitación válidos (constante compartida con Colaborador)
    TIPOS_CAPACITACION = (
        'Altura', 'Espacios Confinados', 'Manipulación Alimentos', 'Bioseguridad',
        'HACCP', 'BPM', 'Primeros Auxilios', 'Brigadas Emergencia',
        'Manejo Extintores', 'Evacuación', 'Trabajo Seguro', 'Uso EPP',
        'Manejo Residuos', 'Control Plagas', 'Bienestar Animal', 'Otro'
    )

    @staticmethod
    def get_all(colaborador_id: int, activas_solo: bool = True) -> list:
        """Obtiene todas las capacitaciones de un colaborador"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT id, colaborador_id, tipo_capacitacion, nombre_curso, entidad_certificadora,
                           horas_duracion, fecha_inicio, fecha_fin, fecha_vencimiento,
                           certificado_ruta, aprobado, observaciones, creado_por, creado_en
                    FROM colaborador_capacitaciones
                    WHERE colaborador_id = %s
                """
                if activas_solo:
                    sql += " AND (fecha_vencimiento IS NULL OR fecha_vencimiento >= CURRENT_DATE)"
                sql += " ORDER BY fecha_inicio DESC"
                cur.execute(sql, (colaborador_id,))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(capacitacion_id: int) -> dict | None:
        """Obtiene una capacitación por ID"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM colaborador_capacitaciones WHERE id = %s
                """, (capacitacion_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def create(data: dict, usuario_id: int, certificado_file=None) -> int:
        """Crea nueva capacitación. Retorna ID creado."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Validar tipo
                if data.get('tipo_capacitacion') not in Capacitacion.TIPOS_CAPACITACION:
                    raise ValueError(f"Tipo de capacitación no válido: {data.get('tipo_capacitacion')}")

                # Procesar certificado si hay
                certificado_ruta = None
                if certificado_file:
                    certificado_ruta = Capacitacion._procesar_certificado(certificado_file, data['colaborador_id'])

                cur.execute("""
                    INSERT INTO colaborador_capacitaciones (
                        colaborador_id, tipo_capacitacion, nombre_curso, entidad_certificadora,
                        horas_duracion, fecha_inicio, fecha_fin, fecha_vencimiento,
                        certificado_ruta, aprobado, observaciones, creado_por
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    data['colaborador_id'], data['tipo_capacitacion'], data['nombre_curso'],
                    parse_empty(data.get('entidad_certificadora')),
                    _to_int(data.get('horas_duracion')),
                    parse_empty(data.get('fecha_inicio')), parse_empty(data.get('fecha_fin')),
                    parse_empty(data.get('fecha_vencimiento')),
                    None,  # certificado_ruta - se procesa aparte si hay archivo
                    data.get('aprobado', True), parse_empty(data.get('observaciones')), usuario_id
                ))
                nuevo_id = cur.fetchone()[0]

                # Si hay archivo, procesar y actualizar ruta
                if certificado_file:
                    certificado_ruta = Capacitacion._procesar_certificado(certificado_file, data['colaborador_id'], nuevo_id)
                    cur.execute("""
                        UPDATE colaborador_capacitaciones SET certificado_ruta = %s WHERE id = %s
                    """, (certificado_ruta, nuevo_id))

                conn.commit()
                return nuevo_id

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def update(capacitacion_id: int, data: dict, usuario_id: int, certificado_file=None, eliminar_certificado: bool = False) -> bool:
        """Actualiza capacitación. Retorna True si éxito."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Verificar existencia
                cur.execute("SELECT certificado_ruta FROM colaborador_capacitaciones WHERE id = %s", (capacitacion_id,))
                actual = cur.fetchone()
                if not actual:
                    raise ValueError("Capacitación no encontrada")
                certificado_actual = actual[0]

                # Validar tipo
                if data.get('tipo_capacitacion') and data['tipo_capacitacion'] not in Capacitacion.TIPOS_CAPACITACION:
                    raise ValueError(f"Tipo de capacitación no válido: {data['tipo_capacitacion']}")

                # Manejar certificado
                certificado_ruta = certificado_actual
                if eliminar_certificado and certificado_actual:
                    Capacitacion._eliminar_certificado(certificado_actual)
                    certificado_ruta = None
                elif certificado_file:
                    # Eliminar anterior y procesar nuevo
                    if certificado_actual:
                        Capacitacion._eliminar_certificado(certificado_actual)
                    certificado_ruta = Capacitacion._procesar_certificado(certificado_file, data.get('colaborador_id'), capacitacion_id)

                cur.execute("""
                    UPDATE colaborador_capacitaciones SET
                        tipo_capacitacion = %s, nombre_curso = %s, entidad_certificadora = %s,
                        horas_duracion = %s, fecha_inicio = %s, fecha_fin = %s, fecha_vencimiento = %s,
                        certificado_ruta = %s, aprobado = %s, observaciones = %s
                    WHERE id = %s
                """, (
                    data.get('tipo_capacitacion'), data.get('nombre_curso'), parse_empty(data.get('entidad_certificadora')),
                    _to_int(data.get('horas_duracion')),
                    parse_empty(data.get('fecha_inicio')), parse_empty(data.get('fecha_fin')),
                    parse_empty(data.get('fecha_vencimiento')),
                    certificado_ruta, data.get('aprobado', True), parse_empty(data.get('observaciones')),
                    capacitacion_id
                ))
                conn.commit()
                return cur.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete(capacitacion_id: int) -> bool:
        """Elimina capacitación (soft delete eliminando certificado físico)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT certificado_ruta FROM colaborador_capacitaciones WHERE id = %s", (capacitacion_id,))
                actual = cur.fetchone()
                if actual and actual[0]:
                    Capacitacion._eliminar_certificado(actual[0])

                cur.execute("DELETE FROM colaborador_capacitaciones WHERE id = %s", (capacitacion_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _procesar_certificado(file_storage, colaborador_id: int, capacitacion_id: int = None) -> str | None:
        """Procesa certificado: valida, renombra, guarda en carpeta del colaborador"""
        if not file_storage or not file_storage.filename:
            return None

        # Validar tamaño (10 MB máx)
        file_storage.seek(0, 2)
        size = file_storage.tell()
        file_storage.seek(0)
        if size > 10 * 1024 * 1024:
            raise ValueError("El certificado supera el límite de 10 MB")

        # Validar MIME
        mime = file_storage.mimetype or ''
        allowed_mimes = ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
        if mime not in allowed_mimes:
            raise ValueError("Solo se permiten PDF, JPG, PNG, WEBP")

        # Obtener num_doc del colaborador para carpeta
        from models.talento_humano.colaborador import Colaborador
        colab = Colaborador.get_by_id(capacitacion_id) if capacitacion_id else None
        # Si no tenemos capacitacion_id, buscar por colaborador_id
        # Para simplificar, usamos colaborador_id directo en la ruta
        folder = f"static/uploads/colaboradores/{colaborador_id}/capacitaciones"
        import os
        base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
        abs_folder = os.path.join(base_path, folder)
        os.makedirs(abs_folder, exist_ok=True)

        # Nombre único
        import datetime
        ext = os.path.splitext(file_storage.filename)[1].lower()
        if ext not in ('.pdf', '.jpg', '.jpeg', '.png', '.webp'):
            ext = '.pdf'
        filename = f"cert_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        filepath = os.path.join(abs_folder, filename)

        # Guardar
        file_storage.save(filepath)

        # Retornar ruta relativa a static/
        rel_path = os.path.relpath(filepath, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'static'))
        return rel_path.replace('\\', '/')

    @staticmethod
    def _eliminar_certificado(ruta_relativa: str):
        """Elimina archivo físico si existe"""
        if not ruta_relativa:
            return
        import os
        base_static = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'static')
        abs_path = os.path.join(base_static, ruta_relativa)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass

    @staticmethod
    def get_vencidas(colaborador_id: int = None) -> list:
        """Obtiene capacitaciones vencidas o por vencer (30 días)"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT cc.*, c.nombre_completo, c.num_doc, c.cargo, c.area
                    FROM colaborador_capacitaciones cc
                    JOIN colaboradores c ON c.id = cc.colaborador_id
                    WHERE cc.fecha_vencimiento IS NOT NULL
                      AND cc.fecha_vencimiento <= CURRENT_DATE + INTERVAL '30 days'
                      AND c.eliminado_en IS NULL
                """
                params = []
                if colaborador_id:
                    sql += " AND cc.colaborador_id = %s"
                    params.append(colaborador_id)
                sql += " ORDER BY cc.fecha_vencimiento ASC"
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()