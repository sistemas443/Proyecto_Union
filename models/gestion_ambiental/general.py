"""
Catalogo de indicadores del modulo General de Gestion Ambiental.

General consolida empresa (Lourdes + Vargas) desde las vistas `general_*` que
ya calcula el ETL sobre `master_ga`. Es la fuente definitiva: la base
`ga_general` es legado y no se consulta.

Cada indicador declara las vistas por sede, de modo que el motor puede mostrar
una sede concreta o el consolidado "Todas". El consolidado etiqueta cada punto
con la sede de origen y el grafico compara ambas plantas.

Las metas se dejan aqui, en un solo lugar, para ajustarlas sin tocar consultas
ni plantillas.
"""

from models.gestion_ambiental.indicadores import (
    indicadores_de_sede,
    normalizar_tipo,
)

# Sedes del selector de General.
SEDES_GENERAL = {
    'todas': {'nombre': 'Todas', 'descripcion': 'Consolidado Lourdes + Vargas'},
    'lourdes': {'nombre': 'Lourdes', 'descripcion': 'Planta Lourdes'},
    'vargas': {'nombre': 'Vargas', 'descripcion': 'Planta Vargas'},
}

SEDE_GENERAL_POR_DEFECTO = 'todas'

# Los dos modulos de General: cada uno es una linea de produccion con su
# planta y sus propios temas.
LINEAS_GENERAL = {
    'produccion': {
        'nombre': 'Producción',
        'descripcion': 'Planta Vargas · indicadores de la línea de producción',
        'sede': 'vargas',
        'icono': 'bx-buildings',
        'temas': {
            'agua': {
                'nombre': 'Parámetros del agua',
                'descripcion': 'Cloro, pH, hierro, laboratorio y consumo de agua por ave.',
                'icono': 'bx-water',
                'activo': True,
            },
            'combustibles': {
                'nombre': 'Combustibles',
                'descripcion': 'Consumo mensual de gasolina y ACPM de la operación.',
                'icono': 'bx-gas-pump',
                'activo': True,
            },
            'residuos': {
                'nombre': 'Residuos',
                'descripcion': 'Orgánicos, ordinarios, peligrosos, reciclables y aprovechamiento.',
                'icono': 'bx-recycle',
                'activo': True,
            },
            'mortalidad': {
                'nombre': 'Mortalidad producción',
                'descripcion': 'Aves muertas y porcentaje de mortalidad del ciclo.',
                'icono': 'bx-pulse',
                'activo': True,
            },
            'gallinaza': {
                'nombre': 'Gallinaza ave',
                'descripcion': 'Abono producido por ave y ventas de abono.',
                'icono': 'bx-leaf',
                'activo': True,
            },
            'energia': {
                'nombre': 'Consumo de energía por unidad de producción',
                'descripcion': 'Consumo eléctrico por huevo producido.',
                'icono': 'bx-bolt-circle',
                'activo': True,
            },
        },
    },
    'levante': {
        'nombre': 'Levante',
        'descripcion': 'Planta Lourdes · indicadores de la línea de levante',
        'sede': 'lourdes',
        'icono': 'bx-home-alt',
        'temas': {
            'agua': {
                'nombre': 'Parámetros del agua Lourdes',
                'descripcion': 'Cloro, pH y análisis de laboratorio del agua de levante.',
                'icono': 'bx-water',
                'activo': True,
            },
            'combustibles': {
                'nombre': 'Combustibles (GLP)',
                'descripcion': 'Consumo de GLP de la operación.',
                'icono': 'bx-gas-pump',
                'activo': True,
            },
            'residuos': {
                'nombre': 'Residuos',
                'descripcion': 'Orgánicos, ordinarios, peligrosos, reciclables y aprovechamiento.',
                'icono': 'bx-recycle',
                'activo': True,
            },
            'mortalidad': {
                'nombre': 'Mortalidad',
                'descripcion': 'Aves muertas y porcentaje de mortalidad del ciclo.',
                'icono': 'bx-pulse',
                'activo': True,
            },
        },
    },
}

LINEA_GENERAL_POR_DEFECTO = 'produccion'

TEMA_GENERAL_POR_DEFECTO = 'agua'

# Secciones de la barra lateral del tablero.
SECCIONES_GENERAL = {
    'diario': {'nombre': 'Mediciones diarias', 'icono': 'bx-water'},
    'laboratorio': {'nombre': 'Laboratorio', 'icono': 'bx-test-tube'},
    'residual': {'nombre': 'Aguas residuales', 'icono': 'bx-test-tube'},
    'consumo': {'nombre': 'Consumo de agua', 'icono': 'bx-droplet'},
    'gasolina': {'nombre': 'Gasolina', 'icono': 'bx-gas-pump'},
    'acpm': {'nombre': 'ACPM', 'icono': 'bx-gas-pump'},
    'glp': {'nombre': 'GLP', 'icono': 'bx-gas-pump'},
    'organicos': {'nombre': 'Residuos orgánicos', 'icono': 'bx-leaf'},
    'ordinarios': {'nombre': 'Residuos ordinarios', 'icono': 'bx-trash'},
    'especiales': {'nombre': 'Residuos especiales', 'icono': 'bx-error-circle'},
    'reciclables': {'nombre': 'Residuos reciclables', 'icono': 'bx-recycle'},
    'total_residuos': {'nombre': 'Total de residuos', 'icono': 'bx-layer'},
    'aprovechamiento': {'nombre': 'Aprovechamiento', 'icono': 'bx-pie-chart-alt'},
    'mortalidad': {'nombre': 'Mortalidad', 'icono': 'bx-pulse'},
    'gallinaza': {'nombre': 'Gallinaza', 'icono': 'bx-leaf'},
    'energia': {'nombre': 'Energía', 'icono': 'bx-bolt-circle'},
}

