"""
Catalogo de indicadores de Gestion Ambiental.

Cada indicador describe de donde sale el dato en la base `master_ga`, con que
unidad se muestra, que rango fisico se considera valido (para descartar
registros corruptos) y cual es el limite normativo de referencia.

Los limites corresponden a la Resolucion 2115 de 2007 (agua potable) salvo que
se indique otra cosa. Se dejan aqui, en un solo lugar, para poder ajustarlos
sin tocar consultas ni plantillas.
"""

# Sedes disponibles. `activa` controla si el selector la habilita.
SEDES = {
    'lourdes': {
        'nombre': 'Lourdes',
        'prefijo': 'lourdes_',
        'activa': True,
    },
    'vargas': {
        'nombre': 'Vargas',
        'prefijo': 'vargas_',
        'activa': True,
    },
}

SEDE_POR_DEFECTO = 'lourdes'

GRUPOS = {
    'resumen': {
        'nombre': 'Resumen',
        'descripcion': 'Vista general de todos los indicadores de la sede.',
        'icono': 'bx-grid-alt',
    },
    'diario': {
        'nombre': 'Mediciones diarias',
        'descripcion': 'Registro diario de pH y cloro en planta y galpones.',
        'icono': 'bx-water',
    },
    'laboratorio': {
        'nombre': 'Laboratorio',
        'descripcion': 'Parametros fisicoquimicos y microbiologicos del agua.',
        'icono': 'bx-test-tube',
    },
}

GRUPO_POR_DEFECTO = 'resumen'


def _ind(id_, nombre, corto, grupo, tabla, col_fecha, col_valor, unidad,
         decimales, fisico, criterio, limite_min=None, limite_max=None,
         nota='', expresion=None, etiqueta_y='Valor real',
         tipo_grafico='line', granularidad='mes',
         etiqueta_limite_min=None, etiqueta_limite_max=None, mapa_sedes=None,
         vistas=None, sedes=('lourdes', 'vargas'), opcionales=None):
    """
    Construye el diccionario de un indicador con los valores por defecto.

    Si se indica `expresion`, el indicador se calcula con esa expresion SQL
    sobre las columnas crudas en lugar de leer una columna ya agregada.

    `vistas` permite leer el indicador desde una vista ya calculada por sede,
    por ejemplo {'lourdes': ('indicador_cloro_lev', 'prom_ponderado_cloro')}.
    Es la via preferida cuando Looker Studio consume esa misma vista, porque
    garantiza el mismo numero.

    `etiqueta_y` es el nombre de la metrica en el eje vertical del grafico.
    `tipo_grafico` puede ser 'line' o 'bar' y `granularidad` 'mes' o 'dia'.
    `mapa_sedes` permite sobrescribir columna o expresion en otra sede, porque
    los aplicativos de Lourdes y Vargas no usan los mismos nombres.
    Los indicadores diarios no muestran el valor sobre cada punto.
    """
    mapa = dict(mapa_sedes or {})
    if grupo == 'laboratorio' and col_valor in COLUMNAS_VARGAS:
        mapa.setdefault('vargas', {'col_valor': COLUMNAS_VARGAS[col_valor]})

    vistas_finales = dict(vistas or {})
    if grupo == 'laboratorio' and id_ in VISTAS_LAB:
        vista_lev, vista_prod = VISTAS_LAB[id_]
        vistas_finales.setdefault('lourdes', (vista_lev, 'valor_real', 'fecha'))
        vistas_finales.setdefault('vargas', (vista_prod, 'valor_real', 'fecha'))

    return {
        'id': id_,
        'nombre': nombre,
        'corto': corto,
        'grupo': grupo,
        'tabla': tabla,
        'col_fecha': col_fecha,
        'col_valor': col_valor,
        'expresion': expresion,
        'mapa_sedes': mapa,
        'vistas': vistas_finales,
        'col_tipo': 'tipo_agua' if grupo == 'laboratorio' else None,
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
        'opcionales': dict(opcionales or {}),
    }


_T_DIARIO = 'mediciones_in_situ_agua'
_T_LAB = 'analisis_agua_laboratorio'
_F_DIARIO = 'fecha_registro'
_F_LAB = 'fecha_toma'

