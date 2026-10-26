# models/talento_humano/colaborador.py
"""
Modelo para gestión de Colaboradores - Talento Humano
Siguiendo patrones del proyecto: clases estáticas, psycopg2, DictCursor
"""
import os
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps

from models.base import get_db_connection, parse_empty, to_float_safe
import psycopg2
import psycopg2.extras


class Colaborador:
    """CRUD y utilidades para tabla colaboradores"""

    # --- CONFIGURACIÓN ARCHIVOS ---
    FOTO_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
    FOTO_DIMS = (300, 300)
    FOTO_QUALITY = 85
    UPLOAD_ROOT = 'static/uploads/colaboradores'

    # Tipos de documento válidos
    TIPOS_DOC = ('CC', 'CE', 'PAS', 'TI', 'NIT')
    GENEROS = ('M', 'F', 'O')
    ESTADOS_CIVILES = ('Soltero', 'Casado', 'Union Libre', 'Separado', 'Divorciado', 'Viudo')
    RHS = ('O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-')
    TIPOS_CONTRATO = ('Indefinido', 'Fijo', 'Obra', 'Aprendizaje', 'Prestacion Servicios', 'Temporal')
    ESTADOS = ('Activo', 'Inactivo', 'Licencia', 'Suspendido', 'Retirado', 'Fallecido')
    TIPOS_CUENTA = ('Ahorros', 'Corriente')
    NIVELES_EDUCATIVOS = ('Ninguno', 'Primaria', 'Secundaria', 'Tecnico', 'Tecnologo', 'Profesional',
                          'Especializacion', 'Maestria', 'Doctorado')
    ETNIAS = ('Ninguna', 'Indigena', 'Raizal', 'Palenquero', 'Negro/Afro', 'ROM', 'Otro')
    PAISES = ('Colombia', 'Venezuela', 'Ecuador', 'Peru', 'Panama', 'Otro')

    # --- NUEVAS LISTAS PARA CAMPOS ADICIONALES ---
    TIPOS_VINCULACION = ('Empleado', 'Contratista', 'Aprendiz', 'Practicante', 'Temporal', 'Misionero')
    CLASES_RIESGO_ARL = ('1', '2', '3', '4', '5')
    TIPOS_VINCULACION_CONTRATO = ('Empleado', 'Contratista', 'Aprendiz', 'Practicante', 'Temporal', 'Misionero')
    TIPOS_EXAMEN = ('Ingreso', 'Periódico', 'Retiro', 'Cambio Cargo', 'Post Incapacidad', 'Post Licencia')
    RESULTADOS_EXAMEN = ('Apto', 'Apto con Restricciones', 'No Apto')
    RIESGOS_CARDIOVASCULAR = ('Bajo', 'Moderado', 'Alto', 'Muy Alto')
    TIPOS_DISCAPACIDAD = ('Física', 'Sensorial', 'Mental', 'Múltiple', 'Otra')
    TIPOS_VIVIENDA = ('Propia', 'Arriendo', 'Familiar', 'Empresa', 'Otra')
    TIPOS_INMUEBLE = ('Casa', 'Apartamento', 'Finca', 'Habitación', 'Otro')
    TRANSPORTES = ('Propio', 'Público', 'Empresa', 'Mixto', 'Bicicleta', 'Caminando')
    TIPOS_VACUNA = ('COVID', 'Influenza', 'Hepatitis B', 'Tétanos', 'Fiebre Amarilla')
    RESULTADOS_VISUAL = ('Normal', 'Con Corrección', 'Anormal')
    RESULTADOS_AUDITIVO = ('Normal', 'Hipoacusia Leve', 'Hipoacusia Moderada', 'Hipoacusia Severa', 'Anormal')
    RESULTADOS_ESPIROMETRIA = ('Normal', 'Obstructivo Leve', 'Obstructivo Moderado', 'Obstructivo Severo', 'Restrictivo', 'Anormal')
    RESULTADOS_RX = ('Normal', 'Anormal')
    RESULTADOS_COVID = ('Positivo', 'Negativo', 'No Realizada')
    TIPOS_CAPACITACION = ('Altura', 'Espacios Confinados', 'Manipulación Alimentos', 'Bioseguridad',
                          'HACCP', 'BPM', 'Primeros Auxilios', 'Brigadas Emergencia',
                          'Manejo Extintores', 'Evacuación', 'Trabajo Seguro', 'Uso EPP',
                          'Manejo Residuos', 'Control Plagas', 'Bienestar Animal', 'Otro')
    MOTIVOS_RETIRO = ('Renuncia', 'Despido', 'Fin Contrato', 'Jubilación', 'Mutuo Acuerdo', 'Salud', 'Estudio', 'Otro')
    TIPOS_FAMILIAR = ('Cónyuge', 'Compañero(a)', 'Hijo(a)', 'Padre', 'Madre', 'Hermano(a)', 'Otro')
    TIPOS_DOC_FAMILIAR = ('CC', 'CE', 'PAS', 'TI', 'NIT', 'RC')

    @staticmethod
    def _mapear_campos_adicionales(data: dict) -> dict:
        """Mapea campos adicionales con parse_empty y tipos correctos"""
        mapped = {}
        campos_fecha = (
            'fecha_expedicion_doc', 'fecha_vencimiento_doc', 'fecha_nacimiento', 'fecha_ingreso',
            'fecha_ultimo_examen_medico', 'vacuna_covid_fecha',
            'vacuna_influenza_fecha', 'vacuna_hepatitis_fecha', 'vacuna_tetanos_fecha',
            'vacuna_fiebre_amarilla_fecha', 'examen_visual_fecha', 'examen_auditivo_fecha',
            'espirometria_fecha',
            'certificado_discapacidad_vencimiento'
        )
        campos_int = (
            'estrato', 'num_hijos', 'num_dependientes_economicos', 'tiempo_traslado_minutos',
            'certificado_discapacidad_porcentaje', 'vacuna_covid_dosis',
            'certificado_discapacidad_porcentaje'
        )
        campos_bool = (
            'discapacidad', 'victima_conflicto', 'comunidad_lgtbi',
            'desplazado', 'tiene_servicios_publicos', 'tiene_internet',
            'epp_casco', 'epp_botas', 'epp_guantes', 'epp_gafas', 'epp_tapabocas', 'epp_overol',
            'epp_botas_dielectricas', 'epp_arnes', 'epp_chaleco_reflectivo', 'epp_proteccion_auditiva',
            'vive_con_colaborador', 'dependiente_economico', 'estudia', 'trabaja'
        )
        
        for campo, valor in data.items():
            if campo in campos_fecha:
                mapped[campo] = parse_empty(valor)
            elif campo in campos_int:
                mapped[campo] = parse_empty(valor, cast_int=True)
            elif campo in campos_bool:
                mapped[campo] = bool(valor) if valor not in (None, '', '0', 0) else False
            else:
                mapped[campo] = parse_empty(valor)
        return mapped

    @staticmethod
    def _get_upload_folder(num_doc: str) -> str:
        """Ruta absoluta de la carpeta del colaborador"""
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', Colaborador.UPLOAD_ROOT, num_doc)
        return os.path.abspath(base)

    @staticmethod
    def _procesar_foto(file_storage, num_doc: str) -> str | None:
        """
        Procesa foto: valida, redimensiona a 300x300, convierte a JPG 85%, guarda en carpeta del colaborador.
        Retorna nombre del archivo guardado (relativo a static/) o None.
        """
        if not file_storage or not file_storage.filename:
            return None

        # Validar tamaño
        file_storage.seek(0, os.SEEK_END)
        size = file_storage.tell()
        file_storage.seek(0)
        if size > Colaborador.FOTO_MAX_SIZE:
            raise ValueError(f"La foto supera el límite de 5 MB ({size/1024/1024:.1f} MB)")

        # Validar MIME
        mime = file_storage.mimetype or ''
        if not mime.startswith('image/'):
            raise ValueError("El archivo no es una imagen válida")

        # Preparar carpeta
        folder = Colaborador._get_upload_folder(num_doc)
        os.makedirs(folder, exist_ok=True)

        # Nombre único
        ext = '.jpg'  # Forzamos JPG
        filename = f"foto_perfil_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        filepath = os.path.join(folder, filename)

        # Procesar con Pillow
        img = Image.open(file_storage)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        img_cuadrada = ImageOps.fit(img, Colaborador.FOTO_DIMS, Image.Resampling.LANCZOS)
        img_cuadrada.save(filepath, format='JPEG', optimize=True, quality=Colaborador.FOTO_QUALITY)

        # Retornar ruta relativa a static/
        rel_path = os.path.relpath(filepath, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'static'))
        return rel_path.replace('\\', '/')

    @staticmethod
    def _eliminar_foto_anterior(ruta_relativa: str):
        """Elimina archivo físico si existe"""
        if not ruta_relativa:
            return
        base_static = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'static')
        abs_path = os.path.join(base_static, ruta_relativa)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass  # Silencioso, no rompe la transacción

    # --- CRUD PRINCIPAL ---

    @staticmethod
    def get_all(filtros: dict | None = None, pagina: int = 1, por_pagina: int = 50) -> tuple[list, int]:
        """
        Retorna (lista_colaboradores, total_registros)
        Soporta filtros: busqueda (texto), estado, area, cargo
        """
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                where_clauses = ["c.eliminado_en IS NULL"]
                params = []

                if filtros:
                    if filtros.get('busqueda'):
                        where_clauses.append("""
                            (c.nombre_completo ILIKE %s OR c.num_doc ILIKE %s OR c.cargo ILIKE %s OR c.area ILIKE %s)
                        """)
                        like = f"%{filtros['busqueda']}%"
                        params.extend([like, like, like, like])

                    if filtros.get('estado'):
                        where_clauses.append("c.estado = %s")
                        params.append(filtros['estado'])

                    if filtros.get('area'):
                        where_clauses.append("c.area ILIKE %s")
                        params.append(f"%{filtros['area']}%")

                    if filtros.get('cargo'):
                        where_clauses.append("c.cargo ILIKE %s")
                        params.append(f"%{filtros['cargo']}%")

                where_sql = " AND ".join(where_clauses)

                # Total
                cur.execute(f"SELECT COUNT(*) FROM colaboradores c WHERE {where_sql}", params)
                total = cur.fetchone()[0]

                # Paginación
                offset = (pagina - 1) * por_pagina
                cur.execute(f"""
                    SELECT 
                        c.id, c.tipo_doc, c.num_doc, c.nombre_completo, c.cargo, c.area,
                        c.eps, c.arl,
                        c.estado, c.fecha_ingreso, c.foto_perfil,
                        COUNT(DISTINCT d.id) FILTER (WHERE d.eliminado_en IS NULL) AS total_documentos,
                        COUNT(DISTINCT d.id) FILTER (WHERE d.eliminado_en IS NULL AND d.fecha_vencimiento < CURRENT_DATE) AS docs_vencidos,
                        COUNT(DISTINCT e.id) AS total_estudios,
                        COUNT(DISTINCT cu.id) AS total_cursos
                    FROM colaboradores c
                    LEFT JOIN colaborador_documentos d ON d.colaborador_id = c.id
                    LEFT JOIN colaborador_estudios e ON e.colaborador_id = c.id
                    LEFT JOIN colaborador_cursos cu ON cu.colaborador_id = c.id
                    WHERE {where_sql}
                    GROUP BY c.id
                    ORDER BY c.nombre_completo ASC
                    LIMIT %s OFFSET %s
                """, params + [por_pagina, offset])

                return cur.fetchall(), total

        finally:
            conn.close()

    @staticmethod
    def get_by_id(colaborador_id: int) -> dict | None:
        """Obtiene colaborador completo por ID"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM colaboradores WHERE id = %s AND eliminado_en IS NULL
                """, (colaborador_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_by_num_doc(num_doc: str) -> dict | None:
        """Obtiene colaborador por número de documento (para validar unicidad)"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, num_doc, nombre_completo FROM colaboradores 
                    WHERE num_doc = %s AND eliminado_en IS NULL
                """, (num_doc,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _pares_formulario(data: dict, ce: dict, foto_rel, usuario_id: int,
                          es_actualizacion: bool = False) -> list:
        """
        Lista única de (columna, valor) usada por INSERT y UPDATE.
        Evita que las columnas y los valores se desalineen.
        """
        columna_usuario = 'actualizado_por' if es_actualizacion else 'creado_por'
        return [
            # --- Datos base ---
            ('tipo_doc', data['tipo_doc']),
            ('num_doc', data['num_doc']),
            ('primer_nombre', data['primer_nombre']),
            ('segundo_nombre', parse_empty(data.get('segundo_nombre'))),
            ('primer_apellido', data['primer_apellido']),
            ('segundo_apellido', parse_empty(data.get('segundo_apellido'))),
            ('fecha_nacimiento', parse_empty(data.get('fecha_nacimiento'))),
            ('genero', parse_empty(data.get('genero'))),
            ('estado_civil', parse_empty(data.get('estado_civil'))),
            ('rh', parse_empty(data.get('rh'))),
            ('correo_personal', parse_empty(data.get('correo_personal'))),
            ('celular', parse_empty(data.get('celular'))),
            ('telefono', parse_empty(data.get('telefono'))),
            ('direccion', parse_empty(data.get('direccion'))),
            ('ciudad', parse_empty(data.get('ciudad'))),
            ('departamento', parse_empty(data.get('departamento'))),
            ('contacto_emergencia_nombre', parse_empty(data.get('contacto_emergencia_nombre'))),
            ('contacto_emergencia_telefono', parse_empty(data.get('contacto_emergencia_telefono'))),
            ('contacto_emergencia_parentesco', parse_empty(data.get('contacto_emergencia_parentesco'))),
            ('cargo', parse_empty(data.get('cargo'))),
            ('area', parse_empty(data.get('area'))),
            ('centro_costo', parse_empty(data.get('centro_costo'))),
            ('jefe_inmediato_id', parse_empty(data.get('jefe_inmediato_id'), cast_int=True)),
            ('tipo_contrato', parse_empty(data.get('tipo_contrato'))),
            ('fecha_ingreso', parse_empty(data.get('fecha_ingreso'))),
            ('estado', data.get('estado', 'Activo')),
            ('eps', parse_empty(data.get('eps'))),
            ('arl', parse_empty(data.get('arl'))),
            ('fondo_pension', parse_empty(data.get('fondo_pension'))),
            ('fondo_cesantias', parse_empty(data.get('fondo_cesantias'))),
            ('caja_compensacion', parse_empty(data.get('caja_compensacion'))),
            ('banco', parse_empty(data.get('banco'))),
            ('tipo_cuenta', parse_empty(data.get('tipo_cuenta'))),
            ('numero_cuenta', parse_empty(data.get('numero_cuenta'))),
            ('nivel_educativo', parse_empty(data.get('nivel_educativo'))),
            ('profesion_oficio', parse_empty(data.get('profesion_oficio'))),
            ('estrato', parse_empty(data.get('estrato'), cast_int=True)),
            ('sisben', parse_empty(data.get('sisben'))),
            ('discapacidad', data.get('discapacidad', False)),
            ('victima_conflicto', data.get('victima_conflicto', False)),
            ('pais_origen', parse_empty(data.get('pais_origen', 'Colombia'))),
            ('etnia', parse_empty(data.get('etnia'))),
            ('comunidad_lgtbi', data.get('comunidad_lgtbi', False)),
            ('foto_perfil', foto_rel),
            (columna_usuario, usuario_id),

            # --- Identificación ---
            ('lugar_expedicion_doc', ce.get('lugar_expedicion_doc')),
            ('fecha_expedicion_doc', ce.get('fecha_expedicion_doc')),
            ('fecha_vencimiento_doc', ce.get('fecha_vencimiento_doc')),

            # --- Datos personales ---
            ('lugar_nacimiento_ciudad', ce.get('lugar_nacimiento_ciudad')),
            ('lugar_nacimiento_departamento', ce.get('lugar_nacimiento_departamento')),
            ('lugar_nacimiento_pais', ce.get('lugar_nacimiento_pais')),
            ('nacionalidad', ce.get('nacionalidad')),
            ('grupo_sanguineo', ce.get('grupo_sanguineo')),
            ('factor_rh', ce.get('factor_rh')),
            ('religion', ce.get('religion')),
            ('nombre_conyuge', ce.get('nombre_conyuge')),
            ('documento_conyuge', ce.get('documento_conyuge')),
            ('telefono_conyuge', ce.get('telefono_conyuge')),
            ('ocupacion_conyuge', ce.get('ocupacion_conyuge')),
            ('empresa_conyuge', ce.get('empresa_conyuge')),

            # --- Contacto de emergencia ---
            ('contacto_emergencia_direccion', ce.get('contacto_emergencia_direccion')),
            ('contacto_emergencia_correo', ce.get('contacto_emergencia_correo')),
            ('contacto_emergencia2_nombre', ce.get('contacto_emergencia2_nombre')),
            ('contacto_emergencia2_telefono', ce.get('contacto_emergencia2_telefono')),
            ('contacto_emergencia2_parentesco', ce.get('contacto_emergencia2_parentesco')),
            ('contacto_emergencia2_direccion', ce.get('contacto_emergencia2_direccion')),
            ('contacto_emergencia2_correo', ce.get('contacto_emergencia2_correo')),

            # --- Laboral ---
            ('sede_planta', ce.get('sede_planta')),
            ('tipo_vinculacion', ce.get('tipo_vinculacion')),
            ('clase_riesgo_arl', ce.get('clase_riesgo_arl')),

            # --- Sociodemográfico ---
            ('num_hijos', ce.get('num_hijos')),
            ('num_dependientes_economicos', ce.get('num_dependientes_economicos')),
            ('tipo_vivienda', ce.get('tipo_vivienda')),
            ('tipo_vivienda_detalle', ce.get('tipo_vivienda_detalle')),
            ('servicios_publicos', ce.get('servicios_publicos')),
            ('tiene_servicios_publicos', ce.get('tiene_servicios_publicos', False)),
            ('tiene_internet', ce.get('tiene_internet', False)),
            ('transporte_tipo', ce.get('transporte_tipo')),
            ('tiempo_traslado_minutos', ce.get('tiempo_traslado_minutos')),
            ('desplazado', ce.get('desplazado')),
            ('registro_unico_victimas', ce.get('registro_unico_victimas')),
            ('certificado_discapacidad_numero', ce.get('certificado_discapacidad_numero')),
            ('certificado_discapacidad_porcentaje', ce.get('certificado_discapacidad_porcentaje')),
            ('certificado_discapacidad_entidad', ce.get('certificado_discapacidad_entidad')),
            ('certificado_discapacidad_vencimiento', ce.get('certificado_discapacidad_vencimiento')),
            ('tipo_discapacidad', ce.get('tipo_discapacidad')),

            # --- Salud ocupacional ---
            ('fecha_ultimo_examen_medico', ce.get('fecha_ultimo_examen_medico')),
            ('tipo_ultimo_examen', ce.get('tipo_ultimo_examen')),
            ('resultado_examen', ce.get('resultado_examen')),
            ('restricciones_medicas', ce.get('restricciones_medicas')),
            ('alergias_conocidas', ce.get('alergias_conocidas')),
            ('medicamentos_uso_continuo', ce.get('medicamentos_uso_continuo')),
            ('enfermedades_cronicas', ce.get('enfermedades_cronicas')),
            ('factor_riesgo_cardiovascular', ce.get('factor_riesgo_cardiovascular')),
            ('vacuna_covid_fecha', ce.get('vacuna_covid_fecha')),
            ('vacuna_covid_dosis', ce.get('vacuna_covid_dosis')),
            ('vacuna_influenza_fecha', ce.get('vacuna_influenza_fecha')),
            ('vacuna_hepatitis_fecha', ce.get('vacuna_hepatitis_fecha')),
            ('vacuna_tetanos_fecha', ce.get('vacuna_tetanos_fecha')),
            ('vacuna_fiebre_amarilla_fecha', ce.get('vacuna_fiebre_amarilla_fecha')),
            ('vacuna_otras', ce.get('vacuna_otras')),
            ('examen_visual_fecha', ce.get('examen_visual_fecha')),
            ('examen_visual_resultado', ce.get('examen_visual_resultado')),
            ('examen_auditivo_fecha', ce.get('examen_auditivo_fecha')),
            ('examen_auditivo_resultado', ce.get('examen_auditivo_resultado')),
            ('espirometria_fecha', ce.get('espirometria_fecha')),
            ('espirometria_resultado', ce.get('espirometria_resultado')),

            # --- EPP y tallas ---
            ('epp_casco', ce.get('epp_casco')),
            ('epp_botas', ce.get('epp_botas')),
            ('epp_guantes', ce.get('epp_guantes')),
            ('epp_gafas', ce.get('epp_gafas')),
            ('epp_tapabocas', ce.get('epp_tapabocas')),
            ('epp_overol', ce.get('epp_overol')),
            ('epp_botas_dielectricas', ce.get('epp_botas_dielectricas')),
            ('epp_arnes', ce.get('epp_arnes')),
            ('epp_chaleco_reflectivo', ce.get('epp_chaleco_reflectivo')),
            ('epp_proteccion_auditiva', ce.get('epp_proteccion_auditiva')),
            ('talla_camisa', ce.get('talla_camisa')),
            ('talla_pantalon', ce.get('talla_pantalon')),
            ('talla_botas', ce.get('talla_botas')),
            ('talla_casco', ce.get('talla_casco')),
        ]

    @staticmethod
    def create(data: dict, usuario_id: int, foto_file=None) -> int:
        """
        Crea nuevo colaborador. Retorna ID creado.
        data: dict con todos los campos del formulario
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Validar documento único
                existing = Colaborador.get_by_num_doc(data['num_doc'])
                if existing:
                    raise ValueError(f"Ya existe un colaborador con documento {data['num_doc']}")

                # Procesar foto si hay
                foto_rel = None
                if foto_file:
                    foto_rel = Colaborador._procesar_foto(foto_file, data['num_doc'])

                # Mapear campos adicionales
                campos_extra = Colaborador._mapear_campos_adicionales(data)

                # Insert (columnas y valores desde una definición única)
                pares = Colaborador._pares_formulario(
                    data, campos_extra, foto_rel, usuario_id, es_actualizacion=False
                )
                columnas = [c for c, _ in pares]
                valores = [v for _, v in pares]
                sql = (
                    "INSERT INTO colaboradores (" + ", ".join(columnas) + ") "
                    "VALUES (" + ", ".join(["%s"] * len(columnas)) + ") RETURNING id"
                )
                cur.execute(sql, valores)
                nuevo_id = cur.fetchone()[0]
                conn.commit()
                return nuevo_id

        except Exception as e:
            conn.rollback()
            # Log detallado del error PostgreSQL
            import traceback
            import sys
            err_msg = f"[ERROR CREATE COLABORADOR] {type(e).__name__}: {e}"
            traceback_msg = f"[ERROR TRACEBACK] {traceback.format_exc()}"
            print(err_msg, file=sys.stderr, flush=True)
            print(traceback_msg, file=sys.stderr, flush=True)
            # Limpiar foto si se subió pero falló el insert
            if 'foto_rel' in locals() and foto_rel:
                Colaborador._eliminar_foto_anterior(foto_rel)
            raise
        finally:
            conn.close()

    @staticmethod
    def update(colaborador_id: int, data: dict, usuario_id: int, foto_file=None, eliminar_foto: bool = False) -> bool:
        """
        Actualiza colaborador. Retorna True si éxito.
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Obtener datos actuales (para foto anterior)
                cur.execute("SELECT num_doc, foto_perfil FROM colaboradores WHERE id = %s", (colaborador_id,))
                actual = cur.fetchone()
                if not actual:
                    raise ValueError("Colaborador no encontrado")
                num_doc_actual, foto_actual = actual

                # Validar documento único (si cambió)
                if data['num_doc'] != num_doc_actual:
                    existing = Colaborador.get_by_num_doc(data['num_doc'])
                    if existing:
                        raise ValueError(f"Ya existe un colaborador con documento {data['num_doc']}")

                # Manejo foto
                foto_rel = foto_actual
                if eliminar_foto:
                    Colaborador._eliminar_foto_anterior(foto_actual)
                    foto_rel = None
                elif foto_file:
                    # Eliminar anterior y procesar nueva
                    Colaborador._eliminar_foto_anterior(foto_actual)
                    foto_rel = Colaborador._procesar_foto(foto_file, data['num_doc'])

                    # Si cambió num_doc, mover carpeta
                    if data['num_doc'] != num_doc_actual:
                        Colaborador._mover_carpeta_colaborador(num_doc_actual, data['num_doc'])

                # Mapear campos adicionales
                campos_extra = Colaborador._mapear_campos_adicionales(data)

                # Update (mismas columnas que el INSERT)
                pares = Colaborador._pares_formulario(
                    data, campos_extra, foto_rel, usuario_id, es_actualizacion=True
                )
                columnas = [c for c, _ in pares]
                valores = [v for _, v in pares]
                sql = (
                    "UPDATE colaboradores SET "
                    + ", ".join(c + " = %s" for c in columnas)
                    + ", actualizado_en = CURRENT_TIMESTAMP WHERE id = %s"
                )
                cur.execute(sql, valores + [colaborador_id])
                conn.commit()
                return cur.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _mover_carpeta_colaborador(num_doc_viejo: str, num_doc_nuevo: str):
        """Renombra carpeta de uploads al cambiar num_doc"""
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', Colaborador.UPLOAD_ROOT)
        vieja = os.path.join(base, num_doc_viejo)
        nueva = os.path.join(base, num_doc_nuevo)
        if os.path.exists(vieja) and not os.path.exists(nueva):
            try:
                os.rename(vieja, nueva)
            except Exception:
                pass

    @staticmethod
    def soft_delete(colaborador_id: int, usuario_id: int) -> bool:
        """Soft delete: marca eliminado_en = NOW()"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE colaboradores SET eliminado_en = CURRENT_TIMESTAMP, actualizado_por = %s
                    WHERE id = %s AND eliminado_en IS NULL
                """, (usuario_id, colaborador_id))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def toggle_estado(colaborador_id: int) -> tuple[bool, str | None]:
        """Alterna estado Activo <-> Inactivo. Retorna (ok, nuevo_estado)"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE colaboradores 
                    SET estado = CASE WHEN estado = 'Activo' THEN 'Inactivo' ELSE 'Activo' END,
                        actualizado_en = CURRENT_TIMESTAMP
                    WHERE id = %s AND eliminado_en IS NULL
                    RETURNING estado
                """, (colaborador_id,))
                row = cur.fetchone()
                conn.commit()
                return (True, row[0]) if row else (False, None)
        finally:
            conn.close()

    # --- LISTAS PARA SELECTS (TomSelect) ---

    @staticmethod
    def buscar_para_jefe(termino: str, excluir_id: int | None = None, limite: int = 20) -> list:
        """Busca colaboradores para selector de jefe inmediato"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT id, nombre_completo, cargo, area, num_doc
                    FROM colaboradores
                    WHERE eliminado_en IS NULL
                      AND estado = 'Activo'
                      AND (nombre_completo ILIKE %s OR num_doc ILIKE %s)
                """
                params = [f"%{termino}%", f"%{termino}%"]
                if excluir_id:
                    sql += " AND id != %s"
                    params.append(excluir_id)
                sql += " ORDER BY nombre_completo LIMIT %s"
                params.append(limite)
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_areas_unicas() -> list:
        """Áreas únicas para filtro"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT area FROM colaboradores WHERE area IS NOT NULL AND eliminado_en IS NULL ORDER BY area")
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_cargos_unicos() -> list:
        """Cargos únicos para filtro"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT cargo FROM colaboradores WHERE cargo IS NOT NULL AND eliminado_en IS NULL ORDER BY cargo")
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()


# --- EXTENSIÓN PARSE_EMPTY PARA CAST INT ---
def parse_empty(value, cast_int=False):
    """Extiende base.parse_empty con opción cast_int"""
    if value is None or str(value).strip() == '':
        return None
    if cast_int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return value