# Submódulos por tema. Cada entrada sin `hijos` abre un tablero; con `hijos`
# abre una página de módulos.
SUBMODULOS_POR_TEMA = {
    ('produccion', 'agua'): [
        {
            'clave': 'laboratorio',
            'nombre': 'Análisis de laboratorio',
            'descripcion': 'Parámetros fisicoquímicos y microbiológicos del agua.',
            'icono': 'bx-test-tube',
            'grupo': 'laboratorio',
        },
        {
            'clave': 'in-situ',
            'nombre': 'Mediciones in situ',
            'descripcion': 'pH, cloro y hierro medidos en planta y galpones.',
            'icono': 'bx-water',
            'hijos': [
                {
                    'clave': 'ph',
                    'nombre': 'pH Vargas',
                    'descripcion': 'pH en PTAP y galpones intermedio y final.',
                    'icono': 'bx-test-tube',
                    'indicadores': ['prom_ph_diario'],
                },
                {
                    'clave': 'cloro',
                    'nombre': 'Cloro Vargas',
                    'descripcion': 'Cloro en PTAP, galpón intermedio y galpón final.',
                    'icono': 'bx-water',
                    'indicadores': ['prom_cloro_diario'],
                },
                {
                    'clave': 'hierro',
                    'nombre': 'Hierro Vargas',
                    'descripcion': 'Hierro medido en la planta de tratamiento.',
                    'icono': 'bx-droplet',
                    'indicadores': ['hierro_ptap'],
                },
            ],
        },
        {
            'clave': 'residuales',
            'nombre': 'Análisis de aguas residuales Vargas',
            'descripcion': 'DQO, DBO, grasas, caudal, metales y otros.',
            'icono': 'bx-test-tube',
            'grupo': 'residual',
        },
        {
            'clave': 'consumo',
            'nombre': 'Consumo agua',
            'descripcion': 'Consumo promedio de agua por ave.',
            'icono': 'bx-droplet',
            'hijos': [
                {
                    'clave': 'ave',
                    'nombre': 'Consumo prom. de agua ave/día producción',
                    'descripcion': 'Consumo promedio diario de agua por ave.',
                    'icono': 'bx-droplet',
                    'indicadores': ['g_consumo_agua_ave_prod'],
                },
                {
                    'clave': 'domestica',
                    'nombre': 'Consumo prom. de agua doméstica ave/día producción',
                    'descripcion': 'Consumo promedio de agua doméstica de la planta.',
                    'icono': 'bx-water',
                    'indicadores': ['g_consumo_agua_domestica_prod'],
                },
            ],
        },
    ],
    ('produccion', 'combustibles'): [
        {
            'clave': 'gasolina',
            'nombre': 'Combustible gasolina producción',
            'descripcion': 'Consumo mensual de gasolina en galones.',
            'icono': 'bx-gas-pump',
            'grupo': 'gasolina',
        },
        {
            'clave': 'acpm',
            'nombre': 'Combustible ACPM producción',
            'descripcion': 'Consumo mensual de ACPM en galones.',
            'icono': 'bx-gas-pump',
            'grupo': 'acpm',
        },
    ],
    ('produccion', 'residuos'): [
        {
            'clave': 'organicos',
            'nombre': 'Residuos orgánicos totales producción',
            'descripcion': 'Restos de comedor y clasificadora.',
            'icono': 'bx-leaf',
            'grupo': 'organicos',
        },
        {
            'clave': 'ordinarios',
            'nombre': 'Residuos ordinarios totales producción',
            'descripcion': 'Residuos no aprovechables de la operación.',
            'icono': 'bx-trash',
            'grupo': 'ordinarios',
        },
        {
            'clave': 'especiales',
            'nombre': 'Cantidad de residuos especiales y/o peligrosos producción',
            'descripcion': 'Residuos con manejo especial.',
            'icono': 'bx-error-circle',
            'grupo': 'especiales',
        },
        {
            'clave': 'reciclables',
            'nombre': 'Residuos reciclables producción',
            'descripcion': 'Material aprovechable recuperado.',
            'icono': 'bx-recycle',
            'grupo': 'reciclables',
        },
        {
            'clave': 'total',
            'nombre': 'Total de residuos producción',
            'descripcion': 'Suma de todos los residuos generados.',
            'icono': 'bx-layer',
            'grupo': 'total_residuos',
        },
        {
            'clave': 'aprovechamiento',
            'nombre': 'Porcentaje de aprovechamiento de residuos Vargas',
            'descripcion': 'Porcentaje de residuos aprovechados.',
            'icono': 'bx-pie-chart-alt',
            'grupo': 'aprovechamiento',
        },
    ],
    ('levante', 'residuos'): [
        {
            'clave': 'organicos',
            'nombre': 'Residuos orgánicos totales',
            'descripcion': 'Restos de comedor y clasificadora.',
            'icono': 'bx-leaf',
            'grupo': 'organicos',
        },
        {
            'clave': 'ordinarios',
            'nombre': 'Residuos ordinarios totales',
            'descripcion': 'Residuos no aprovechables de la operación.',
            'icono': 'bx-trash',
            'grupo': 'ordinarios',
        },
        {
            'clave': 'especiales',
            'nombre': 'Cantidad de residuos especiales y/o peligrosos',
            'descripcion': 'Residuos con manejo especial.',
            'icono': 'bx-error-circle',
            'grupo': 'especiales',
        },
        {
            'clave': 'reciclables',
            'nombre': 'Residuos reciclables',
            'descripcion': 'Material aprovechable recuperado.',
            'icono': 'bx-recycle',
            'grupo': 'reciclables',
        },
        {
            'clave': 'total',
            'nombre': 'Total de residuos',
            'descripcion': 'Suma de todos los residuos generados.',
            'icono': 'bx-layer',
            'grupo': 'total_residuos',
        },
        {
            'clave': 'aprovechamiento',
            'nombre': 'Porcentaje de aprovechamiento de residuos',
            'descripcion': 'Porcentaje de residuos aprovechados.',
            'icono': 'bx-pie-chart-alt',
            'grupo': 'aprovechamiento',
        },
    ],
    ('levante', 'agua'): [
        {
            'clave': 'laboratorio',
            'nombre': 'Análisis de laboratorio',
            'descripcion': 'Parámetros fisicoquímicos y microbiológicos del agua.',
            'icono': 'bx-test-tube',
            'grupo': 'laboratorio',
        },
        {
            'clave': 'in-situ',
            'nombre': 'Mediciones in situ',
            'descripcion': 'pH y cloro medidos en planta y galpones.',
            'icono': 'bx-water',
            'hijos': [
                {
                    'clave': 'ph',
                    'nombre': 'pH Lourdes',
                    'descripcion': 'pH medido en PTAP y galpones.',
                    'icono': 'bx-test-tube',
                    'indicadores': ['prom_ph_diario'],
                },
                {
                    'clave': 'cloro',
                    'nombre': 'Cloro Lourdes',
                    'descripcion': 'Cloro medido en planta y galpones.',
                    'icono': 'bx-water',
                    'indicadores': ['prom_cloro_diario'],
                },
            ],
        },
        {
            'clave': 'residuales',
            'nombre': 'Análisis de aguas residuales Lourdes',
            'descripcion': 'DQO, DBO, grasas, caudal, metales y otros.',
            'icono': 'bx-test-tube',
            'grupo': 'residual',
        },
        {
            'clave': 'consumo',
            'nombre': 'Consumo agua',
            'descripcion': 'Consumo promedio de agua por ave.',
            'icono': 'bx-droplet',
            'hijos': [
                {
                    'clave': 'ave',
                    'nombre': 'Consumo prom. de agua ave/día levante',
                    'descripcion': 'Consumo promedio diario de agua por ave.',
                    'icono': 'bx-droplet',
                    'indicadores': ['g_consumo_agua_ave'],
                },
                {
                    'clave': 'domestica',
                    'nombre': 'Consumo prom. de agua doméstica ave/día levante',
                    'descripcion': 'Consumo de agua doméstica de la planta.',
                    'icono': 'bx-water',
                    'indicadores': ['g_consumo_agua_domestica_lev'],
                },
            ],
        },
    ],
}


