# models/talento_humano/documentos.py
"""
Modelo para Documentos de Colaboradores - Talento Humano

Los archivos se guardan en static/uploads/documentos/<colaborador_id>/
y en la BD solo se almacena la ruta relativa a static/.
"""
import os
import uuid
import hashlib
from datetime import datetime

import psycopg2.extras

from models.base import get_db_connection, parse_empty


class Documento:
    """CRUD de documentos del colaborador (con archivo físico)"""

    UPLOAD_ROOT = 'static/uploads/documentos'
    MAX_SIZE_MB = 10
    EXTENSIONES = {
        '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.gif',
        '.doc', '.docx', '.xls', '.xlsx', '.txt',
    }

    # Debe coincidir con el CHECK colaborador_documentos_tipo_documento_check
    TIPOS = (
        'Contrato', 'Hoja de Vida', 'Examenes Medicos', 'Certificado Laboral',
        'Curso Capacitacion', 'Carne Vacunacion', 'ARL', 'EPS', 'Fondo Pension',
        'Fondo Cesantias', 'Cuenta Bancaria', 'Licencia Conduccion', 'Pasaporte',
        'Antecedentes Penales', 'Referencia Personal', 'Referencia Familiar', 'Otro',
    )

    # ------------------------------------------------------------
    # Utilidades de archivos
    # ------------------------------------------------------------
    @staticmethod
    def _base_static() -> str:
        return os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'static')
        )

    @staticmethod
    def ruta_absoluta(ruta_relativa: str) -> str:
        """Convierte 'uploads/documentos/...' en ruta absoluta."""
        if not ruta_relativa:
            return ''
        return os.path.join(Documento._base_static(), ruta_relativa)

    @staticmethod
    def _guardar_archivo(file_storage, colaborador_id: int) -> tuple:
        """
        Valida y guarda el archivo. Retorna
        (nombre_original, nombre_archivo, ruta_relativa, mime, tamano, hash).
        """
        if not file_storage or not file_storage.filename:
            raise ValueError('Debe seleccionar un archivo')

        # Normalizar el nombre (espacios, puntos finales, caracteres invisibles)
        nombre_original = os.path.basename(file_storage.filename)
        nombre_original = (nombre_original
                           .replace('\u200b', '')
                           .replace('\ufeff', '')
                           .strip()
                           .strip('.'))

        ext = os.path.splitext(nombre_original)[1].lower().strip()
        mime = (file_storage.mimetype or '').lower()

        if ext not in Documento.EXTENSIONES:
            # Algunos navegadores no envían la extensión: aceptar PDF por MIME
            if mime == 'application/pdf':
                ext = '.pdf'
                if not nombre_original.lower().endswith('.pdf'):
                    nombre_original = f'{nombre_original or "documento"}.pdf'
            else:
                permitidas = ', '.join(sorted(Documento.EXTENSIONES))
                raise ValueError(
                    f'Formato no permitido ({ext or "sin extensión"}). '
                    f'Use PDF, Word, Excel, imágenes o TXT. Extensiones: {permitidas}'
                )

        # Leer contenido para tamaño y hash
        file_storage.seek(0)
        contenido = file_storage.read()
        file_storage.seek(0)

        tamano = len(contenido)
        if tamano == 0:
            raise ValueError('El archivo está vacío')
        if tamano > Documento.MAX_SIZE_MB * 1024 * 1024:
            raise ValueError(
                f'El archivo supera el límite de {Documento.MAX_SIZE_MB} MB '
                f'({tamano / 1024 / 1024:.1f} MB)'
            )

        hash_sha256 = hashlib.sha256(contenido).hexdigest()

        carpeta = os.path.join(Documento._base_static(), 'uploads', 'documentos', str(colaborador_id))
        os.makedirs(carpeta, exist_ok=True)

        nombre_archivo = f'{uuid.uuid4().hex}{ext}'
        with open(os.path.join(carpeta, nombre_archivo), 'wb') as f:
            f.write(contenido)

        ruta_relativa = f'uploads/documentos/{colaborador_id}/{nombre_archivo}'
        mime = mime or 'application/octet-stream'

        return nombre_original, nombre_archivo, ruta_relativa, mime, tamano, hash_sha256

    @staticmethod
    def _borrar_archivo(ruta_relativa: str):
        """Elimina el archivo físico (silencioso si no existe)."""
        ruta = Documento.ruta_absoluta(ruta_relativa)
        if ruta and os.path.exists(ruta):
            try:
                os.remove(ruta)
            except OSError:
                pass

    # ------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------
    @staticmethod
    def get_all(colaborador_id: int, incluir_eliminados: bool = False) -> list:
        """Documentos de un colaborador."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT id, colaborador_id, tipo_documento, nombre_original,
                           nombre_archivo, ruta_archivo, mime_type, tamano_bytes,
                           hash_sha256, fecha_documento, fecha_subida, fecha_vencimiento,
                           observaciones, subido_por, eliminado_en,
                           (fecha_vencimiento - CURRENT_DATE) AS dias_restantes
                    FROM colaborador_documentos
                    WHERE colaborador_id = %s
                """
                if not incluir_eliminados:
                    sql += ' AND eliminado_en IS NULL'
                sql += ' ORDER BY fecha_subida DESC, id DESC'
                cur.execute(sql, (colaborador_id,))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(doc_id: int, incluir_eliminados: bool = False) -> dict | None:
        """Documento por ID."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT *, (fecha_vencimiento - CURRENT_DATE) AS dias_restantes
                    FROM colaborador_documentos WHERE id = %s
                """
                if not incluir_eliminados:
                    sql += ' AND eliminado_en IS NULL'
                cur.execute(sql, (doc_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_global(filtros: dict | None = None) -> list:
        """
        Listado global de documentos con datos del colaborador.
        filtros: colaborador_id, tipo, q (nombre o documento), estado
                 (todos | vigentes | por_vencer | vencidos), sin_vencimiento
        """
        filtros = filtros or {}
        where = [
            'd.eliminado_en IS NULL',
            "c.eliminado_en IS NULL",
        ]
        params = []

        if filtros.get('colaborador_id'):
            where.append('d.colaborador_id = %s')
            params.append(int(filtros['colaborador_id']))

        if filtros.get('tipo'):
            where.append('d.tipo_documento = %s')
            params.append(filtros['tipo'])

        if filtros.get('q'):
            where.append('(c.nombre_completo ILIKE %s OR c.num_doc ILIKE %s)')
            like = f"%{filtros['q']}%"
            params.extend([like, like])

        estado = (filtros.get('estado') or 'todos').lower()
        if estado == 'por_vencer':
            where.append("d.fecha_vencimiento BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'")
        elif estado == 'vencidos':
            where.append('d.fecha_vencimiento < CURRENT_DATE')
        elif estado == 'vigentes':
            where.append('(d.fecha_vencimiento IS NULL OR d.fecha_vencimiento >= CURRENT_DATE)')
        elif estado == 'sin_vencimiento':
            where.append('d.fecha_vencimiento IS NULL')

        sql = f"""
            SELECT d.id, d.colaborador_id, d.tipo_documento, d.nombre_original,
                   d.ruta_archivo, d.mime_type, d.tamano_bytes, d.fecha_documento,
                   d.fecha_subida, d.fecha_vencimiento, d.observaciones,
                   (d.fecha_vencimiento - CURRENT_DATE) AS dias_restantes,
                   c.nombre_completo, c.num_doc, c.cargo, c.area
            FROM colaborador_documentos d
            JOIN colaboradores c ON c.id = d.colaborador_id
            WHERE {' AND '.join(where)}
            ORDER BY d.fecha_subida DESC, d.id DESC
            LIMIT 500
        """
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_resumen(colaborador_id: int) -> dict:
        """Totales por estado para el colaborador."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE fecha_vencimiento < CURRENT_DATE) AS vencidos,
                        COUNT(*) FILTER (
                            WHERE fecha_vencimiento >= CURRENT_DATE
                              AND fecha_vencimiento <= CURRENT_DATE + INTERVAL '30 days'
                        ) AS por_vencer,
                        COUNT(*) FILTER (WHERE fecha_vencimiento IS NULL) AS sin_vencimiento
                    FROM colaborador_documentos
                    WHERE colaborador_id = %s AND eliminado_en IS NULL
                """, (colaborador_id,))
                resumen = dict(cur.fetchone())

                cur.execute("""
                    SELECT tipo_documento, COUNT(*) AS total
                    FROM colaborador_documentos
                    WHERE colaborador_id = %s AND eliminado_en IS NULL
                    GROUP BY tipo_documento
                """, (colaborador_id,))
                resumen['por_tipo'] = {r['tipo_documento']: r['total'] for r in cur.fetchall()}
                return resumen
        finally:
            conn.close()

    @staticmethod
    def get_estadisticas() -> dict:
        """Estadísticas globales del módulo de documentos."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE d.fecha_vencimiento < CURRENT_DATE) AS vencidos,
                        COUNT(*) FILTER (
                            WHERE d.fecha_vencimiento >= CURRENT_DATE
                              AND d.fecha_vencimiento <= CURRENT_DATE + INTERVAL '30 days'
                        ) AS por_vencer,
                        COUNT(DISTINCT d.colaborador_id) AS colaboradores
                    FROM colaborador_documentos d
                    JOIN colaboradores c ON c.id = d.colaborador_id
                    WHERE d.eliminado_en IS NULL AND c.eliminado_en IS NULL
                """)
                return dict(cur.fetchone())
        finally:
            conn.close()

    # ------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------
    @staticmethod
    def create(colaborador_id: int, data: dict, file_storage, usuario_id: int) -> int:
        """Registra un documento nuevo con su archivo. Retorna el ID."""
        tipo = (data.get('tipo_documento') or '').strip()
        if tipo not in Documento.TIPOS:
            raise ValueError(f'Tipo de documento no válido: {tipo or "(vacío)"}')

        conn = get_db_connection()
        ruta_creada = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT id FROM colaboradores WHERE id = %s AND eliminado_en IS NULL',
                    (colaborador_id,)
                )
                if not cur.fetchone():
                    raise ValueError('Colaborador no encontrado')

                (nombre_original, nombre_archivo, ruta_relativa,
                 mime, tamano, hash_sha) = Documento._guardar_archivo(file_storage, colaborador_id)
                ruta_creada = ruta_relativa

                # Evitar duplicados exactos
                cur.execute("""
                    SELECT id FROM colaborador_documentos
                    WHERE colaborador_id = %s AND hash_sha256 = %s AND eliminado_en IS NULL
                """, (colaborador_id, hash_sha))
                if cur.fetchone():
                    raise ValueError('Este archivo ya está cargado para este colaborador')

                cur.execute("""
                    INSERT INTO colaborador_documentos (
                        colaborador_id, tipo_documento, nombre_original, nombre_archivo,
                        ruta_archivo, mime_type, tamano_bytes, hash_sha256,
                        fecha_documento, fecha_vencimiento, observaciones, subido_por
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    colaborador_id, tipo, nombre_original, nombre_archivo,
                    ruta_relativa, mime, tamano, hash_sha,
                    parse_empty(data.get('fecha_documento')),
                    parse_empty(data.get('fecha_vencimiento')),
                    parse_empty(data.get('observaciones')),
                    usuario_id,
                ))
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id

        except Exception:
            conn.rollback()
            if ruta_creada:
                Documento._borrar_archivo(ruta_creada)
            raise
        finally:
            conn.close()

    @staticmethod
    def update(doc_id: int, data: dict, usuario_id: int) -> bool:
        """Actualiza metadatos del documento."""
        tipo = (data.get('tipo_documento') or '').strip()
        if tipo and tipo not in Documento.TIPOS:
            raise ValueError(f'Tipo de documento no válido: {tipo}')

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT id FROM colaborador_documentos WHERE id = %s AND eliminado_en IS NULL',
                    (doc_id,)
                )
                if not cur.fetchone():
                    raise ValueError('Documento no encontrado')

                cur.execute("""
                    UPDATE colaborador_documentos SET
                        tipo_documento = %s,
                        fecha_documento = %s,
                        fecha_vencimiento = %s,
                        observaciones = %s
                    WHERE id = %s
                """, (
                    tipo,
                    parse_empty(data.get('fecha_documento')),
                    parse_empty(data.get('fecha_vencimiento')),
                    parse_empty(data.get('observaciones')),
                    doc_id,
                ))
                conn.commit()
                return cur.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete(doc_id: int, usuario_id: int | None = None) -> bool:
        """Baja lógica + eliminación del archivo físico."""
        conn = get_db_connection()
        ruta = None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ruta_archivo FROM colaborador_documentos
                    WHERE id = %s AND eliminado_en IS NULL
                """, (doc_id,))
                row = cur.fetchone()
                if not row:
                    return False
                ruta = row[0]

                cur.execute("""
                    UPDATE colaborador_documentos SET eliminado_en = NOW()
                    WHERE id = %s
                """, (doc_id,))
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        Documento._borrar_archivo(ruta)
        return True

    @staticmethod
    def contar_por_tipo(colaborador_id: int) -> dict:
        """Alias corto de get_resumen()['por_tipo']"""
        return Documento.get_resumen(colaborador_id).get('por_tipo', {})
