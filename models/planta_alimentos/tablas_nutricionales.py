# -*- coding: utf-8 -*-
"""
Tablas Nutricionales - Fase 1

Une los datos que ya existen en Produccion (cabecera del lote, consumo, peso,
conversion, % de produccion) con la evaluacion nutricional importada del Excel
(tabla `tn_registros`).

No duplica informacion: los indicadores se leen de:
  - semanal_levante  (semanas 1 a 17)
  - bd_vargas        (semana 18 en adelante)
"""
import io
import unicodedata
from datetime import date, datetime

from psycopg2.extras import Json

from models.base import get_db_connection

# Parametros nutricionales que se muestran en la tabla y en los graficos.
# (codigo, etiqueta, unidad)
NUTRIENTES = [
    ('proteina', 'Proteína', 'g'),
    ('metionina', 'Metionina', 'mg'),
    ('met_cistina', 'Metionina + Cistina', 'mg'),
    ('lisina', 'Lisina', 'mg'),
    ('triptofano', 'Triptófano', 'mg'),
    ('treonina', 'Treonina', 'mg'),
    ('arginina', 'Arginina', 'mg'),
    ('isoleucina', 'Isoleucina', 'mg'),
    ('valina', 'Valina', 'mg'),
    ('calcio', 'Calcio', 'g'),
    ('rel_ca_p', 'Relación Ca / P', ''),
    ('fosforo', 'Fósforo disp.', 'mg'),
    ('sodio', 'Sodio', 'g'),
    ('potasio', 'Potasio', 'mg'),
    ('cloro', 'Cloro', 'g'),
    ('energia', 'Energía', 'Kcal'),
    ('energia_max', 'Energía máxima', 'Kcal'),
]

# Columnas que se muestran por nutriente (las originales del Excel, sin duplicar "Real")
SUBS_POR_NUTRIENTE = {
    'calcio': [('tabla', 'Guía'), ('real', 'Real'), ('formu', 'Formu'),
               ('adicional_alimento', 'Adic. alimento'), ('adicional_biocalcio', 'Adic. biocalcio'),
               ('dif', 'Dif')],
    'rel_ca_p': [('tabla', 'Guía'), ('real', 'Real'), ('dif', 'Dif')],
    'fosforo': [('tabla', 'Guía'), ('real', 'Real'), ('formu', 'Formu'), ('dif', 'Dif')],
    'potasio': [('tabla', 'Guía'), ('formu', 'Formu'), ('real', 'Real'), ('dif', 'Dif')],
    'energia': [('tabla_min', 'Tabla mín'), ('tabla_sup', 'Tabla máx'), ('real', 'Real'),
                ('formu', 'Formu'), ('dif', 'Dif')],
    'energia_max': [('tabla', 'Tabla'), ('formu', 'Formu'), ('real', 'Real'), ('dif', 'Dif')],
}
SUBS_DEFAULT = [('tabla', 'Guía'), ('pro', 'PRO'), ('real', 'Real'), ('formu', 'Formu'), ('dif', 'Dif')]

# Columnas que el usuario puede editar (las demas son guia o formulas)
SUBS_EDITABLES = {'pro', 'formu', 'adicional_alimento', 'adicional_biocalcio'}

# Campos del bloque de indicadores que se pueden editar
CORE_EDITABLES = {'gramos', 'conversion', 'peso', 'produccion', 'precio_formula', 'costo_huevo'}

# Formulas del Excel: nutrientes cuyo "Real" se multiplica por 1000
NUTRIENTES_X1000 = {'metionina', 'met_cistina', 'lisina', 'triptofano', 'treonina',
                    'arginina', 'isoleucina', 'valina', 'sodio', 'potasio', 'cloro'}
# Nutrientes cuya diferencia se mide contra PRO (los demas contra la tabla)
NUTRIENTES_VS_PRO = {'proteina', 'metionina', 'met_cistina', 'lisina', 'triptofano',
                     'treonina', 'arginina', 'isoleucina', 'valina'}


def columnas_nutrientes():
    """Lista (codigo, etiqueta, unidad, subs) para pintar el encabezado."""
    return [(codigo, etiqueta, unidad, SUBS_POR_NUTRIENTE.get(codigo, SUBS_DEFAULT))
            for codigo, etiqueta, unidad in NUTRIENTES]


# Analisis: un grafico por indicador (mismos del libro de Excel)
GRAFICOS = [
    {'codigo': 'peso_consumo', 'titulo': 'Peso y consumo', 'tipo': 'core', 'unidad': 'g'},
    {'codigo': 'ca_p_r', 'titulo': 'Análisis CA-P-R', 'tipo': 'capr', 'unidad': 'g/ave/día'},
    {'codigo': 'proteina', 'titulo': 'Proteína', 'nutriente': 'proteina', 'unidad': 'g'},
    {'codigo': 'metionina', 'titulo': 'Metionina', 'nutriente': 'metionina', 'unidad': 'mg'},
    {'codigo': 'met_cistina', 'titulo': 'Metionina + Cistina', 'nutriente': 'met_cistina', 'unidad': 'mg'},
    {'codigo': 'lisina', 'titulo': 'Lisina', 'nutriente': 'lisina', 'unidad': 'mg'},
    {'codigo': 'triptofano', 'titulo': 'Triptófano', 'nutriente': 'triptofano', 'unidad': 'mg'},
    {'codigo': 'treonina', 'titulo': 'Treonina', 'nutriente': 'treonina', 'unidad': 'mg'},
    {'codigo': 'arginina', 'titulo': 'Arginina', 'nutriente': 'arginina', 'unidad': 'mg'},
    {'codigo': 'isoleucina', 'titulo': 'Isoleucina', 'nutriente': 'isoleucina', 'unidad': 'mg'},
    {'codigo': 'valina', 'titulo': 'Valina', 'nutriente': 'valina', 'unidad': 'mg'},
    {'codigo': 'calcio', 'titulo': 'Calcio', 'nutriente': 'calcio', 'unidad': 'g'},
    {'codigo': 'rel_ca_p', 'titulo': 'Relación Ca / P', 'nutriente': 'rel_ca_p', 'unidad': ''},
    {'codigo': 'fosforo', 'titulo': 'Fósforo disponible', 'nutriente': 'fosforo', 'unidad': 'g'},
    {'codigo': 'sodio', 'titulo': 'Sodio', 'nutriente': 'sodio', 'unidad': 'g'},
    {'codigo': 'energia', 'titulo': 'Energía', 'nutriente': 'energia', 'unidad': 'Kcal'},
]