def submodulos_de(linea, tema):
    """Submódulos del tema para la línea indicada (vacío si no tiene)."""
    return SUBMODULOS_POR_TEMA.get((linea, tema), [])


def _gind(id_, nombre, corto, grupo, unidad, decimales, fisico, criterio,
          limite_min=None, limite_max=None, vistas=None, fuente_unica=None,
          col_fecha='fecha', col_valor='valor_real', col_tipo=None,
          tipo_grafico='line', granularidad='mes', etiqueta_y='Valor real',
          etiqueta_limite_min=None, etiqueta_limite_max=None, nota='',
          sedes=None, tema='agua', **extra):
    """
    Construye un indicador de General con los valores por defecto.

    `vistas` declara la vista calculada de cada sede, por ejemplo
    {'lourdes': ('general_turbiedad_lev', 'valor_real', 'fecha')}.

    `fuente_unica` se usa cuando la tabla no distingue sede (por ejemplo el
    consumo de agua por ave): se lee una sola vez y no se duplica al
    consolidar. Los parámetros adicionales (`modo`, `extra`, `filtro_sql`...)
    se copian tal cual al diccionario del indicador.
    """
    vistas_finales = dict(vistas or {})
    if sedes is None:
        sedes = tuple(vistas_finales.keys())

    datos = {
        'id': id_,
        'nombre': nombre,
        'corto': corto,
        'tema': tema,
        'grupo': grupo,
        'tabla': None,
        'col_fecha': col_fecha,
        'col_valor': col_valor,
        'expresion': None,
        'mapa_sedes': {},
        'vistas': vistas_finales,
        'fuente_unica': fuente_unica,
        'col_tipo': col_tipo,
        'unidad': unidad,
        'decimales': decimales,
        'fisico': fisico,
        'criterio': criterio,
        'limite_min': limite_min,
        'limite_max': limite_max,
        'etiqueta_limite_min': etiqueta_limite_min,
        'etiqueta_limite_max': etiqueta_limite_max,
        'nota': nota,
        'etiqueta_y': etiqueta_y,
        'tipo_grafico': tipo_grafico,
        'granularidad': granularidad,
        'mostrar_valores': grupo != 'diario',
        'sedes': tuple(sedes),
        'opcionales': {},
        'columnas_tabla': {},
    }
    datos.update(extra)
    return datos


# Vistas de laboratorio del aplicativo de Vargas. Producción las consume
# directamente para que General muestre los mismos números que /ga/vargas.
VISTAS_LAB_VARGAS = {
    'color_aparente': 'color_aparente_prod',
    'turbiedad': 'turbiedad_prod',
    'conductividad': 'conductividad_prod',
    'cloro_residual': 'cloro_residual_libre_prod',
    'arsenico': 'arsenico_prod',
    'mercurio': 'mercurio_prod',
    'selenio': 'selenio_prod',
    'nitritos': 'nitritos_prod',
    'nitratos': 'nitratos_prod',
    'alcalinidad_total': 'alcalinidad_prod',
    'cloruros': 'cloruros_prod',
    'aluminio': 'aluminio_prod',
    'dureza_total': 'dureza_total_prod',
    'hierro_total': 'hierro_total_prod',
    'magnesio': 'magnesio_prod',
    'sulfatos': 'sulfatos_prod',
    'fosfatos': 'fosfatos_prod',
    'coliformes_totales': 'coliformes_totales_prod',
    'escherichia_coli': 'escherichia_coli_prod',
    'heterotrofos': 'heterotrofos_prod',
    'pseudomona': 'pseudomona_prod',
    'calcio': 'calcio_prod',
    'cot': 'carbono_organico_prod',
    'cryptosporidium': 'cryptosporidium_prod',
    'fluoruros': 'fluoruros_prod',
    'fosforo': 'fosforo_prod',
    'manganeso': 'manganeso_prod',
    'mesofilos': 'mesofilos_prod',
}


# Vistas de laboratorio del aplicativo de Lourdes. Levante las consume
# directamente para que General muestre los mismos números que /ga/lourdes.
VISTAS_LAB_LOURDES = {
    'color_aparente': 'color_aparente_lev',
    'turbiedad': 'turbiedad_lev',
    'conductividad': 'conductividad_lev',
    'cloro_residual': 'cloro_residual_libre_lev',
    'arsenico': 'arsenico_lev',
    'mercurio': 'mercurio_lev',
    'selenio': 'selenio_lev',
    'nitritos': 'nitritos_lev',
    'nitratos': 'nitratos_lev',
    'alcalinidad_total': 'alcalinidad_lev',
    'cloruros': 'cloruros_lev',
    'aluminio': 'aluminio_lev',
    'dureza_total': 'dureza_total_lev',
    'hierro_total': 'hierro_total_lev',
    'magnesio': 'magnesio_lev',
    'sulfatos': 'sulfatos_lev',
    'fosfatos': 'fosfatos_lev',
    'coliformes_totales': 'coliformes_totales_lev',
    'escherichia_coli': 'escherichia_coli_lev',
    'heterotrofos': 'heterotrofos_lev',
    'pseudomona': 'pseudomona_lev',
}