# Vistas ya calculadas que consume Looker Studio, por indicador de laboratorio.
# (sufijo de Lourdes, sufijo de Vargas)
VISTAS_LAB = {
    'color_aparente': ('color_aparente_lev', 'color_aparente_prod'),
    'turbiedad': ('turbiedad_lev', 'turbiedad_prod'),
    'conductividad': ('conductividad_lev', 'conductividad_prod'),
    'cloro_residual': ('cloro_residual_libre_lev', 'cloro_residual_libre_prod'),
    'arsenico': ('arsenico_lev', 'arsenico_prod'),
    'mercurio': ('mercurio_lev', 'mercurio_prod'),
    'selenio': ('selenio_lev', 'selenio_prod'),
    'nitritos': ('nitritos_lev', 'nitritos_prod'),
    'nitratos': ('nitratos_lev', 'nitratos_prod'),
    'alcalinidad': ('alcalinidad_total_lev', 'alcalinidad_prod'),
    'cloruros': ('cloruros_lev', 'cloruros_prod'),
    'aluminio': ('aluminio_lev', 'aluminio_prod'),
    'dureza': ('dureza_total_lev', 'dureza_total_prod'),
    'hierro': ('hierro_total_lev', 'hierro_total_prod'),
    'magnesio': ('magnesio_lev', 'magnesio_prod'),
    'sulfatos': ('sulfatos_lev', 'sulfatos_prod'),
    'fosfatos': ('fosfatos_lev', 'fosfatos_prod'),
    'coliformes_totales': ('coliformes_totales_lev', 'coliformes_totales_prod'),
    'escherichia_coli': ('escherichia_coli_lev', 'escherichia_coli_prod'),
    'heterotrofos': ('heterotrofos_lev', 'heterotrofos_prod'),
    'pseudomona': ('pseudomona_lev', 'pseudomona_prod'),
}

# Equivalencias de columnas entre el aplicativo de Lourdes y el de Vargas.
# Vargas sufija casi todos los parametros con `_valor_numerico`.
COLUMNAS_VARGAS = {
    'color_numerico': 'color_valor_numerico',
    'turbiedad_numerico': 'turbiedad_valor_numerico',
    'conductividad_numerico': 'conductividad_valor_numerico',
    'cloro_residual_numerico': 'cloro_residual_valor_numerico',
    'arsenico_total_numerico': 'arsenico_valor_numerico',
    'mercurio_numerico': 'mercurio_valor_numerico',
    'selenio_total_numerico': 'selenio_total_valor_numerico',
    'nitritos_numerico': 'nitritos_valor_numerico',
    'nitratos_numerico': 'nitratos_valor_numerico',
    'alcalinidad_numerico': 'alcalinidad_valor_numerico',
    'cloruros_numerico': 'cloruros_valor_numerico',
    'aluminio_numerico': 'aluminio_numerico',
    'dureza_numerico': 'dureza_valor_numerico',
    'hierro_total_numerico': 'hierro_total_valor_numerico',
    'magneso_total_numerico': 'magnesio_total_valor_numerico',
    'sulfatos_numerico': 'sulfatos_valor_numerico',
    'ortofosfato_numerico': 'ortofosfatos_valor_numerico',
    'coliformes_totales_numerico': 'coliformes_totales_valor_numerico',
    'e_coli_numerico': 'e_coli_valor_numerico',
    'heterotrofos_numerico': 'heterotrofos_valor_numerico',
    'pseudomona_numerico': 'pseudomona_valor_numerico',
}