# Tramo de semanas criticas que la empresa marca con linea punteada en el Excel
SEMANAS_CRITICAS = (12, 24)


def _serie_limpia(valores):
    """En las graficas, un 0 se trata como dato faltante para no dibujar caidas."""
    return [None if (v is None or v == 0) else v for v in valores]


def _limpio(valor):
    return None if (valor is None or valor == 0) else valor


def _promedio(valores):
    limpios = [v for v in valores if v is not None]
    return (sum(limpios) / len(limpios)) if limpios else None


def _ultimo(valores):
    for valor in reversed(valores):
        if valor is not None:
            return valor
    return None

GRUPOS_EXCEL = [
    ('proteina', 'proteina'),
    ('metionina + cistina', 'met_cistina'),
    ('metionina', 'metionina'),
    ('lisina', 'lisina'),
    ('triptofano', 'triptofano'),
    ('treonina', 'treonina'),
    ('arginina', 'arginina'),
    ('isoleucina', 'isoleucina'),
    ('valina', 'valina'),
    ('calcio', 'calcio'),
    ('relacion ca', 'rel_ca_p'),
    ('fosf', 'fosforo'),
    ('sodio', 'sodio'),
    ('potasio', 'potasio'),
    ('cloro', 'cloro'),
    ('energia maxima', 'energia_max'),
    ('energia', 'energia'),
]

ETAPAS = [
    (3, 'Pre-iniciación'),
    (6, 'Iniciación'),
    (12, 'Crecimiento'),
    (17, 'Desarrollo'),
    (999, 'Producción'),
]

# Clase CSS de cada etapa: pinta toda la fila con un color propio
ETAPA_CLASES = {
    'Pre-iniciación': 'pre',
    'Iniciación': 'ini',
    'Crecimiento': 'cre',
    'Desarrollo': 'des',
    'Producción': 'pro',
}


def _norm(texto):
    if texto is None:
        return ''
    base = unicodedata.normalize('NFKD', str(texto))
    base = ''.join(c for c in base if not unicodedata.combining(c))
    return ' '.join(base.replace('\n', ' ').strip().lower().split())