def _lab(id_, nombre, corto, base, unidad, decimales, fisico, criterio,
         limite_max=None, limite_min=None, sedes=('lourdes', 'vargas'),
         col_tipo='tipo_agua', nota='', etiqueta_y='Valor real'):
    """
    Indicador de laboratorio: Lourdes desde su aplicativo (`<base>_lev`) y
    Vargas desde la misma vista que usa el tablero de Vargas (`<base>_prod`).

    Cuando la sede no mide el parametro se omite su vista y el indicador deja
    de aparecer al filtrar por esa sede.
    """
    vistas = {}
    if 'lourdes' in sedes:
        vista_lourdes = VISTAS_LAB_LOURDES.get(base, 'general_%s_lev' % base)
        vistas['lourdes'] = (vista_lourdes, 'valor_real', 'fecha')
    if 'vargas' in sedes:
        vista_vargas = VISTAS_LAB_VARGAS.get(base, '%s_prod' % base)
        vistas['vargas'] = (vista_vargas, 'valor_real', 'fecha')
    return _gind(
        id_, nombre, corto, 'laboratorio', unidad, decimales, fisico, criterio,
        limite_min=limite_min, limite_max=limite_max, vistas=vistas,
        col_tipo=col_tipo, nota=nota, etiqueta_y=etiqueta_y,
    )


def _residual(id_, nombre, corto, base, unidad, decimales,
              col_tipo='tipo_agua'):
    """Indicador de aguas residuales: vista `general_<base>_prod`."""
    return _gind(
        id_, nombre, corto, 'residual', unidad, decimales, (0, 1000000),
        'informativo',
        vistas={'vargas': ('general_%s_prod' % base, 'valor_real', 'fecha')},
        col_tipo=col_tipo,
        nota='Monitoreo de aguas residuales. La referencia depende de la '
             'norma aplicable.',
    )


def _residual_lev(id_, nombre, corto, base, unidad, decimales,
                  col_tipo='tipo_agua'):
    """Indicador de aguas residuales de Levante: vista `<base>_residual_lev`."""
    return _gind(
        id_, nombre, corto, 'residual', unidad, decimales, (0, 1000000),
        'informativo',
        vistas={'lourdes': ('general_%s_residual_lev' % base, 'valor_real', 'fecha')},
        col_tipo=col_tipo, sedes=('lourdes',),
        nota='Monitoreo de aguas residuales de levante.',
    )