INDICADORES = [
    # ------------------------------------------------------------------
    # Mediciones diarias (in situ)
    # ------------------------------------------------------------------
    _ind(
        'prom_cloro_diario', 'Promedio cloro mg/L diario', 'Cloro',
        'diario', _T_DIARIO, _F_DIARIO, 'promedio_cloro_total',
        'mg/L', 3, (0, 5), 'rango', 1.0, 2.5,
        'Promedio de las tomas finales de los dos galpones. '
        'Rango de control de la planta: mínimo 1,0 y máximo 2,5 mg/L.',
        expresion="""CASE WHEN toma_1_cloro_galpon_final IS NULL
                              AND toma_2_cloro_galpon_final IS NULL THEN NULL
                     ELSE (COALESCE(toma_1_cloro_galpon_final, toma_2_cloro_galpon_final)
                         + COALESCE(toma_2_cloro_galpon_final, toma_1_cloro_galpon_final)) / 2.0
                END""",
        etiqueta_y='Promedio ponderado cloro',
        tipo_grafico='bar',
        granularidad='dia',
        etiqueta_limite_min='MIN (1)',
        etiqueta_limite_max='MAX (2,5)',
        vistas={
            'lourdes': ('indicador_cloro_lev', 'prom_ponderado_cloro', 'fecha_registro'),
            'vargas': ('indicador_cloro_prod', 'promedio_ponderado_cloro', 'fecha'),
        },
        opcionales={
            'vargas': [
                ('Cloro galpón final', 'cloro_galpon_final'),
                ('Cloro galpón intermedio', 'cloro_galpon_intermedio'),
                ('Cloro PTAP', 'cloro_ptap'),
            ],
        },
        mapa_sedes={
            'vargas': {'col_valor': 'cloro_galpon_final', 'expresion': None},
        },
    ),
    _ind(
        'prom_ph_diario', 'Promedio pH diario', 'pH',
        'diario', _T_DIARIO, _F_DIARIO, 'promedio_toma_final_ph',
        'pH', 2, (0, 14), 'rango', 5.0, 5.5,
        'Promedio de las tomas finales de los galpones. '
        'Rango de control de la planta: mínimo 5,0 y máximo 5,5.',
        expresion="""CASE WHEN toma_1_ph_galpon_final IS NULL
                              AND toma_2_ph_galpon_final IS NULL THEN NULL
                     ELSE (COALESCE(toma_1_ph_galpon_final, toma_2_ph_galpon_final)
                         + COALESCE(toma_2_ph_galpon_final, toma_1_ph_galpon_final)) / 2.0
                END""",
        etiqueta_y='Promedio ponderado pH',
        tipo_grafico='line',
        granularidad='dia',
        etiqueta_limite_min='MIN (5)',
        etiqueta_limite_max='MAX (5,5)',
        vistas={
            'lourdes': ('indicador_ph_lev', 'promedio_ponderado_ph', 'fecha_registro'),
            'vargas': ('indicador_ph_prod', 'promedio_ponderado_ph', 'fecha'),
        },
        mapa_sedes={
            'vargas': {
                'col_valor': None,
                'expresion': """CASE WHEN toma_1_ph_galpon_final_am IS NULL
                                          AND toma_2_ph_galpon_final_am IS NULL
                                          AND toma_1_ph_galpon_final_pm IS NULL
                                          AND toma_2_ph_galpon_final_pm IS NULL THEN NULL
                                 ELSE (COALESCE(toma_1_ph_galpon_final_am, 0)
                                     + COALESCE(toma_2_ph_galpon_final_am, 0)
                                     + COALESCE(toma_1_ph_galpon_final_pm, 0)
                                     + COALESCE(toma_2_ph_galpon_final_pm, 0))
                                     / NULLIF((toma_1_ph_galpon_final_am IS NOT NULL)::int
                                            + (toma_2_ph_galpon_final_am IS NOT NULL)::int
                                            + (toma_1_ph_galpon_final_pm IS NOT NULL)::int
                                            + (toma_2_ph_galpon_final_pm IS NOT NULL)::int, 0)
                            END""",
            },
        },
    ),

    # ------------------------------------------------------------------
    # Laboratorio (analisis de agua)
    # ------------------------------------------------------------------
    _ind('color_aparente', 'Color aparente', 'Color',
         'laboratorio', _T_LAB, _F_LAB, 'color_numerico',
         'UPC', 0, (0, 1000), 'maximo', None, 15,
         'Res. 2115: maximo 15 UPC.'),
    _ind('turbiedad', 'Turbiedad', 'Turbiedad',
         'laboratorio', _T_LAB, _F_LAB, 'turbiedad_numerico',
         'UNT', 2, (0, 100), 'maximo', None, 2,
         'Res. 2115: maximo 2 UNT. En Vargas, Looker grafica el recuento '
         'distinto de valores (CTD).',
         mapa_sedes={
             'vargas': {
                 'agregacion': 'ctd',
                 'unidad': 'valores',
                 'etiqueta_y': 'Recuento distinto',
             },
         }),
    _ind('conductividad', 'Conductividad', 'Conductividad',
         'laboratorio', _T_LAB, _F_LAB, 'conductividad_numerico',
         'uS/cm', 1, (0, 2000), 'maximo', None, 1000,
         'Res. 2115: maximo 1000 uS/cm.'),
    _ind('cloro_residual', 'Cloro residual', 'Cloro residual',
         'laboratorio', _T_LAB, _F_LAB, 'cloro_residual_numerico',
         'mg/L', 2, (0, 5), 'rango', 0.3, 2.0,
         'Res. 2115: 0,3 a 2,0 mg/L.'),
    _ind('arsenico', 'Arsenico (As)', 'Arsenico',
         'laboratorio', _T_LAB, _F_LAB, 'arsenico_total_numerico',
         'mg/L', 4, (0, 1), 'maximo', None, 0.01,
         'Res. 2115: maximo 0,01 mg/L.'),
    _ind('mercurio', 'Mercurio (Hg)', 'Mercurio',
         'laboratorio', _T_LAB, _F_LAB, 'mercurio_numerico',
         'mg/L', 4, (0, 1), 'maximo', None, 0.001,
         'Res. 2115: maximo 0,001 mg/L.'),
    _ind('selenio', 'Selenio (Se)', 'Selenio',
         'laboratorio', _T_LAB, _F_LAB, 'selenio_total_numerico',
         'mg/L', 4, (0, 1), 'maximo', None, 0.01,
         'Res. 2115: maximo 0,01 mg/L.'),
    _ind('nitritos', 'Nitritos (NO2-)', 'Nitritos',
         'laboratorio', _T_LAB, _F_LAB, 'nitritos_numerico',
         'mg/L', 3, (0, 10), 'maximo', None, 0.1,
         'Res. 2115: maximo 0,1 mg/L.'),
    _ind('nitratos', 'Nitratos (NO3-)', 'Nitratos',
         'laboratorio', _T_LAB, _F_LAB, 'nitratos_numerico',
         'mg/L', 2, (0, 100), 'maximo', None, 10,
         'Res. 2115: maximo 10 mg/L.'),
    _ind('alcalinidad', 'Alcalinidad total (CaCO3)', 'Alcalinidad',
         'laboratorio', _T_LAB, _F_LAB, 'alcalinidad_numerico',
         'mg/L', 1, (0, 1000), 'maximo', None, 200,
         'Res. 2115: maximo 200 mg/L.'),
    _ind('cloruros', 'Cloruros (Cl-)', 'Cloruros',
         'laboratorio', _T_LAB, _F_LAB, 'cloruros_numerico',
         'mg/L', 2, (0, 1000), 'maximo', None, 250,
         'Res. 2115: maximo 250 mg/L.'),
    _ind('aluminio', 'Aluminio (Al3+)', 'Aluminio',
         'laboratorio', _T_LAB, _F_LAB, 'aluminio_numerico',
         'mg/L', 3, (0, 5), 'maximo', None, 0.2,
         'Res. 2115: maximo 0,2 mg/L.'),
    _ind('dureza', 'Dureza total (CaCO3)', 'Dureza',
         'laboratorio', _T_LAB, _F_LAB, 'dureza_numerico',
         'mg/L', 1, (0, 2000), 'maximo', None, 300,
         'Res. 2115: maximo 300 mg/L.'),
    _ind('hierro', 'Hierro laboratorio (Fe)', 'Hierro lab',
         'laboratorio', _T_LAB, _F_LAB, 'hierro_total_numerico',
         'mg/L', 3, (0, 10), 'maximo', None, 0.3,
         'Res. 2115: maximo 0,3 mg/L.'),
    _ind('magnesio', 'Magnesio (Mg)', 'Magnesio',
         'laboratorio', _T_LAB, _F_LAB, 'magneso_total_numerico',
         'mg/L', 3, (0, 200), 'maximo', None, 36,
         'Res. 2115: maximo 36 mg/L.'),
    _ind('sulfatos', 'Sulfatos (SO42-)', 'Sulfatos',
         'laboratorio', _T_LAB, _F_LAB, 'sulfatos_numerico',
         'mg/L', 2, (0, 1000), 'maximo', None, 250,
         'Res. 2115: maximo 250 mg/L.'),
    _ind('fosfatos', 'Fosfatos (PO43-)', 'Fosfatos',
         'laboratorio', _T_LAB, _F_LAB, 'ortofosfato_numerico',
         'mg/L', 2, (0, 50), 'maximo', None, 0.5,
         'Res. 2115: maximo 0,5 mg/L.'),
    _ind('coliformes_totales', 'Coliformes totales', 'Coliformes',
         'laboratorio', _T_LAB, _F_LAB, 'coliformes_totales_numerico',
         'UFC/100 mL', 0, (0, 1000000), 'cero', None, 0,
         'Res. 2115: 0 UFC/100 mL.'),
    _ind('escherichia_coli', 'Escherichia coli', 'E. coli',
         'laboratorio', _T_LAB, _F_LAB, 'e_coli_numerico',
         'UFC/100 mL', 0, (0, 1000000), 'cero', None, 0,
         'Res. 2115: 0 UFC/100 mL.'),
    _ind('heterotrofos', 'Heterotrofos', 'Heterotrofos',
         'laboratorio', _T_LAB, _F_LAB, 'heterotrofos_numerico',
         'UFC/mL', 0, (0, 1000000), 'maximo', None, 100,
         'Lourdes: máximo 100 UFC/mL. Vargas: máximo 500 UFC/mL.',
         mapa_sedes={'vargas': {'limite_max': 500}}),
    _ind('pseudomona', 'Pseudomona', 'Pseudomona',
         'laboratorio', _T_LAB, _F_LAB, 'pseudomona_numerico',
         'UFC/100 mL', 0, (0, 1000000), 'cero', None, 0,
         'Res. 2115: ausencia.'),

    # ------------------------------------------------------------------
    # Solo Vargas (el aplicativo de Lourdes no mide estos parametros)
    # ------------------------------------------------------------------
    _ind('hierro_ptap', 'Hierro PTAP', 'Hierro PTAP',
         'diario', _T_DIARIO, _F_DIARIO, 'hierro_ptap',
         'mg/L', 2, (0, 100), 'maximo', None, 0.3,
         'Hierro medido en la planta de tratamiento.',
         etiqueta_y='Hierro PTAP',
         tipo_grafico='line', granularidad='dia',
         sedes=('vargas',),
         vistas={'vargas': ('indicador_hierro_prod', 'hierro_ptap', 'fecha')}),
    _ind('calcio', 'Calcio (Ca)', 'Calcio',
         'laboratorio', _T_LAB, _F_LAB, 'calcio_numerico',
         'mg/L', 2, (0, 1000), 'maximo', None, 60,
         'Res. 2115: máximo 60 mg/L.',
         sedes=('vargas',),
         vistas={'vargas': ('calcio_prod', 'valor_real', 'fecha')}),
    _ind('carbono_organico_total', 'Carbono orgánico total', 'COT',
         'laboratorio', _T_LAB, _F_LAB, 'carbono_organico_total_numerico',
         'mg/L', 2, (0, 200), 'informativo',
         nota='Parámetro informativo, sin límite definido.',
         sedes=('vargas',),
         vistas={'vargas': ('carbono_organico_prod', 'valor_real', 'fecha')}),
    _ind('cryptosporidium', 'Cryptosporidium', 'Cryptosporidium',
         'laboratorio', _T_LAB, _F_LAB, 'cryptosporidium_numerico',
         'ooq/L', 0, (0, 1000000), 'cero', None, 0,
         'Ausencia esperada.',
         sedes=('vargas',),
         vistas={'vargas': ('cryptosporidium_prod', 'valor_real', 'fecha')}),
    _ind('fluoruros', 'Fluoruros (F-)', 'Fluoruros',
         'laboratorio', _T_LAB, _F_LAB, 'fluoruros_numerico',
         'mg/L', 2, (0, 50), 'maximo', None, 1.0,
         'Res. 2115: máximo 1,0 mg/L.',
         sedes=('vargas',),
         vistas={'vargas': ('fluoruros_prod', 'valor_real', 'fecha')}),
    _ind('fosforo', 'Fósforo (P)', 'Fósforo',
         'laboratorio', _T_LAB, _F_LAB, 'fosforo_numerico',
         'mg/L', 2, (0, 100), 'maximo', None, 0.1,
         'Referencia de la vista: máximo 0,1 mg/L.',
         sedes=('vargas',),
         vistas={'vargas': ('fosforo_prod', 'valor_real', 'fecha')}),
    _ind('manganeso', 'Manganeso (Mn)', 'Manganeso',
         'laboratorio', _T_LAB, _F_LAB, 'manganeso_numerico',
         'mg/L', 3, (0, 50), 'maximo', None, 0.1,
         'Res. 2115: máximo 0,1 mg/L.',
         sedes=('vargas',),
         vistas={'vargas': ('manganeso_prod', 'valor_real', 'fecha')}),
    _ind('mesofilos', 'Mesófilos', 'Mesófilos',
         'laboratorio', _T_LAB, _F_LAB, 'mesofilos_numerico',
         'UFC/mL', 0, (0, 10000000), 'maximo', None, 100,
         'Referencia de la vista: máximo 100 UFC/mL.',
         sedes=('vargas',),
         vistas={'vargas': ('mesofilos_prod', 'valor_real', 'fecha')}),
]