def _num(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip().replace(' ', '').replace('\xa0', '')
    if not texto:
        return None

    if ',' in texto:
        # Formato español: 1.234,56
        texto = texto.replace('.', '').replace(',', '.')
    elif texto.count('.') > 1:
        # Varios puntos: separadores de miles
        texto = texto.replace('.', '')
    elif texto.count('.') == 1:
        entero, decimales = texto.split('.')
        # "1.796" son miles; "0.213" o "2.80" son decimales
        if len(decimales) == 3 and entero and not entero.startswith('0') and len(entero) <= 3:
            texto = entero + decimales

    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def _fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()[:10]
        try:
            return date.fromisoformat(texto)
        except ValueError:
            return None
    return None


def etapa_de(semana):
    try:
        semana = int(semana)
    except (TypeError, ValueError):
        return ''
    for limite, nombre in ETAPAS:
        if semana <= limite:
            return nombre
    return ''


def _codigo_grupo(texto):
    t = _norm(texto)
    # El Excel trae un bloque "IND" con los mismos valores por x10: no se duplica
    if 'mg x10' in t or t.endswith(' ind'):
        return None
    for clave, codigo in GRUPOS_EXCEL:
        if t.startswith(clave):
            return codigo
    return None


def _codigo_sub(texto):
    t = _norm(texto)
    if not t:
        return None
    if t.startswith('dif'):
        return 'dif'
    if t == 'eco':
        return 'eco'
    if t == 'pro':
        return 'pro'
    if t.startswith('real'):
        return 'real'
    if t.startswith('formu'):
        return 'formu'
    if t == 'tabla min':
        return 'tabla_min'
    if t == 'tabla sup':
        return 'tabla_sup'
    if t.startswith('tabla'):
        return 'tabla'
    if 'alimento' in t:
        return 'adicional_alimento'
    if 'biocalcio' in t:
        return 'adicional_biocalcio'
    return None


class TablaNutricional:

    @staticmethod
    def _fotos_catalogo(meta, cur=None):
        """Foto del nutricionista y de la variedad, igual que en Producción."""
        from models.catalogos import services as catalogos_services

        def buscar(tipos, nombre):
            nombre = (nombre or '').strip()
            if not nombre:
                return None
            for tipo in tipos:
                _, url = catalogos_services.foto_por_nombre(tipo, nombre)
                if url and 'placeholder-catalogo' not in url:
                    return url
            return None

        return {
            'nutricionista': buscar(
                ['nutricionista_prod', 'nutricionista_lev'],
                meta.get('nutricionista_prod') or meta.get('nutricionista')
            ),
            'variedad': buscar(['variedad'], meta.get('variedad')),
            'marca': buscar(['marca_galpon'], meta.get('marca_galpon')),
        }

    @staticmethod
    def _recalcular(nutrientes):
        """Replica las formulas del Excel: Real y Dif a partir de Formu/Gramos/guia."""
        core = nutrientes.setdefault('_core', {})
        gramos = _num(core.get('gramos')) or 0.0
        consumo2 = _num(core.get('consumo2')) or 0.0

        # Potasio y Cloro: su valor de tabla es una formula del Excel
        proteina = nutrientes.get('proteina') or {}
        potasio = nutrientes.setdefault('potasio', {})
        if _num(proteina.get('formu')) is not None:
            potasio['tabla'] = (_num(proteina.get('formu')) or 0.0) * 0.18 * 10
        cloro = nutrientes.setdefault('cloro', {})
        cloro['tabla'] = consumo2 * 0.18 * 10

        for code, nodo in nutrientes.items():
            if code in ('_core', 'rel_ca_p') or not isinstance(nodo, dict):
                continue

            formu = _num(nodo.get('formu')) or 0.0
            real = None
            if code == 'proteina':
                real = formu * gramos
            elif code in NUTRIENTES_X1000:
                real = formu * gramos * 1000
            elif code == 'calcio':
                ad1 = _num(nodo.get('adicional_alimento')) or 0.0
                ad2 = _num(nodo.get('adicional_biocalcio')) or 0.0
                real = (formu * gramos / 100) + (ad1 * 0.37) + (ad2 * 0.0179)
            elif code == 'fosforo':
                real = formu * gramos
            elif code in ('energia', 'energia_max'):
                real = formu * gramos / 1000
            else:
                real = formu * gramos

            nodo['real'] = real
            if code in NUTRIENTES_VS_PRO:
                referencia = _num(nodo.get('pro'))
            elif code == 'energia':
                referencia = _num(nodo.get('tabla_sup'))
            else:
                referencia = _num(nodo.get('tabla'))
            nodo['dif'] = (real - referencia) if (real is not None and referencia is not None) else None

        # Relacion Ca/P: depende del calcio y fosforo ya calculados
        relacion = nutrientes.setdefault('rel_ca_p', {})
        calcio_real = _num((nutrientes.get('calcio') or {}).get('real'))
        fosforo_real = _num((nutrientes.get('fosforo') or {}).get('real'))
        rel_real = (calcio_real / fosforo_real) if (calcio_real and fosforo_real) else None
        relacion['real'] = rel_real
        rel_tabla = _num(relacion.get('tabla'))
        relacion['dif'] = (rel_real - rel_tabla) if (rel_real is not None and rel_tabla is not None) else None
        return nutrientes

    @staticmethod
    def actualizar_celda(lote, semana, campo, valor, usuario):
        """Guarda un valor editable y recalcula las formulas de esa semana."""
        conn = get_db_connection()
        valores = {}
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT nutrientes, fecha, observaciones
                    FROM tn_registros WHERE lote = %s AND semana = %s
                """, (lote, semana))
                fila = cur.fetchone()
                nutrientes = dict(fila[0] or {}) if fila else {}
                fecha = fila[1] if fila else None
                observaciones = (fila[2] or '') if fila else ''

                if not fecha:
                    cur.execute("""
                        SELECT fecha_fin_sem FROM bd_vargas
                        WHERE lote = %s AND sem_prod = %s
                    """, (lote, semana))
                    encontrada = cur.fetchone()
                    fecha = _fecha(encontrada[0]) if encontrada else None
                    if not fecha:
                        cur.execute("""
                            SELECT fecha_fin_sem FROM semanal_levante
                            WHERE lote = %s AND sem = %s
                        """, (lote, semana))
                        encontrada = cur.fetchone()
                        fecha = _fecha(encontrada[0]) if encontrada else None

                if campo == 'observaciones':
                    observaciones = (str(valor) if valor is not None else '')[:1000]
                else:
                    codigo, _, sub = campo.partition('.')
                    if not sub:
                        return {'ok': False, 'msg': 'Campo no válido.'}
                    if codigo == 'core':
                        if sub not in CORE_EDITABLES:
                            return {'ok': False, 'msg': 'Ese campo no es editable.'}
                        nodo = nutrientes.setdefault('_core', {})
                    else:
                        if sub not in SUBS_EDITABLES:
                            return {'ok': False, 'msg': 'Ese campo es una fórmula.'}
                        nodo = nutrientes.setdefault(codigo, {})
                    nodo[sub] = _num(valor)
                    TablaNutricional._recalcular(nutrientes)

                cur.execute("""
                    INSERT INTO tn_registros
                        (lote, semana, fecha, nutrientes, observaciones, archivo, actualizado_por)
                    VALUES (%s, %s, %s, %s, %s, 'edición manual', %s)
                    ON CONFLICT (lote, semana) DO UPDATE SET
                        fecha = COALESCE(EXCLUDED.fecha, tn_registros.fecha),
                        nutrientes = EXCLUDED.nutrientes,
                        observaciones = EXCLUDED.observaciones,
                        actualizado_por = EXCLUDED.actualizado_por,
                        actualizado_en = now()
                """, (lote, semana, fecha, Json(nutrientes), observaciones, usuario))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f'[ERROR GUARDAR TN]: {e}')
            return {'ok': False, 'msg': 'No se pudo guardar el cambio.'}
        finally:
            conn.close()

        for clave, dato in (nutrientes.get('_core') or {}).items():
            valores['core.' + clave] = dato
        for code, nodo in nutrientes.items():
            if code == '_core' or not isinstance(nodo, dict):
                continue
            for sub, dato in nodo.items():
                valores[f'{code}.{sub}'] = dato
        valores['observaciones'] = observaciones
        return {'ok': True, 'valores': valores}

    @staticmethod
    def datos_grafico(datos, codigo):
        """Series y KPIs del grafico seleccionado."""
        definicion = next((g for g in GRAFICOS if g['codigo'] == codigo), GRAFICOS[0])
        semanas = datos.get('semanas') or []
        tope = datos.get('semana_max')
        if tope:
            semanas = [s for s in semanas if s['semana'] <= tope]
        x = [s['semana'] for s in semanas]
        serie_actual = datos.get('semana_actual')

        if definicion.get('tipo') == 'core':
            peso = _serie_limpia([s.get('peso') for s in semanas])
            peso_tabla = _serie_limpia([s.get('peso_tabla') for s in semanas])
            consumo = _serie_limpia([s.get('consumo') for s in semanas])
            consumo_tabla = _serie_limpia([s.get('consumo_tabla') for s in semanas])
            series = [
                {'nombre': 'Peso real', 'y': peso, 'color': '#2c3e50', 'ancho': 2.4},
                {'nombre': 'Peso tabla', 'y': peso_tabla, 'color': '#9aa3b1', 'dash': 'dot'},
                {'nombre': 'Consumo real', 'y': consumo, 'color': '#2f6b3a', 'eje': 'y2', 'ancho': 2.4},
                {'nombre': 'Consumo tabla', 'y': consumo_tabla, 'color': '#9aa3b1', 'dash': 'dot', 'eje': 'y2'},
            ]
            kpis = [
                {'label': 'Peso actual', 'valor': _ultimo(peso), 'detalle': 'g'},
                {'label': 'Consumo actual', 'valor': _ultimo(consumo), 'detalle': 'g/ave/día'},
                {'label': 'Conversión actual',
                 'valor': _ultimo(_serie_limpia([s.get('conversion') for s in semanas])),
                 'detalle': ''},
            ]
            return {'codigo': definicion['codigo'], 'titulo': definicion['titulo'],
                    'unidad': 'Peso (g)', 'dual': True, 'x': x, 'series': series,
                    'kpis': kpis, 'semana_actual': serie_actual,
                    'criticas': list(SEMANAS_CRITICAS),
                    'y2_titulo': 'Consumo (g/ave/día)', 'nota': 'Doble eje: peso a la izquierda, consumo a la derecha.'}

        if definicion.get('tipo') == 'capr':
            calcio_guia, calcio_real = [], []
            fosf_guia, fosf_real = [], []
            rel_guia, rel_real = [], []
            gramos_ave, consumo1 = [], []
            for s in semanas:
                nodos = s.get('nutrientes') or {}
                calcio = nodos.get('calcio') or {}
                fosforo = nodos.get('fosforo') or {}
                relacion = nodos.get('rel_ca_p') or {}

                calcio_guia.append(_limpio(_num(calcio.get('tabla'))))
                calcio_real.append(_limpio(_num(calcio.get('real'))))
                rel_guia.append(_limpio(_num(relacion.get('tabla'))))
                rel_real.append(_limpio(_num(relacion.get('real'))))

                # El Excel grafica el fosforo x10 para que se vea en el eje 0-20
                fosf_tabla = _num(fosforo.get('tabla'))
                fosf_real_val = _num(fosforo.get('real'))
                fosf_guia.append(fosf_tabla * 10 if fosf_tabla else None)
                fosf_real.append(fosf_real_val * 10 if fosf_real_val else None)

                # Consumo: eje derecho, igual que el libro de Excel
                extras = s.get('extras') or {}
                gramos = _num(extras.get('gramos'))
                if gramos is None:
                    gramos = _num(s.get('consumo'))
                gramos_ave.append(_limpio(gramos))
                consumo1.append(_limpio(_num(extras.get('consumo1'))))

            series = [
                {'nombre': 'Relación tabla', 'y': rel_guia, 'color': '#c9a227', 'dash': 'dot'},
                {'nombre': 'Relación real', 'y': rel_real, 'color': '#97271C', 'ancho': 2.4},
                {'nombre': 'Calcio real', 'y': calcio_real, 'color': '#2c3e50', 'ancho': 2.4},
                {'nombre': 'Calcio tabla', 'y': calcio_guia, 'color': '#8fb8d9', 'dash': 'dot'},
                {'nombre': 'Fósforo real (×10)', 'y': fosf_real, 'color': '#2f6b3a', 'ancho': 2.4},
                {'nombre': 'Fósforo tabla (×10)', 'y': fosf_guia, 'color': '#93c9a8', 'dash': 'dot'},
                {'nombre': 'Gramos ave', 'y': gramos_ave, 'color': '#1f4e79', 'eje': 'y2', 'ancho': 2.0},
                {'nombre': 'Consumo 1', 'y': consumo1, 'color': '#4a90c2', 'eje': 'y2', 'ancho': 2.0},
            ]
            kpis = [
                {'label': 'Calcio real (último)', 'valor': _ultimo(calcio_real), 'detalle': 'g/ave/día'},
                {'label': 'Fósforo real (último)', 'valor': _ultimo(fosf_real) / 10 if _ultimo(fosf_real) else None, 'detalle': 'g/ave/día'},
                {'label': 'Relación Ca/P actual', 'valor': _ultimo(rel_real), 'detalle': 'Ca real / P real'},
            ]
            return {'codigo': definicion['codigo'], 'titulo': definicion['titulo'],
                    'unidad': 'gramos/ave/día', 'dual': True, 'x': x, 'series': series,
                    'kpis': kpis, 'semana_actual': serie_actual,
                    'criticas': list(SEMANAS_CRITICAS),
                    'y2_titulo': 'Consumo (g/ave/día)',
                    'y_rango': [0, 20], 'y_dtick': 2.2, 'y_formato': '.2f',
                    'y2_formato': '.0f',
                    'nota': 'Eje izquierdo: calcio, fósforo (×10) y relación Ca/P (0 a 20). Eje derecho: consumo.'}

        clave = definicion['nutriente']
        guia, pro, real, dif = [], [], [], []
        guia_sup = []
        for s in semanas:
            nodo = (s.get('nutrientes') or {}).get(clave) or {}
            valor_guia = nodo.get('tabla') if nodo.get('tabla') is not None else nodo.get('tabla_min')
            guia.append(None if valor_guia == 0 else valor_guia)
            guia_sup.append(None if nodo.get('tabla_sup') == 0 else nodo.get('tabla_sup'))
            pro.append(None if nodo.get('pro') == 0 else nodo.get('pro'))
            real.append(None if nodo.get('real') == 0 else nodo.get('real'))
            dif.append(nodo.get('dif'))

        series = []
        if clave == 'energia':
            series.append({'nombre': 'Tabla mín', 'y': guia, 'color': '#9aa3b1', 'dash': 'dot'})
            series.append({'nombre': 'Tabla máx', 'y': guia_sup, 'color': '#b6bdc8', 'dash': 'dash'})
        else:
            series.append({'nombre': 'Guía', 'y': guia, 'color': '#9aa3b1', 'dash': 'dot'})
        if any(v is not None for v in pro):
            series.append({'nombre': 'PRO', 'y': pro, 'color': '#c9a227', 'dash': 'dash'})
        series.append({'nombre': 'Real', 'y': real, 'color': '#97271C', 'ancho': 2.6})

        semana_ultima = next(
            (s['semana'] for s in reversed(semanas)
             if _limpio(((s.get('nutrientes') or {}).get(clave) or {}).get('real')) is not None),
            None,
        )
        kpis = [
            {'label': 'Real promedio', 'valor': _promedio(real), 'detalle': definicion['unidad']},
            {'label': 'Diferencia promedio', 'valor': _promedio(dif), 'detalle': 'vs. guía'},
            {'label': 'Última semana', 'valor': _ultimo(real),
             'detalle': f'semana {semana_ultima}' if semana_ultima else 'sin dato'},
        ]
        return {'codigo': definicion['codigo'], 'titulo': definicion['titulo'],
                'unidad': definicion['unidad'], 'dual': False, 'x': x, 'series': series,
                'kpis': kpis, 'semana_actual': serie_actual,
                'criticas': list(SEMANAS_CRITICAS)}

    # ------------------------------------------------------------------
    # Consulta unificada (Produccion + nutricion)
    # ------------------------------------------------------------------
    @staticmethod
    def lotes_disponibles():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.lote, COALESCE(e.nombre, '') AS empresa,
                           EXISTS (SELECT 1 FROM tn_registros t WHERE t.lote = c.lote) AS tiene_datos
                    FROM cabecera_lotes c
                    LEFT JOIN empresas e ON e.id = c.empresa_id
                    ORDER BY c.id DESC
                """)
                return [{'lote': f[0], 'empresa': f[1], 'tiene_datos': bool(f[2])}
                        for f in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def obtener_datos_lote(lote):
        if not lote:
            return None

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.lote, c.empresa_id, COALESCE(e.nombre, '') AS empresa,
                           c.granja_lev, c.granja_prod, c.responsable_tecnico,
                           c.nutricionista, c.nutricionista_prod,
                           c.tipo_galpon, c.variedad, c.marca_galpon,
                           c.fecha_recepcion, c.fecha_encasetamiento,
                           c.no_aves_encasetadas
                    FROM cabecera_lotes c
                    LEFT JOIN empresas e ON e.id = c.empresa_id
                    WHERE c.lote = %s
                    LIMIT 1
                """, (lote,))
                fila = cur.fetchone()
                if not fila:
                    return None
                columnas = [d[0] for d in cur.description]
                meta = dict(zip(columnas, fila))

                # Levante: semanas 1 a 17
                cur.execute("""
                    SELECT sem, fecha_fin_sem, peso_real, peso_tab,
                           cons_real, cons_tab, conv_sem, porc_mort_sem
                    FROM semanal_levante
                    WHERE lote = %s AND sem < 18
                    ORDER BY sem
                """, (lote,))
                levante = [dict(zip([d[0] for d in cur.description], f)) for f in cur.fetchall()]

                # Produccion: desde la semana 18
                cur.execute("""
                    SELECT sem_prod AS sem, fecha_fin_sem,
                           peso_ave_real, peso_ave_tab,
                           consumo_alim_real, consumo_alim_tab,
                           conv_sem_real, conv_sem_tab,
                           porcentaje_prod_real, porcentaje_prod_tb,
                           percent_mort_sem, precio_dieta, costo_huevo
                    FROM bd_vargas
                    WHERE lote = %s AND sem_prod >= 18
                    ORDER BY sem_prod
                """, (lote,))
                produccion = [dict(zip([d[0] for d in cur.description], f)) for f in cur.fetchall()]

                # Evaluacion nutricional importada
                cur.execute("""
                    SELECT semana, fecha, nutrientes, observaciones
                    FROM tn_registros
                    WHERE lote = %s
                    ORDER BY semana
                """, (lote,))
                nutricion = {f[0]: {'fecha': f[1], 'nutrientes': f[2] or {}, 'observaciones': f[3]}
                             for f in cur.fetchall()}

                try:
                    fotos = TablaNutricional._fotos_catalogo(meta, cur)
                except Exception as e:
                    print(f'[AVISO FOTOS TN]: {e}')
                    fotos = {}
        finally:
            conn.close()

        meta['foto_nutricionista'] = fotos.get('nutricionista')
        meta['foto_variedad'] = fotos.get('variedad')
        meta['foto_marca'] = fotos.get('marca')

        semanas = {}

        for f in levante:
            sem = int(f['sem'])
            semanas[sem] = {
                'semana': sem,
                'fecha': _fecha(f['fecha_fin_sem']),
                'peso': _num(f['peso_real']),
                'peso_tabla': _num(f['peso_tab']),
                'consumo': _num(f['cons_real']),
                'consumo_tabla': _num(f['cons_tab']),
                'conversion': _num(f['conv_sem']),
                'produccion': None,
                'produccion_tabla': None,
                'mortalidad': _num(f['porc_mort_sem']),
                'precio_dieta': None,
                'costo_huevo': None,
                'origen': 'levante',
            }

        for f in produccion:
            sem = int(f['sem'])
            semanas[sem] = {
                'semana': sem,
                'fecha': _fecha(f['fecha_fin_sem']),
                'peso': _num(f['peso_ave_real']),
                'peso_tabla': _num(f['peso_ave_tab']),
                'consumo': _num(f['consumo_alim_real']),
                'consumo_tabla': _num(f['consumo_alim_tab']),
                'conversion': _num(f['conv_sem_real']),
                'produccion': _num(f['porcentaje_prod_real']),
                'produccion_tabla': _num(f['porcentaje_prod_tb']),
                'mortalidad': _num(f['percent_mort_sem']),
                'precio_dieta': _num(f['precio_dieta']),
                'costo_huevo': _num(f['costo_huevo']),
                'origen': 'produccion',
            }

        for sem, datos in nutricion.items():
            if sem not in semanas:
                semanas[sem] = {
                    'semana': sem, 'fecha': None, 'peso': None, 'peso_tabla': None,
                    'consumo': None, 'consumo_tabla': None, 'conversion': None,
                    'produccion': None, 'produccion_tabla': None, 'mortalidad': None,
                    'precio_dieta': None, 'costo_huevo': None, 'origen': 'nutricion',
                }
            if not semanas[sem]['fecha']:
                semanas[sem]['fecha'] = datos['fecha']
            semanas[sem]['nutrientes'] = datos['nutrientes']
            semanas[sem]['observaciones'] = datos['observaciones']

        lista = []
        for sem in sorted(semanas):
            fila = semanas[sem]
            fila['etapa'] = etapa_de(sem)
            fila.setdefault('nutrientes', {})
            fila['extras'] = fila['nutrientes'].get('_core') or {}
            fila.setdefault('observaciones', '')

            # El Excel es la fuente de la tabla; Produccion es el respaldo
            for origen, destino in (('gramos', 'consumo'), ('conversion', 'conversion'),
                                    ('peso', 'peso'), ('produccion', 'produccion')):
                valor_excel = _num(fila['extras'].get(origen))
                if valor_excel is not None:
                    fila[destino] = valor_excel

            if fila.get('precio_dieta') is None:
                fila['precio_dieta'] = _num(fila['extras'].get('precio_formula'))
            if fila.get('costo_huevo') is None:
                fila['costo_huevo'] = _num(fila['extras'].get('costo_huevo'))

            # El Excel manda para las columnas $ Fórmula y $ Huevo; producción es el respaldo
            precio_excel = _num(fila['extras'].get('precio_formula'))
            costo_excel = _num(fila['extras'].get('costo_huevo'))
            fila['precio_formula'] = precio_excel if precio_excel is not None else fila.get('precio_dieta')
            fila['costo_huevo_mostrar'] = costo_excel if costo_excel is not None else fila.get('costo_huevo')
            if fila.get('consumo') is None:
                fila['consumo'] = _num(fila['extras'].get('gramos'))
            if fila.get('conversion') is None:
                fila['conversion'] = _num(fila['extras'].get('conversion'))
            if fila.get('peso') is None:
                fila['peso'] = _num(fila['extras'].get('peso'))
            if fila.get('produccion') is None:
                fila['produccion'] = _num(fila['extras'].get('produccion'))

            lista.append(fila)

        # Fusionar la etapa en un solo bloque por grupo de semanas
        i = 0
        while i < len(lista):
            j = i
            while j + 1 < len(lista) and lista[j + 1]['etapa'] == lista[i]['etapa']:
                j += 1
            lista[i]['etapa_rowspan'] = j - i + 1
            lista[i]['inicio_etapa'] = True
            lista[i]['etapa_cierra'] = True
            lista[j]['fin_etapa'] = True
            clase = ETAPA_CLASES.get(lista[i]['etapa'], 'pro')
            for k in range(i, j + 1):
                lista[k]['etapa_clase'] = clase
            for k in range(i + 1, j + 1):
                lista[k]['etapa_rowspan'] = 0
            i = j + 1

        # Semana vigente: primera semana cuya fecha de cierre es hoy o posterior
        hoy = date.today()
        semana_actual = None
        for fila in lista:
            if fila.get('fecha') and fila['fecha'] >= hoy:
                semana_actual = fila['semana']
                break
        for fila in lista:
            fila['es_actual'] = (fila['semana'] == semana_actual)

        # Ultima semana con informacion: nutricion importada o produccion
        con_datos = [
            f['semana'] for f in lista
            if f.get('nutrientes')
            or any(f.get(k) not in (None, 0) for k in ('consumo', 'peso', 'conversion', 'produccion'))
        ]
        semana_max = max(con_datos) if con_datos else (lista[-1]['semana'] if lista else None)

        # Precio de la dieta: ultimo valor registrado (el Excel lo deja vacio al final)
        precio_dieta_actual = None
        semana_precio = None
        for fila in reversed(lista):
            precio = _num(fila.get('precio_formula'))
            if precio:
                precio_dieta_actual = precio
                semana_precio = fila['semana']
                break

        meta['nutricionista_visible'] = meta.get('nutricionista_prod') or meta.get('nutricionista') or ''
        return {'lote': lote, 'meta': meta, 'semanas': lista,
                'semana_actual': semana_actual, 'semana_max': semana_max,
                'precio_dieta_actual': precio_dieta_actual,
                'semana_precio': semana_precio, 'hoy': hoy}

    # ------------------------------------------------------------------
    # Importacion del Excel
    # ------------------------------------------------------------------
    @staticmethod
    def importar_excel(datos, nombre_archivo, usuario):
        try:
            import openpyxl
        except ImportError:
            return {'ok': False, 'msg': 'Falta la librería openpyxl en el servidor.'}

        try:
            wb = openpyxl.load_workbook(io.BytesIO(datos), data_only=True, read_only=True)
        except Exception as e:
            return {'ok': False, 'msg': f'No se pudo abrir el archivo: {e}'}

        try:
            hoja = None
            for nombre in wb.sheetnames:
                if 'hy line' in _norm(nombre):
                    hoja = wb[nombre]
                    break
            if hoja is None:
                return {'ok': False, 'msg': 'El archivo no tiene la hoja "Hy line Brown".'}

            fila_encabezado = None
            for r in range(1, 41):
                valores = [_norm(hoja.cell(row=r, column=c).value) for c in range(1, 30)]
                tiene_fecha = 'fecha' in valores
                tiene_semana = any(v.startswith('semana') for v in valores)
                tiene_gramos = any(v.startswith('gramos') for v in valores)
                if tiene_fecha and tiene_semana and tiene_gramos:
                    fila_encabezado = r
                    break
            if not fila_encabezado:
                return {'ok': False, 'msg': 'No se encontró el encabezado de semanas.'}

            meta = TablaNutricional._leer_meta(hoja, fila_encabezado)
            columnas = TablaNutricional._mapa_columnas(hoja, fila_encabezado)
            if not columnas:
                return {'ok': False, 'msg': 'No se reconocieron las columnas del archivo.'}

            semanas = TablaNutricional._leer_semanas(hoja, fila_encabezado, columnas)
            if not semanas:
                return {'ok': False, 'msg': 'No se encontraron semanas con datos.'}

            lote, aviso = TablaNutricional._resolver_lote(meta, nombre_archivo)
            if not lote:
                return {'ok': False, 'msg': aviso or 'No se pudo detectar el lote en el archivo.'}

            guardadas = TablaNutricional._guardar(lote, semanas, nombre_archivo, usuario)
            return {'ok': True, 'lote': lote, 'semanas': guardadas, 'meta': meta, 'aviso': aviso}
        finally:
            wb.close()

    @staticmethod
    def _lote_existe(lote):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM cabecera_lotes WHERE lote = %s LIMIT 1", (lote,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def _resolver_lote(meta, nombre_archivo):
        """El nombre del archivo manda; el encabezado del Excel es el respaldo."""
        import re

        candidatos = []
        coincidencia = re.search(r'(\d{1,4}-\d{1,3})', nombre_archivo or '')
        if coincidencia:
            candidatos.append(coincidencia.group(1))

        lote_meta = str(meta.get('lote') or '').strip()
        if lote_meta:
            if '-' in lote_meta:
                candidatos.append(lote_meta)
            elif meta.get('galpon'):
                candidatos.append(f"{lote_meta}-{meta['galpon']}")
            candidatos.append(lote_meta)

        vistos = []
        for lote in candidatos:
            if lote and lote not in vistos:
                vistos.append(lote)
                if TablaNutricional._lote_existe(lote):
                    return lote, None

        if vistos:
            return None, (f'El lote detectado ({vistos[0]}) no existe en Gestión de lotes. '
                          'Créelo primero o revise el nombre del archivo.')
        return None, 'No se pudo detectar el lote en el archivo.'

    @staticmethod
    def _leer_meta(hoja, fila_encabezado):
        meta = {}
        etiquetas = {'empresa': 'empresa', 'granja': 'granja', 'lote': 'lote',
                     'nutricionista': 'nutricionista', 'galpon': 'galpon'}
        for r in range(1, fila_encabezado):
            for c in range(1, 12):
                valor = _norm(hoja.cell(row=r, column=c).value)
                if valor in etiquetas:
                    for c2 in range(c + 1, min(c + 4, 12)):
                        dato = hoja.cell(row=r, column=c2).value
                        if dato not in (None, ''):
                            meta[etiquetas[valor]] = str(dato).strip()
                            break
        return meta

    @staticmethod
    def _mapa_columnas(hoja, fila_encabezado):
        """Devuelve {'core': {...}, 'nutrientes': {codigo: [(sub, col), ...]}}."""
        columnas = {'core': {}, 'nutrientes': {}}
        grupo_actual = None
        max_col = hoja.max_column or 60

        for c in range(1, max_col + 1):
            titulo = hoja.cell(row=fila_encabezado, column=c).value
            if titulo not in (None, ''):
                grupo_actual = titulo
            sub = hoja.cell(row=fila_encabezado + 1, column=c).value
            norm_titulo = _norm(titulo)

            if norm_titulo == 'fecha':
                columnas['core']['fecha'] = c
            elif norm_titulo.startswith('semana'):
                columnas['core']['semana'] = c
            elif norm_titulo == 'gramos ave':
                columnas['core']['gramos'] = c
            elif norm_titulo == 'conversion':
                columnas['core']['conversion'] = c
            elif norm_titulo == 'peso ave':
                columnas['core']['peso'] = c
            elif norm_titulo.startswith('% prod'):
                columnas['core']['produccion'] = c
            elif norm_titulo.replace(' ', '').startswith('consumo1'):
                columnas['core']['consumo1'] = c
            elif norm_titulo.replace(' ', '').startswith('consumo2'):
                columnas['core']['consumo2'] = c
            elif norm_titulo.startswith('observaciones'):
                columnas['core']['observaciones'] = c
            elif 'precio formula' in norm_titulo:
                columnas['core']['precio_formula'] = c
            elif 'costo huevo' in norm_titulo:
                columnas['core']['costo_huevo'] = c

            codigo = _codigo_grupo(grupo_actual)
            subcodigo = _codigo_sub(sub)
            if codigo and subcodigo:
                columnas['nutrientes'].setdefault(codigo, []).append((subcodigo, c))

        return columnas if columnas['core'].get('semana') else None

    @staticmethod
    def _leer_semanas(hoja, fila_encabezado, columnas):
        semanas = []
        vacias = 0
        core = columnas['core']

        for r in range(fila_encabezado + 2, (hoja.max_row or 0) + 1):
            semana = hoja.cell(row=r, column=core['semana']).value
            fecha = hoja.cell(row=r, column=core.get('fecha', 0)).value if core.get('fecha') else None
            if semana in (None, ''):
                vacias += 1
                if vacias >= 3:
                    break
                continue
            try:
                semana = int(float(semana))
            except (TypeError, ValueError):
                vacias += 1
                if vacias >= 3:
                    break
                continue

            vacias = 0
            fila = {'semana': semana, 'fecha': _fecha(fecha), 'nutrientes': {}}

            extras = {}
            for clave in ('consumo1', 'consumo2', 'gramos', 'precio_formula',
                          'costo_huevo', 'conversion', 'peso', 'produccion'):
                if core.get(clave):
                    extras[clave] = _num(hoja.cell(row=r, column=core[clave]).value)

            # Algunos pesos vienen en kg (1.796) en lugar de gramos
            peso = extras.get('peso')
            if peso is not None and 0 < peso < 50:
                extras['peso'] = peso * 1000

            fila['nutrientes']['_core'] = extras

            for codigo, pares in columnas['nutrientes'].items():
                datos = {}
                for subcodigo, col in pares:
                    valor = _num(hoja.cell(row=r, column=col).value)
                    if subcodigo in datos:
                        if subcodigo == 'real':
                            subcodigo = 'real2'
                        else:
                            continue
                    datos[subcodigo] = valor
                fila['nutrientes'][codigo] = {
                    'tabla': (datos.get('tabla') if datos.get('tabla') is not None
                              else datos.get('tabla_min') if datos.get('tabla_min') is not None
                              else datos.get('eco')),
                    'real': datos.get('real'),
                    'dif': datos.get('dif'),
                    **{k: v for k, v in datos.items() if k not in ('tabla', 'real', 'dif')},
                }

            if core.get('observaciones'):
                obs = hoja.cell(row=r, column=core['observaciones']).value
                fila['observaciones'] = str(obs).strip() if obs not in (None, '') else ''

            semanas.append(fila)

        return semanas

    @staticmethod
    def _guardar(lote, semanas, nombre_archivo, usuario):
        conn = get_db_connection()
        guardadas = 0
        try:
            with conn.cursor() as cur:
                for fila in semanas:
                    cur.execute("""
                        INSERT INTO tn_registros
                            (lote, semana, fecha, nutrientes, observaciones, archivo, actualizado_por)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (lote, semana) DO UPDATE SET
                            fecha = EXCLUDED.fecha,
                            nutrientes = EXCLUDED.nutrientes,
                            observaciones = EXCLUDED.observaciones,
                            archivo = EXCLUDED.archivo,
                            actualizado_por = EXCLUDED.actualizado_por,
                            actualizado_en = now()
                    """, (
                        lote, fila['semana'], fila.get('fecha'),
                        Json(fila['nutrientes']),
                        fila.get('observaciones', ''),
                        (nombre_archivo or '')[:200],
                        usuario,
                    ))
                    guardadas += 1
            conn.commit()
            return guardadas
        except Exception as e:
            conn.rollback()
            print(f'[ERROR IMPORTANDO TABLA NUTRICIONAL]: {e}')
            raise
        finally:
            conn.close()