INDICADORES_GENERAL = [
    # ------------------------------------------------------------------
    # Mediciones diarias (cloro, pH y hierro PTAP)
    # ------------------------------------------------------------------
    _gind(
        'g_cloro_diario', 'Promedio cloro mg/L diario', 'Cloro',
        'diario', 'mg/L', 3, (0, 5), 'rango', 1.0, 2.5,
        vistas={
            'lourdes': ('indicador_cloro_lev', 'prom_ponderado_cloro', 'fecha_registro'),
            'vargas': ('indicador_cloro_prod', 'promedio_ponderado_cloro', 'fecha'),
        },
        tipo_grafico='bar', granularidad='dia',
        etiqueta_y='Promedio ponderado cloro',
        etiqueta_limite_min='MIN (1)', etiqueta_limite_max='MAX (2,5)',
        nota='Rango de control de la planta: mínimo 1,0 y máximo 2,5 mg/L.',
    ),
    _gind(
        'g_ph_diario', 'Promedio pH diario', 'pH',
        'diario', 'pH', 2, (0, 14), 'rango', 5.0, 5.5,
        vistas={
            'lourdes': ('indicador_ph_lev', 'promedio_ponderado_ph', 'fecha_registro'),
            'vargas': ('indicador_ph_prod', 'promedio_ponderado_ph', 'fecha'),
        },
        granularidad='dia', etiqueta_y='Promedio ponderado pH',
        etiqueta_limite_min='MIN (5)', etiqueta_limite_max='MAX (5,5)',
        nota='Rango de control de la planta: mínimo 5,0 y máximo 5,5.',
    ),
    _gind(
        'g_hierro_ptap', 'Hierro PTAP', 'Hierro PTAP',
        'diario', 'mg/L', 2, (0, 100), 'maximo', None, 0.3,
        vistas={'vargas': ('indicador_hierro_prod', 'hierro_ptap', 'fecha')},
        granularidad='dia', etiqueta_y='Hierro PTAP',
        nota='Hierro medido en la planta de tratamiento (solo Vargas).',
    ),

    # ------------------------------------------------------------------
    # Laboratorio (vistas general_*_lev y general_*_prod)
    # ------------------------------------------------------------------
    _lab('g_color_aparente', 'Color aparente', 'Color', 'color_aparente',
         'UPC', 0, (0, 1000), 'maximo', 15,
         nota='Res. 2115: máximo 15 UPC.'),
    _lab('g_turbiedad', 'Turbiedad', 'Turbiedad', 'turbiedad',
         'UNT', 2, (0, 100), 'maximo', 2,
         nota='Res. 2115: máximo 2 UNT.'),
    _lab('g_conductividad', 'Conductividad', 'Conductividad', 'conductividad',
         'uS/cm', 1, (0, 2000), 'maximo', 1000,
         nota='Res. 2115: máximo 1000 uS/cm.'),
    _lab('g_cloro_residual', 'Cloro residual', 'Cloro residual', 'cloro_residual',
         'mg/L', 2, (0, 5), 'rango', limite_min=0.3, limite_max=2.0,
         nota='Res. 2115: 0,3 a 2,0 mg/L.'),
    _lab('g_arsenico', 'Arsénico (As)', 'Arsénico', 'arsenico',
         'mg/L', 4, (0, 1), 'maximo', 0.01,
         nota='Res. 2115: máximo 0,01 mg/L.'),
    _lab('g_mercurio', 'Mercurio (Hg)', 'Mercurio', 'mercurio',
         'mg/L', 4, (0, 1), 'maximo', 0.001,
         nota='Res. 2115: máximo 0,001 mg/L.'),
    _lab('g_selenio', 'Selenio (Se)', 'Selenio', 'selenio',
         'mg/L', 4, (0, 1), 'maximo', 0.01,
         nota='Res. 2115: máximo 0,01 mg/L.'),
    _lab('g_nitritos', 'Nitritos (NO2-)', 'Nitritos', 'nitritos',
         'mg/L', 3, (0, 10), 'maximo', 0.1,
         nota='Res. 2115: máximo 0,1 mg/L.'),
    _lab('g_nitratos', 'Nitratos (NO3-)', 'Nitratos', 'nitratos',
         'mg/L', 2, (0, 100), 'maximo', 10,
         nota='Res. 2115: máximo 10 mg/L.'),
    _lab('g_alcalinidad', 'Alcalinidad total (CaCO3)', 'Alcalinidad',
         'alcalinidad_total', 'mg/L', 1, (0, 1000), 'maximo', 200,
         nota='Res. 2115: máximo 200 mg/L.'),
    _lab('g_cloruros', 'Cloruros (Cl-)', 'Cloruros', 'cloruros',
         'mg/L', 2, (0, 1000), 'maximo', 250,
         nota='Res. 2115: máximo 250 mg/L.'),
    _lab('g_aluminio', 'Aluminio (Al3+)', 'Aluminio', 'aluminio',
         'mg/L', 3, (0, 5), 'maximo', 0.2,
         nota='Res. 2115: máximo 0,2 mg/L.'),
    _lab('g_dureza', 'Dureza total (CaCO3)', 'Dureza', 'dureza_total',
         'mg/L', 1, (0, 2000), 'maximo', 300,
         nota='Res. 2115: máximo 300 mg/L.'),
    _lab('g_hierro', 'Hierro (Fe)', 'Hierro', 'hierro_total',
         'mg/L', 3, (0, 10), 'maximo', 0.3,
         nota='Res. 2115: máximo 0,3 mg/L.'),
    _lab('g_magnesio', 'Magnesio (Mg)', 'Magnesio', 'magnesio',
         'mg/L', 3, (0, 200), 'maximo', 36,
         nota='Res. 2115: máximo 36 mg/L.'),
    _lab('g_sulfatos', 'Sulfatos (SO42-)', 'Sulfatos', 'sulfatos',
         'mg/L', 2, (0, 1000), 'maximo', 250,
         nota='Res. 2115: máximo 250 mg/L.'),
    _lab('g_fosfatos', 'Fosfatos (PO43-)', 'Fosfatos', 'fosfatos',
         'mg/L', 2, (0, 50), 'maximo', 0.5,
         nota='Res. 2115: máximo 0,5 mg/L.'),
    _lab('g_coliformes_totales', 'Coliformes totales', 'Coliformes',
         'coliformes_totales', 'UFC/100 mL', 0, (0, 1000000), 'cero', 0,
         nota='Res. 2115: 0 UFC/100 mL.'),
    _lab('g_escherichia_coli', 'Escherichia coli', 'E. coli',
         'escherichia_coli', 'UFC/100 mL', 0, (0, 1000000), 'cero', 0,
         nota='Res. 2115: 0 UFC/100 mL.'),
    _lab('g_heterotrofos', 'Heterótrofos', 'Heterótrofos', 'heterotrofos',
         'UFC/mL', 0, (0, 1000000), 'maximo', 100,
         nota='Lourdes: máximo 100 UFC/mL. Vargas: máximo 500 UFC/mL.'),
    _lab('g_pseudomona', 'Pseudomona', 'Pseudomona', 'pseudomona',
         'UFC/100 mL', 0, (0, 1000000), 'cero', 0,
         nota='Res. 2115: ausencia.'),

    # Parámetros que solo mide Vargas.
    _lab('g_calcio', 'Calcio (Ca)', 'Calcio', 'calcio',
         'mg/L', 2, (0, 1000), 'maximo', 60, sedes=('vargas',),
         nota='Res. 2115: máximo 60 mg/L.'),
    _lab('g_fluoruros', 'Fluoruros (F-)', 'Fluoruros', 'fluoruros',
         'mg/L', 2, (0, 50), 'maximo', 1.0, sedes=('vargas',),
         nota='Res. 2115: máximo 1,0 mg/L.'),
    _lab('g_fosforo', 'Fósforo (P)', 'Fósforo', 'fosforo',
         'mg/L', 2, (0, 100), 'maximo', 0.1, sedes=('vargas',),
         nota='Referencia de la vista: máximo 0,1 mg/L.'),
    _lab('g_manganeso', 'Manganeso (Mn)', 'Manganeso', 'manganeso',
         'mg/L', 3, (0, 50), 'maximo', 0.1, sedes=('vargas',),
         nota='Res. 2115: máximo 0,1 mg/L.'),
    _lab('g_mesofilos', 'Mesófilos', 'Mesófilos', 'mesofilos',
         'UFC/mL', 0, (0, 10000000), 'maximo', 100, sedes=('vargas',),
         nota='Referencia de la vista: máximo 100 UFC/mL.'),
    _lab('g_carbono_organico_total', 'Carbono orgánico total', 'COT', 'cot',
         'mg/L', 2, (0, 200), 'informativo', sedes=('vargas',),
         nota='Parámetro informativo, sin límite definido.'),
    _gind('g_cryptosporidium', 'Cryptosporidium', 'Cryptosporidium',
          'laboratorio', 'ooq/L', 0, (0, 1000000), 'cero', None, 0,
          vistas={'vargas': ('general_cryptosporidium_prod', 'valor_real', 'fecha')},
          nota='Ausencia esperada.'),

    # ------------------------------------------------------------------
    # Aguas residuales (solo Vargas)
    # ------------------------------------------------------------------
    _residual('g_dqo', 'DQO', 'DQO', 'dqo', 'mg/L', 2),
    _residual('g_dbo', 'DBO', 'DBO', 'dbo', 'mg/L', 2),
    _residual('g_grasas_aceites', 'Grasas y aceites', 'Grasas y aceites',
              'grasas_aceites_residual', 'mg/L', 2),
    _residual('g_caudal_residual', 'Caudal', 'Caudal', 'caudal_residual',
              'm³/s', 3),
    _residual('g_ph_residual', 'pH residual', 'pH residual', 'ph_residual',
              'pH', 2),
    _residual('g_temperatura_residual', 'Temperatura', 'Temperatura',
              'temperatura_residual', '°C', 2),
    _residual('g_fluoruros_residual', 'Fluoruros', 'Fluoruros',
              'fluoruros_residual', 'mg/L', 2),
    _residual('g_hidrocarburos_residual', 'Hidrocarburos', 'Hidrocarburos',
              'hidrocarburos_residual', 'mg/L', 2, col_tipo=None),
    _residual('g_hierro_residual', 'Hierro residual', 'Hierro residual',
              'hierro_total_residual', 'mg/L', 2),
    _residual('g_plomo_residual', 'Plomo', 'Plomo', 'plomo_total_residual',
              'mg/L', 3),
    _residual('g_solidos_suspendidos_residual', 'Sólidos suspendidos',
              'Sólidos suspendidos', 'solidos_suspendidos_residual', 'mg/L', 2),
    _residual('g_sulfuros_residual', 'Sulfuros', 'Sulfuros', 'sulfuros_residual',
              'mg/L', 2),

    # ------------------------------------------------------------------
    # Combustibles (solo Producción / Vargas)
    # ------------------------------------------------------------------
    _gind(
        'g_combustible_gasolina', 'Combustible gasolina producción', 'Gasolina',
        'gasolina', 'gal', 2, (0, 1000000), 'informativo',
        vistas={'vargas': ('general_combustible_gasolina_prod', 'cantidad', 'fecha')},
        sedes=('vargas',), tema='combustibles',
        granularidad='mes', tipo_grafico='bar',
        etiqueta_y='Consumo de gasolina (gal)',
        nota='Consumo mensual de gasolina de la producción.',
    ),
    _gind(
        'g_combustible_acpm', 'Combustible ACPM producción', 'ACPM',
        'acpm', 'gal', 2, (0, 1000000), 'informativo',
        vistas={'vargas': ('general_combustible_acpm_prod', 'cantidad', 'fecha')},
        sedes=('vargas',), tema='combustibles',
        granularidad='mes', tipo_grafico='bar',
        etiqueta_y='Consumo de ACPM (gal)',
        nota='Consumo mensual de ACPM de la producción.',
    ),

    # ------------------------------------------------------------------
    # Residuos (Producción / Vargas)
    # ------------------------------------------------------------------
    _gind(
        'g_residuos_organicos', 'Residuos orgánicos totales producción',
        'Orgánicos', 'organicos', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'vargas': ('general_residuos_organicos_totales',
                           'total_organicos_kg', 'fecha')},
        filtro_sql="\"sede\" = 'Vargas (Producción)'",
        sedes=('vargas',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos orgánicos (kg)',
    ),
    _gind(
        'g_residuos_ordinarios', 'Residuos ordinarios totales producción',
        'Ordinarios', 'ordinarios', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'vargas': ('general_residuos_ordinarios_totales',
                           'cantidad_kg', 'fecha')},
        filtro_sql="\"sede\" = 'Vargas (Producción)'",
        sedes=('vargas',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos ordinarios (kg)',
    ),
    _gind(
        'g_residuos_especiales',
        'Cantidad de residuos especiales y/o peligrosos producción',
        'Especiales', 'especiales', 'kg', 2, (0, 1000000000), 'informativo',
        fuente_unica='general_cant_residuos_esp_peligrosos_pro',
        col_fecha='fecha', col_valor='total_residuos_especiales',
        sedes=('vargas',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos especiales (kg)',
    ),
    _gind(
        'g_residuos_reciclables', 'Residuos reciclables producción',
        'Reciclables', 'reciclables', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'vargas': ('general_residuos_reciclables_prod',
                           'cantidad_kg', 'fecha')},
        sedes=('vargas',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos reciclables (kg)',
    ),
    _gind(
        'g_total_residuos', 'Total de residuos producción',
        'Total residuos', 'total_residuos', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'vargas': ('general_total_residuos_prod',
                           'total_generados_kg', 'fecha')},
        sedes=('vargas',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Total de residuos (kg)',
    ),
    _gind(
        'g_aprovechamiento_residuos',
        'Porcentaje de aprovechamiento de residuos Vargas',
        'Aprovechamiento', 'aprovechamiento', '%', 1, (0, 100), 'informativo',
        vistas={'vargas': ('general_total_residuos_prod',
                           'porcentaje_aprovechamiento', 'fecha')},
        sedes=('vargas',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', etiqueta_y='% de aprovechamiento',
    ),

    # ------------------------------------------------------------------
    # Mortalidad (Producción / Vargas)
    # ------------------------------------------------------------------
    _gind(
        'g_mortalidad_pct', 'Porcentaje de mortalidad producción',
        'Mortalidad %', 'mortalidad', '%', 3, (0, 100), 'informativo',
        vistas={'vargas': ('general_mortalidad_prod',
                           'porcentaje_mortalidad', 'fecha')},
        sedes=('vargas',), tema='mortalidad', granularidad='mes',
        etiqueta_y='Porcentaje de mortalidad',
        nota='Porcentaje de mortalidad reportado por la vista de producción.',
    ),
    _gind(
        'g_mortalidad_aves', 'Aves muertas producción',
        'Aves muertas', 'mortalidad', 'aves', 0, (0, 1000000000), 'informativo',
        vistas={'vargas': ('general_mortalidad_prod', 'aves_muertas', 'fecha')},
        sedes=('vargas',), tema='mortalidad', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Aves muertas',
    ),
    _gind(
        'g_mortalidad_kg', 'Kilos de mortalidad producción',
        'Kg mortalidad', 'mortalidad', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'vargas': ('general_mortalidad_prod', 'kg_mortalidad', 'fecha')},
        sedes=('vargas',), tema='mortalidad', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Kg de mortalidad',
    ),

    # ------------------------------------------------------------------
    # Gallinaza (Producción / Vargas)
    # ------------------------------------------------------------------
    _gind(
        'g_gallinaza_kg_ave', 'Gallinaza: kg de abono por ave',
        'Kg abono/ave', 'gallinaza', 'kg/ave', 3, (0, 1000), 'informativo',
        vistas={'vargas': ('general_gallinaza_ave', 'kg_abono_ave', 'fecha')},
        sedes=('vargas',), tema='gallinaza', granularidad='mes',
        tipo_grafico='bar', etiqueta_y='Kg de abono por ave',
    ),

    # ------------------------------------------------------------------
    # Energía por unidad de producción (Vargas)
    # ------------------------------------------------------------------
    _gind(
        'g_energia_huevo', 'Consumo de energía por huevo producido',
        'kWh/huevo', 'energia', 'kWh/huevo', 4, (0, 100), 'informativo',
        fuente_unica='general_consumo_energia_huevo',
        col_fecha='fecha', col_valor='consumo_kw_x_unidad_huevo',
        sedes=('vargas',), tema='energia', granularidad='mes',
        etiqueta_y='Consumo kWh por huevo',
        nota='Consumo eléctrico por huevo producido. La tabla se poblará con '
             'el cierre de la migración.',
    ),

    # ------------------------------------------------------------------
    # Levante (Lourdes): combustibles GLP, residuos y mortalidad
    # ------------------------------------------------------------------
    _gind(
        'g_glp_lev', 'Consumo de GLP levante', 'GLP',
        'glp', 'gal', 2, (0, 200000), 'informativo',
        vistas={'lourdes': ('general_consumo_glp_lev', 'total_consumo_glp', 'fecha')},
        sedes=('lourdes',), tema='combustibles', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Consumo de GLP (gal)',
        nota='Consumo de GLP de la línea de levante.',
    ),

    _gind(
        'g_residuos_organicos_lev', 'Residuos orgánicos totales',
        'Orgánicos', 'organicos', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'lourdes': ('general_residuos_organicos_totales',
                            'total_organicos_kg', 'fecha')},
        filtro_sql="\"sede\" = 'Lourdes (Levante)'",
        sedes=('lourdes',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos orgánicos (kg)',
    ),
    _gind(
        'g_residuos_ordinarios_lev', 'Residuos ordinarios totales',
        'Ordinarios', 'ordinarios', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'lourdes': ('general_residuos_ordinarios_totales',
                            'cantidad_kg', 'fecha')},
        filtro_sql="\"sede\" = 'Lourdes (Levante)'",
        sedes=('lourdes',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos ordinarios (kg)',
    ),
    _gind(
        'g_residuos_especiales_lev',
        'Cantidad de residuos especiales y/o peligrosos',
        'Especiales', 'especiales', 'kg', 2, (0, 1000000000), 'informativo',
        fuente_unica='general_cantidad_residuos_especiales',
        col_fecha='fecha', col_valor='total_residuos_especiales',
        sedes=('lourdes',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos especiales (kg)',
    ),
    _gind(
        'g_residuos_reciclables_lev', 'Residuos reciclables',
        'Reciclables', 'reciclables', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'lourdes': ('general_residuos_reciclables_lev',
                            'cantidad_kg', 'fecha')},
        sedes=('lourdes',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Residuos reciclables (kg)',
    ),
    _gind(
        'g_total_residuos_lev', 'Total de residuos',
        'Total residuos', 'total_residuos', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'lourdes': ('general_total_residuos_lev',
                            'total_generados_kg', 'fecha')},
        sedes=('lourdes',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Total de residuos (kg)',
    ),
    _gind(
        'g_aprovechamiento_residuos_lev',
        'Porcentaje de aprovechamiento de residuos',
        'Aprovechamiento', 'aprovechamiento', '%', 1, (0, 100), 'informativo',
        vistas={'lourdes': ('general_total_residuos_lev',
                            'porcentaje_aprovechamiento', 'fecha')},
        sedes=('lourdes',), tema='residuos', granularidad='mes',
        tipo_grafico='bar', etiqueta_y='% de aprovechamiento',
    ),

    _gind(
        'g_mortalidad_pct_lev', 'Porcentaje de mortalidad',
        'Mortalidad %', 'mortalidad', '%', 3, (0, 100), 'informativo',
        vistas={'lourdes': ('general_mortalidad_lev',
                            'porcentaje_mortalidad', 'fecha')},
        sedes=('lourdes',), tema='mortalidad', granularidad='mes',
        etiqueta_y='Porcentaje de mortalidad',
    ),
    _gind(
        'g_mortalidad_aves_lev', 'Aves muertas',
        'Aves muertas', 'mortalidad', 'aves', 0, (0, 1000000000), 'informativo',
        vistas={'lourdes': ('general_mortalidad_lev', 'aves_muertas', 'fecha')},
        sedes=('lourdes',), tema='mortalidad', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Aves muertas',
    ),
    _gind(
        'g_mortalidad_kg_lev', 'Kilos de mortalidad',
        'Kg mortalidad', 'mortalidad', 'kg', 2, (0, 1000000000), 'informativo',
        vistas={'lourdes': ('general_mortalidad_lev', 'kg_mortalidad', 'fecha')},
        sedes=('lourdes',), tema='mortalidad', granularidad='mes',
        tipo_grafico='bar', agregacion_mensual='suma',
        etiqueta_y='Kg de mortalidad',
    ),

    # Aguas residuales de Levante
    _residual_lev('g_dqo_lev', 'DQO', 'DQO', 'dqo', 'mg/L', 2),
    _residual_lev('g_dbo_lev', 'DBO', 'DBO', 'dbo', 'mg/L', 2),
    _residual_lev('g_grasas_aceites_lev', 'Grasas y aceites', 'Grasas y aceites',
                  'grasas_aceites_residual', 'mg/L', 2),
    _residual_lev('g_caudal_residual_lev', 'Caudal', 'Caudal',
                  'caudal_residual', 'm³/s', 3),
    _residual_lev('g_ph_residual_lev', 'pH residual', 'pH residual',
                  'ph_residual', 'pH', 2),
    _residual_lev('g_temperatura_residual_lev', 'Temperatura', 'Temperatura',
                  'temperatura_residual', '°C', 2),
    _residual_lev('g_fluoruros_residual_lev', 'Fluoruros', 'Fluoruros',
                  'fluoruros_residual', 'mg/L', 2),
    _residual_lev('g_hidrocarburos_residual_lev', 'Hidrocarburos', 'Hidrocarburos',
                  'hidrocarburos_residual', 'mg/L', 2, col_tipo=None),
    _residual_lev('g_hierro_residual_lev', 'Hierro residual', 'Hierro residual',
                  'hierro_total_residual', 'mg/L', 2),
    _residual_lev('g_plomo_residual_lev', 'Plomo', 'Plomo',
                  'plomo_total_residual', 'mg/L', 3),
    _residual_lev('g_solidos_suspendidos_residual_lev', 'Sólidos suspendidos',
                  'Sólidos suspendidos', 'solidos_suspendidos_residual', 'mg/L', 2),
    _residual_lev('g_sulfuros_residual_lev', 'Sulfuros', 'Sulfuros',
                  'sulfuros_residual', 'mg/L', 2),

    _gind(
        'g_consumo_agua_domestica_lev',
        'Consumo prom. de agua doméstica ave/día levante',
        'Consumo agua doméstica', 'consumo', 'personas', 2, (0, 100000),
        'informativo',
        fuente_unica='general_consumo_agua_domestica',
        modo='anio_mes', col_anio='ano', col_mes_num='numero_mes', col_mes='mes',
        col_valor='prom_numero_personas',
        filtro_sql='"promedio_ml_persona" IS NOT NULL',
        extra=[('Promedio mL/persona', 'promedio_ml_persona')],
        sedes=('lourdes',), tema='agua', granularidad='anio', desglose='mes',
        etiqueta_y='Promedio de personas',
        nota='Vista de Looker: eje X año, desglose por mes, eje Y promedio de personas.',
    ),

    # ------------------------------------------------------------------
    # Consumo de agua
    # ------------------------------------------------------------------
    _gind(
        'g_consumo_agua_ave_prod', 'Consumo prom. de agua ave/día producción',
        'Consumo agua ave', 'consumo', 'mL/mes', 0, (0, 500000000), 'informativo',
        fuente_unica='general_consumo_agua_avedia_produccion',
        col_fecha='fecha', col_valor='promedio_mes_ml_galpones',
        filtro_sql='"promedio_mes_ml_galpones" IS NOT NULL',
        extra=[
            ('Número de aves', 'numero_aves'),
            ('Número de aves final', 'numero_aves_final'),
        ],
        referencia_valor=60000000, referencia_texto='60 Millones',
        sedes=('vargas',), granularidad='mes', tipo_grafico='bar',
        etiqueta_y='Promedio/Mes ml Galpones',
        nota='Vista de Looker: eje X fecha por año y mes, eje Y promedio/mes '
             'mL galpones, sin valores nulos.',
    ),
    _gind(
        'g_consumo_agua_domestica_prod',
        'Consumo prom. de agua doméstica ave/día producción',
        'Consumo agua doméstica', 'consumo', 'personas', 2, (0, 100000), 'informativo',
        fuente_unica='general_consumo_agua_domestica',
        modo='anio_mes', col_anio='ano', col_mes_num='numero_mes', col_mes='mes',
        col_valor='prom_numero_personas',
        filtro_sql='"promedio_ml_persona" IS NOT NULL',
        extra=[('Promedio mL/persona', 'promedio_ml_persona')],
        sedes=('vargas',), granularidad='anio', desglose='mes',
        etiqueta_y='Promedio de personas',
        nota='Vista de Looker: eje X año, desglose por mes, eje Y promedio de personas.',
    ),
    # Serie consolidada que hoy consume Levante (migración histórica).
    _gind(
        'g_consumo_agua_ave', 'Consumo de agua por ave', 'Consumo agua',
        'consumo', 'mL/ave/día', 2, (0, 10000), 'informativo',
        fuente_unica='general_consumo_prom_agua_ave_dia',
        col_fecha='fecha', col_valor='promedio_consumo_ml_ave',
        sedes=('lourdes',), granularidad='mes',
        etiqueta_y='Consumo promedio mL/ave/día',
        nota='Consumo promedio diario de agua por ave. Se alimenta del último '
             'lote de migración histórica.',
    ),
]

INDICADORES_GENERAL_POR_ID = {i['id']: i for i in INDICADORES_GENERAL}


def obtener_indicador_general(id_indicador):
    """Devuelve el indicador de General solicitado o None."""
    return INDICADORES_GENERAL_POR_ID.get(id_indicador)


def indicadores_general(linea, tema, sede=None):
    """
    Indicadores de una línea y tema, según la planta que le corresponde.

    Producción lee Vargas y Levante lee Lourdes. Se ocultan los parámetros que
    esa planta no mide.
    """
    info = LINEAS_GENERAL.get(linea)
    if not info:
        return []
    sede = sede or info['sede']

    if tema == 'agua':
        # Los indicadores de agua se heredan tal cual del modulo de la sede:
        # mismos limites, unidades, CTD, series opcionales y columnas de tabla.
        extra = [
            i for i in INDICADORES_GENERAL
            if i['tema'] == 'agua'
            and i['grupo'] in ('residual', 'consumo')
            and sede in i.get('sedes', ())
        ]
        return list(indicadores_de_sede(sede)) + extra

    return [
        i for i in INDICADORES_GENERAL
        if i['tema'] == tema and sede in i.get('sedes', ())
    ]


def indicadores_de_submodulo(linea, submodulo, tema='agua'):
    """
    Indicadores de un submódulo.

    Se filtra por grupo (laboratorio, residual, gasolina...) o por una lista
    explícita de ids cuando el submódulo es de una sola métrica.
    """
    lista = indicadores_general(linea, tema)
    if submodulo.get('grupo'):
        return [i for i in lista if i['grupo'] == submodulo['grupo']]
    ids = submodulo.get('indicadores') or []
    return [i for i in lista if i['id'] in ids]


def conteo_general(linea, tema=TEMA_GENERAL_POR_DEFECTO):
    """Numero de indicadores visibles en una linea y tema."""
    return len(indicadores_general(linea, tema))