INDICADORES_POR_ID = {i['id']: i for i in INDICADORES}


def obtener_indicador(id_indicador):
    """Devuelve el indicador solicitado o None si no existe."""
    return INDICADORES_POR_ID.get(id_indicador)


def indicadores_del_grupo(grupo, sede=None):
    """Lista los indicadores de un grupo, en el orden del catalogo."""
    lista = indicadores_de_sede(sede) if sede else INDICADORES
    return [i for i in lista if i['grupo'] == grupo]


# Orden de presentacion propio de Vargas.
ORDEN_POR_SEDE = {
    'vargas': [
        'prom_cloro_diario', 'prom_ph_diario', 'hierro_ptap',
        'color_aparente', 'turbiedad', 'alcalinidad', 'aluminio', 'arsenico',
        'calcio', 'carbono_organico_total', 'cloro_residual', 'cloruros',
        'coliformes_totales', 'conductividad', 'cryptosporidium', 'dureza',
        'escherichia_coli', 'fluoruros', 'fosfatos', 'fosforo',
        'heterotrofos', 'hierro', 'magnesio', 'manganeso', 'mercurio',
        'mesofilos', 'nitratos', 'nitritos', 'pseudomona', 'selenio',
        'sulfatos',
    ],
}


def indicadores_de_sede(sede):
    """Indicadores disponibles en la sede, en el orden que le corresponde."""
    lista = [i for i in INDICADORES if sede in i.get('sedes', ('lourdes', 'vargas'))]
    orden = ORDEN_POR_SEDE.get(sede)
    if orden:
        posicion = {id_: n for n, id_ in enumerate(orden)}
        lista.sort(key=lambda i: (posicion.get(i['id'], 999), i['id']))
    return lista


