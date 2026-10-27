# models/talento_humano/reportes.py
"""
Indicadores / reportes de Talento Humano.

Agrupan y cuentan la información ya existente en `colaboradores`
para construir los indicadores solicitados. Solo lectura.
"""
import psycopg2
import psycopg2.extras
from datetime import date
from models.base import get_db_connection

# Listas blancas: evitan SQL dinámico sobre columnas arbitrarias.
CAMPOS_CATALOGO = {
    'nacionalidad', 'pais_origen', 'departamento', 'ciudad', 'genero',
    'nivel_educativo', 'tipo_contrato', 'etnia', 'tipo_vivienda',
    'sisben', 'talla_camisa', 'talla_pantalon', 'talla_botas', 'talla_casco',
    'tipo_discapacidad', 'zona',
}
CAMPOS_BOOLEANO = {
    'discapacidad', 'victima_conflicto', 'comunidad_lgtbi', 'desplazado',
    'tiene_servicios_publicos', 'tiene_internet',
}
CAMPOS_NUMERICOS = {'estrato'}


class ReportesTH:
    """Cálculo de indicadores desde la tabla colaboradores."""

    TEMAS = {
        'nacionalidad_residencia': {
            'titulo': 'Nacionalidad / Residencia',
            'bloques': [
                {'titulo': 'Nacionalidad', 'tipo': 'catalogo', 'campo': 'nacionalidad'},
                {'titulo': 'País de origen', 'tipo': 'catalogo', 'campo': 'pais_origen'},
                {'titulo': 'Departamento de residencia', 'tipo': 'catalogo', 'campo': 'departamento'},
                {'titulo': 'Ciudad de residencia', 'tipo': 'catalogo', 'campo': 'ciudad'},
                {'titulo': 'Zona (Urbano/Rural)', 'tipo': 'catalogo', 'campo': 'zona'},
            ],
        },
        'sexo_edad': {
            'titulo': 'Sexo / Edad',
            'bloques': [
                {'titulo': 'Sexo', 'tipo': 'catalogo', 'campo': 'genero'},
                {'titulo': 'Edad', 'tipo': 'edad'},
            ],
        },
        'escolaridad': {
            'titulo': 'Escolaridad',
            'bloques': [
                {'titulo': 'Nivel educativo', 'tipo': 'catalogo', 'campo': 'nivel_educativo'},
            ],
        },
        'antiguedad_contrato': {
            'titulo': 'Antigüedad / Tipo de contrato',
            'bloques': [
                {'titulo': 'Tipo de contrato', 'tipo': 'catalogo', 'campo': 'tipo_contrato'},
                {'titulo': 'Antigüedad', 'tipo': 'antiguedad'},
            ],
        },
        'poblacion_especial': {
            'titulo': 'Población especial',
            'bloques': [
                {'titulo': 'Discapacidad', 'tipo': 'booleano', 'campo': 'discapacidad'},
                {'titulo': 'Víctima del conflicto', 'tipo': 'booleano', 'campo': 'victima_conflicto'},
                {'titulo': 'Comunidad LGTBI', 'tipo': 'booleano', 'campo': 'comunidad_lgtbi'},
                {'titulo': 'Desplazado', 'tipo': 'booleano', 'campo': 'desplazado'},
                {'titulo': 'Etnia', 'tipo': 'catalogo', 'campo': 'etnia'},
            ],
        },
        'vivienda_servicios': {
            'titulo': 'Vivienda / Servicios básicos',
            'bloques': [
                {'titulo': 'Tipo de vivienda', 'tipo': 'catalogo', 'campo': 'tipo_vivienda'},
                {'titulo': 'Servicios públicos', 'tipo': 'booleano', 'campo': 'tiene_servicios_publicos'},
                {'titulo': 'Internet', 'tipo': 'booleano', 'campo': 'tiene_internet'},
                {'titulo': 'Estrato', 'tipo': 'numerico', 'campo': 'estrato'},
                {'titulo': 'SISBEN', 'tipo': 'catalogo', 'campo': 'sisben'},
            ],
        },
        'tallaje': {
            'titulo': 'Tallaje',
            'bloques': [
                {'titulo': 'Talla camisa', 'tipo': 'catalogo', 'campo': 'talla_camisa'},
                {'titulo': 'Talla pantalón', 'tipo': 'catalogo', 'campo': 'talla_pantalon'},
                {'titulo': 'Talla botas', 'tipo': 'catalogo', 'campo': 'talla_botas'},
                {'titulo': 'Talla casco', 'tipo': 'catalogo', 'campo': 'talla_casco'},
            ],
        },
    }

    @staticmethod
    def total():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*)::int FROM colaboradores WHERE eliminado_en IS NULL")
                return cur.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def obtener(tema):
        cfg = ReportesTH.TEMAS.get(tema)
        if not cfg:
            return None
        bloques = []
        for b in cfg['bloques']:
            tipo = b['tipo']
            if tipo == 'catalogo':
                datos = ReportesTH._catalogo(b['campo'])
            elif tipo == 'booleano':
                datos = ReportesTH._booleano(b['campo'])
            elif tipo == 'numerico':
                datos = ReportesTH._numerico(b['campo'])
            elif tipo == 'edad':
                datos = ReportesTH._edad()
            elif tipo == 'antiguedad':
                datos = ReportesTH._antiguedad()
            else:
                datos = []
            bloques.append({
                'titulo': b['titulo'],
                'tipo': tipo,
                'grafico': ReportesTH._grafico_sugerido(tipo, len(datos)),
                'datos': datos,
            })
        return {'titulo': cfg['titulo'], 'total': ReportesTH.total(), 'bloques': bloques}

    @staticmethod
    def _grafico_sugerido(tipo, n):
        if tipo == 'booleano':
            return 'donut'
        if tipo in ('edad', 'antiguedad'):
            return 'bar'
        if tipo in ('catalogo', 'numerico'):
            return 'donut' if n <= 5 else 'barh'
        return 'bar'

    @staticmethod
    def _catalogo(campo):
        assert campo in CAMPOS_CATALOGO
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT COALESCE(NULLIF(TRIM(CAST({campo} AS text)), ''), 'Sin dato') AS etiqueta,
                           COUNT(*)::int AS valor
                    FROM colaboradores
                    WHERE eliminado_en IS NULL
                    GROUP BY 1
                    ORDER BY 2 DESC, 1
                """)
                return [{'etiqueta': r[0], 'valor': r[1]} for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _numerico(campo):
        assert campo in CAMPOS_NUMERICOS
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT CASE WHEN {campo} IS NULL THEN 'Sin dato' ELSE CAST({campo} AS text) END AS etiqueta,
                           COUNT(*)::int AS valor
                    FROM colaboradores
                    WHERE eliminado_en IS NULL
                    GROUP BY 1
                    ORDER BY MIN({campo}) ASC NULLS LAST
                """)
                return [{'etiqueta': r[0], 'valor': r[1]} for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _booleano(campo):
        assert campo in CAMPOS_BOOLEANO
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT CASE
                               WHEN {campo} IS TRUE THEN 'Sí'
                               WHEN {campo} IS FALSE THEN 'No'
                               ELSE 'Sin dato'
                           END AS etiqueta,
                           COUNT(*)::int AS valor
                    FROM colaboradores
                    WHERE eliminado_en IS NULL
                    GROUP BY 1
                """)
                datos = {r[0]: r[1] for r in cur.fetchall()}
                return [{'etiqueta': k, 'valor': datos[k]} for k in ('Sí', 'No', 'Sin dato') if k in datos]
        finally:
            conn.close()

    @staticmethod
    def _edad():
        return ReportesTH._distribucion_anios(
            'fecha_nacimiento',
            [('Menor de 18', lambda e: e < 18),
             ('18 - 25', lambda e: 18 <= e <= 25),
             ('26 - 35', lambda e: 26 <= e <= 35),
             ('36 - 45', lambda e: 36 <= e <= 45),
             ('46 - 55', lambda e: 46 <= e <= 55),
             ('Mayor de 55', lambda e: e > 55)],
        )

    @staticmethod
    def _antiguedad():
        return ReportesTH._distribucion_anios(
            'fecha_ingreso',
            [('Menos de 1 año', lambda e: e < 1),
             ('1 - 3 años', lambda e: 1 <= e < 3),
             ('3 - 5 años', lambda e: 3 <= e < 5),
             ('5 - 10 años', lambda e: 5 <= e < 10),
             ('Más de 10 años', lambda e: e >= 10)],
        )

    @staticmethod
    def _distribucion_anios(campo, rangos):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {campo} FROM colaboradores WHERE eliminado_en IS NULL")
                filas = cur.fetchall()
        finally:
            conn.close()

        hoy = date.today()
        conteo = {nombre: 0 for nombre, _ in rangos}
        conteo['Sin dato'] = 0
        for (fecha,) in filas:
            if not fecha:
                conteo['Sin dato'] += 1
                continue
            anios = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
            ubicado = False
            for nombre, cond in rangos:
                if cond(anios):
                    conteo[nombre] += 1
                    ubicado = True
                    break
            if not ubicado:
                conteo['Sin dato'] += 1

        return [{'etiqueta': k, 'valor': v} for k, v in conteo.items() if v > 0]