CAMPOS_POR_SEDE = ('limite_min', 'limite_max', 'agregacion', 'etiqueta_y', 'unidad', 'criterio')


def indicador_para_sede(indicador, sede):
    """
    Copia el indicador aplicando los ajustes propios de la sede, si los tiene.

    Sirve para casos como heterotrofos (limite 500 en Vargas y 100 en Lourdes)
    o turbiedad de Vargas, que Looker grafica como recuento distinto.
    """
    override = (indicador.get('mapa_sedes') or {}).get(sede) or {}
    if not any(campo in override for campo in CAMPOS_POR_SEDE):
        return indicador

    copia = dict(indicador)
    for campo in CAMPOS_POR_SEDE:
        if campo in override:
            copia[campo] = override[campo]

    if copia.get('agregacion') == 'ctd':
        copia['criterio'] = 'informativo'
        copia['limite_min'] = None
        copia['limite_max'] = None
        copia['mostrar_valores'] = True
    return copia


def primer_indicador(grupo=None):
    """Primer indicador del grupo indicado (o del catalogo completo)."""
    if grupo:
        lista = indicadores_del_grupo(grupo)
        return lista[0] if lista else None
    return INDICADORES[0]


# ----------------------------------------------------------------------
# Slugs cortos para las URL (/ga/<sede>/<grupo>/<indicador>)
# ----------------------------------------------------------------------
GRUPO_A_SLUG = {
    'resumen': 'todo',
    'diario': 'diario',
    'laboratorio': 'lab',
}
SLUG_A_GRUPO = {v: k for k, v in GRUPO_A_SLUG.items()}

# Etiquetas normalizadas para la dimension de desglose.
TIPOS_AGUA = {
    'tratada': 'Tratada',
    'sin tratar': 'Sin tratar',
    'cruda': 'Cruda',
    'acueducto': 'Acueducto',
}
TIPO_SIN_CLASIFICAR = 'Sin clasificar'


def normalizar_tipo(valor):
    """Unifica las variantes de `tipo_agua` que trae AppSheet."""
    if valor is None:
        return TIPO_SIN_CLASIFICAR
    texto = str(valor).strip()
    if not texto:
        return TIPO_SIN_CLASIFICAR
    return TIPOS_AGUA.get(texto.lower(), texto.title())
