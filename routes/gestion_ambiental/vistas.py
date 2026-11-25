"""
Vistas del modulo de Gestion Ambiental.

Navegacion en tres niveles:
    /ga                         portada con las dos sedes
    /ga/<sede>                  temas de la sede
    /ga/<sede>/agua             tablero de indicadores (sidebar + grafico)

El modulo es de solo lectura: lee los indicadores migrados desde los
aplicativos de AppSheet (base `master_ga`).
"""

from datetime import date, timedelta
from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from models.gestion_ambiental import services
from models.gestion_ambiental.consultas import rango_historico
from models.gestion_ambiental.general import (
    LINEAS_GENERAL,
    SEDES_GENERAL,
    conteo_general,
    indicadores_de_submodulo,
    indicadores_general,
    submodulos_de,
)
from models.gestion_ambiental.general_services import (
    construir_tablero_general,
    datos_exportacion_general,
    registros_detalle_general,
    serie_para_grafico_general,
)
from models.gestion_ambiental.indicadores import (
    SEDES,
    indicadores_de_sede,
    obtener_indicador,
)
from routes.routes import login_requerido

gestion_ambiental_bp = Blueprint('gestion_ambiental', __name__)

ROLES_CON_ACCESO = ('Gestion Ambiental', 'Superadmin')

# Temas disponibles por sede. Por ahora solo agua; se ampliara cuando
# se migren los demas aplicativos.
TEMAS = {
    'agua': {
        'nombre': 'Parámetros del agua',
        'descripcion': 'Cloro, pH, hierro PTAP y análisis de laboratorio.',
        'icono': 'bx-water',
    },
}
TEMA_POR_DEFECTO = 'agua'

# Codigos cortos de rango para la URL.
RANGOS = {
    'h': 'Histórico',
    'a': 'Año actual',
    '12': 'Últimos 12 meses',
    'm': 'Mes actual',
    'p': 'Personalizado',
}
RANGO_POR_DEFECTO = 'h'


def gestion_ambiental_requerido(f):
    """Permite el acceso solo al rol Gestion Ambiental y a Superadmin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_rol') not in ROLES_CON_ACCESO:
            if request.path.startswith('/api/'):
                return {'status': 'error', 'msg': 'Acceso restringido.'}, 403
            flash('Acceso denegado. Esta área es exclusiva de Gestión Ambiental.', 'error')
            return redirect(url_for('main.pantalla_principal'))
        return f(*args, **kwargs)
    return decorated_function


def _fecha_compacta(texto):
    """Convierte AAAAMMDD o AAAA-MM-DD en date; None si no es valido."""
    if not texto:
        return None
    texto = texto.strip().replace('-', '')
    if len(texto) != 8 or not texto.isdigit():
        return None
    try:
        return date(int(texto[:4]), int(texto[4:6]), int(texto[6:]))
    except ValueError:
        return None


def _rango(codigo, desde_txt, hasta_txt):
    """Traduce el codigo de rango a un par (desde, hasta)."""
    hoy = date.today()
    if codigo == 'a':
        return date(hoy.year, 1, 1), None
    if codigo == '12':
        return hoy - timedelta(days=365), None
    if codigo == 'm':
        return date(hoy.year, hoy.month, 1), None
    if codigo == 'p':
        return _fecha_compacta(desde_txt), _fecha_compacta(hasta_txt)
    return None, None


def _texto_rango(desde, hasta):
    """Descripcion legible del rango activo."""
    if not desde and not hasta:
        return 'Desde el primer registro'
    if desde and hasta:
        return '%s a %s' % (services.formatear_fecha(desde), services.formatear_fecha(hasta))
    if desde:
        return 'Desde %s' % services.formatear_fecha(desde)
    return 'Hasta %s' % services.formatear_fecha(hasta)


def _filtro_fechas(args):
    """
    Lee los filtros de fecha (``d``, ``h``, ``anio``) y devuelve el rango.

    Se conserva el parametro antiguo ``r`` para que los enlaces anteriores
    sigan funcionando. Si se elige un año y las fechas caben dentro de él, el
    año actua como limite amplio y las fechas lo recortan; si las fechas
    quedan fuera, mandan las fechas y se descarta el año. Sin ningun filtro se
    usa el preset de ``r``.

    Devuelve (desde, hasta, anio, desde_param, hasta_param, codigo_rango).
    """
    hoy = date.today()
    desde_param = _fecha_compacta(args.get('d'))
    hasta_param = _fecha_compacta(args.get('h'))
    if desde_param and desde_param > hoy:
        desde_param = None
    if hasta_param and hasta_param > hoy:
        hasta_param = hoy
    if desde_param and hasta_param and desde_param > hasta_param:
        desde_param, hasta_param = hasta_param, desde_param

    anio = None
    texto_anio = (args.get('anio') or '').strip()
    if texto_anio.isdigit():
        valor = int(texto_anio)
        if 1900 <= valor <= hoy.year:
            anio = valor

    codigo = args.get('r', RANGO_POR_DEFECTO)
    if codigo not in RANGOS:
        codigo = RANGO_POR_DEFECTO

    desde, hasta = desde_param, hasta_param
    if anio:
        inicio = date(anio, 1, 1)
        fin = date(anio, 12, 31)
        fuera_del_anio = (
            (desde_param is not None and not inicio <= desde_param <= fin) or
            (hasta_param is not None and not inicio <= hasta_param <= fin)
        )
        if fuera_del_anio:
            # Las fechas explicitas no caben en el año elegido: mandan las
            # fechas y el selector de año vuelve a "Todos".
            anio = None
        else:
            desde = max(desde, inicio) if desde else inicio
            hasta = min(hasta, fin) if hasta else fin
    elif not desde and not hasta:
        desde, hasta = _rango(codigo, '', '')

    if hasta and hasta > hoy:
        hasta = hoy

    return desde, hasta, anio, desde_param, hasta_param, codigo


def _texto_filtro(desde, hasta, anio, desde_param, hasta_param):
    """Resumen legible del filtro: 'Año 2026', 'Año 2026 · 1 mar a 30 abr'..."""
    if anio and not desde_param and not hasta_param:
        return 'Año %d' % anio
    if anio:
        return 'Año %d · %s' % (anio, _texto_rango(desde, hasta))
    return _texto_rango(desde, hasta)


def _anios_filtro(primera, ultima):
    """Años seleccionables, del más reciente al más antiguo."""
    hoy = date.today()
    inicio = primera.year if primera else 2014
    fin = hoy.year
    if ultima and ultima.year > fin:
        fin = ultima.year
    return list(range(fin, inicio - 1, -1))


def _sede_valida(sede):
    return sede in SEDES and SEDES[sede]['activa']


@gestion_ambiental_bp.route('/gestion-ambiental')
@login_requerido
def tablero_largo():
    """Compatibilidad: la URL larga redirige a la portada."""
    return redirect(url_for('gestion_ambiental.inicio'), code=301)


@gestion_ambiental_bp.route('/ga')
@login_requerido
@gestion_ambiental_requerido
def inicio():
    """Portada: una tarjeta por sede y la tarjeta de General."""
    conteos = {clave: len(indicadores_de_sede(clave)) for clave in SEDES}
    temas_activos = sum(
        1 for linea in LINEAS_GENERAL.values()
        for tema in linea['temas'].values() if tema['activo']
    )
    temas_total = sum(len(linea['temas']) for linea in LINEAS_GENERAL.values())
    return render_template(
        'gestion_ambiental/inicio.html',
        sedes=SEDES,
        conteos=conteos,
        lineas_general=LINEAS_GENERAL,
        general_temas_activos=temas_activos,
        general_temas_total=temas_total,
    )


@gestion_ambiental_bp.route('/ga/<sede>')
@login_requerido
@gestion_ambiental_requerido
def temas(sede):
    """Temas disponibles en la sede (por ahora solo Parámetros del agua)."""
    sede_actual = (sede or '').strip().lower()
    if sede_actual == 'general':
        return redirect(url_for('gestion_ambiental.general_lineas'), code=302)
    if not _sede_valida(sede_actual):
        return redirect(url_for('gestion_ambiental.inicio'), code=302)

    conteos = {clave: len(indicadores_de_sede(clave)) for clave in SEDES}
    return render_template(
        'gestion_ambiental/temas.html',
        sedes=SEDES,
        sede=sede_actual,
        temas=TEMAS,
        indicadores=conteos[sede_actual],
        migas=_migas(
            ('Módulos', url_for('gestion_ambiental.inicio')),
            (SEDES[sede_actual]['nombre'], None),
        ),
    )


def _migas(*partes):
    """Arma las migas de pan: cada parte es (nombre, url) o (nombre, None)."""
    return [{'nombre': nombre, 'url': url} for nombre, url in partes]


def _prefijo_valido(linea, tema, partes):
    """Indica si una ruta de submódulos existe igual en la otra línea."""
    if not partes:
        return False
    actuales = submodulos_de(linea, tema)
    if not actuales:
        return False
    for parte in partes:
        encontrado = next((s for s in actuales if s['clave'] == parte), None)
        if not encontrado:
            return False
        actuales = encontrado.get('hijos') or []
    return True


def _url_linea_destino(linea_destino, tema, prefijo=None):
    """
    URL para cambiar de línea conservando tema y submódulo cuando existen.

    Si la línea destino no tiene el tema, se abre su listado de temas.
    """
    info = LINEAS_GENERAL.get(linea_destino)
    if not info:
        return url_for('gestion_ambiental.general_lineas')

    tema_info = info['temas'].get(tema)
    if tema_info and tema_info['activo']:
        argumentos = {'linea': linea_destino, 'tema': tema}
        if prefijo and _prefijo_valido(linea_destino, tema, prefijo):
            argumentos['resto'] = '/'.join(prefijo)
        return url_for('gestion_ambiental.general_tablero', **argumentos)

    return url_for('gestion_ambiental.general_temas', linea=linea_destino)


@gestion_ambiental_bp.route('/ga/general')
@login_requerido
@gestion_ambiental_requerido
def general_lineas():
    """Portada de General: Producción (Vargas) y Levante (Lourdes)."""
    return render_template(
        'gestion_ambiental/general_lineas.html',
        lineas=LINEAS_GENERAL,
        migas=_migas(
            ('Módulos', url_for('gestion_ambiental.inicio')),
            ('General', None),
        ),
    )


@gestion_ambiental_bp.route('/ga/general/<linea>')
@login_requerido
@gestion_ambiental_requerido
def general_temas(linea):
    """Temas de la línea de General seleccionada."""
    linea_actual = (linea or '').strip().lower()
    if linea_actual not in LINEAS_GENERAL:
        return redirect(url_for('gestion_ambiental.general_lineas'), code=302)

    info = LINEAS_GENERAL[linea_actual]
    etiquetas = {}
    for clave, tema in info['temas'].items():
        if not tema['activo']:
            etiquetas[clave] = 'En construcción'
        elif submodulos_de(linea_actual, clave):
            etiquetas[clave] = '%d módulos' % len(submodulos_de(linea_actual, clave))
        else:
            n_ind = conteo_general(linea_actual, clave)
            etiquetas[clave] = '%d indicador%s' % (n_ind, '' if n_ind == 1 else 'es')

    return render_template(
        'gestion_ambiental/general_temas.html',
        lineas=LINEAS_GENERAL,
        linea=info,
        linea_slug=linea_actual,
        temas=info['temas'],
        etiquetas=etiquetas,
        migas=_migas(
            ('Módulos', url_for('gestion_ambiental.inicio')),
            ('General', url_for('gestion_ambiental.general_lineas')),
            (info['nombre'], None),
        ),
        urls_lineas={
            clave: url_for('gestion_ambiental.general_temas', linea=clave)
            for clave in LINEAS_GENERAL
        },
    )


@gestion_ambiental_bp.route('/ga/general/<linea>/<tema>')
@gestion_ambiental_bp.route('/ga/general/<linea>/<tema>/<path:resto>')
@login_requerido
@gestion_ambiental_requerido
def general_tablero(linea, tema, resto=''):
    """
    Tema de General: submódulos, tablero o indicador concreto.

    La ruta admite varios niveles: /agua (submódulos), /agua/in-situ
    (módulos hijos), /agua/in-situ/ph (tablero) y
    /agua/laboratorio/g_turbiedad (indicador dentro de un tablero).
    """
    linea_actual = (linea or '').strip().lower()
    if linea_actual not in LINEAS_GENERAL:
        return redirect(url_for('gestion_ambiental.general_lineas'), code=302)

    info_linea = LINEAS_GENERAL[linea_actual]
    tema_actual = (tema or '').strip().lower()
    if tema_actual not in info_linea['temas']:
        return redirect(url_for('gestion_ambiental.general_temas',
                                linea=linea_actual), code=302)
    if not info_linea['temas'][tema_actual]['activo']:
        flash('Este tema de General estará disponible próximamente.', 'info')
        return redirect(url_for('gestion_ambiental.general_temas',
                                linea=linea_actual), code=302)

    sede_filtro = info_linea['sede']
    partes = [p for p in (resto or '').split('/') if p]
    submodulos = submodulos_de(linea_actual, tema_actual)
    seccion = None
    hijo = None

    def url_pagina(ruta=None):
        """URL de una página del tema (sin rango)."""
        argumentos = {'linea': linea_actual, 'tema': tema_actual}
        if ruta:
            argumentos['resto'] = '/'.join(ruta)
        return url_for('gestion_ambiental.general_tablero', **argumentos)

    def tarjetas(items, prefijo=None):
        """Copia los submódulos con su URL y el conteo que muestra la tarjeta."""
        salida = []
        for item in items:
            copia = dict(item)
            copia['url'] = url_pagina(
                ([prefijo] if prefijo else []) + [item['clave']])
            if item.get('hijos'):
                n_hijos = len(item['hijos'])
                copia['meta'] = '%d módulo%s' % (n_hijos, '' if n_hijos == 1 else 's')
            else:
                n_ind = len(indicadores_de_submodulo(linea_actual, item, tema_actual))
                copia['meta'] = '%d indicador%s' % (n_ind, '' if n_ind == 1 else 'es')
            salida.append(copia)
        return salida

    # --- Página de submódulos (solo para temas con estructura propia) ---
    if submodulos:
        if not partes:
            tema_info = info_linea['temas'][tema_actual]
            return render_template(
                'gestion_ambiental/general_secciones.html',
                linea=info_linea,
                linea_slug=linea_actual,
                tema=tema_info,
                tema_slug=tema_actual,
                titulo=tema_info['nombre'],
                subtitulo=tema_info['descripcion'],
                icono=tema_info['icono'],
                migas=_migas(
                    ('Módulos', url_for('gestion_ambiental.inicio')),
                    ('General', url_for('gestion_ambiental.general_lineas')),
                    (info_linea['nombre'],
                     url_for('gestion_ambiental.general_temas', linea=linea_actual)),
                    (tema_info['nombre'], None),
                ),
                volver_url=url_for('gestion_ambiental.general_temas', linea=linea_actual),
                volver_texto=info_linea['nombre'],
                tarjetas=tarjetas(submodulos),
                lineas=LINEAS_GENERAL,
                urls_lineas={
                    clave: _url_linea_destino(clave, tema_actual)
                    for clave in LINEAS_GENERAL
                },
            )

        seccion = next((s for s in submodulos if s['clave'] == partes[0]), None)
        if not seccion:
            return redirect(url_pagina(), code=302)

        if seccion.get('hijos'):
            if len(partes) == 1:
                return render_template(
                    'gestion_ambiental/general_secciones.html',
                    linea=info_linea,
                    linea_slug=linea_actual,
                    tema=info_linea['temas'][tema_actual],
                    tema_slug=tema_actual,
                    titulo=seccion['nombre'],
                    subtitulo=seccion.get('descripcion', ''),
                    icono=seccion.get('icono', 'bx-grid-alt'),
                    migas=_migas(
                        ('Módulos', url_for('gestion_ambiental.inicio')),
                        ('General', url_for('gestion_ambiental.general_lineas')),
                        (info_linea['nombre'],
                         url_for('gestion_ambiental.general_temas', linea=linea_actual)),
                        (info_linea['temas'][tema_actual]['nombre'], url_pagina()),
                        (seccion['nombre'], None),
                    ),
                    volver_url=url_pagina(),
                    volver_texto=info_linea['temas'][tema_actual]['nombre'],
                    tarjetas=tarjetas(seccion['hijos'], prefijo=seccion['clave']),
                    lineas=LINEAS_GENERAL,
                    urls_lineas={
                        clave: _url_linea_destino(
                            clave, tema_actual, [seccion['clave']])
                        for clave in LINEAS_GENERAL
                    },
                )

            hijo = next((h for h in seccion['hijos'] if h['clave'] == partes[1]), None)
            if not hijo:
                return redirect(url_pagina([seccion['clave']]), code=302)

            prefijo = [seccion['clave'], hijo['clave']]
            lista = indicadores_de_submodulo(linea_actual, hijo, tema_actual)
            titulo = hijo['nombre']
            icono = hijo.get('icono') or seccion.get('icono') or 'bx-grid-alt'
            volver_url = url_pagina([seccion['clave']])
            volver_texto = seccion['nombre']
            indicador = partes[2] if len(partes) > 2 else None
        else:
            prefijo = [seccion['clave']]
            lista = indicadores_de_submodulo(linea_actual, seccion, tema_actual)
            titulo = seccion['nombre']
            icono = seccion.get('icono', 'bx-grid-alt')
            volver_url = url_pagina()
            volver_texto = info_linea['temas'][tema_actual]['nombre']
            indicador = partes[1] if len(partes) > 1 else None
    else:
        prefijo = []
        lista = indicadores_general(linea_actual, tema_actual)
        titulo = info_linea['temas'][tema_actual]['nombre']
        icono = info_linea['temas'][tema_actual]['icono']
        volver_url = url_for('gestion_ambiental.general_temas', linea=linea_actual)
        volver_texto = info_linea['nombre']
        indicador = partes[0] if partes else None

    disponibles = {i['id'] for i in lista}
    ind_foco = None
    if indicador:
        ind_foco = next(
            (i for i in lista if i['id'] == indicador.strip().lower()), None)
        if not ind_foco or ind_foco['id'] not in disponibles:
            return redirect(url_pagina(prefijo), code=302)

    desde, hasta, anio_sel, desde_param, hasta_param, codigo_rango = _filtro_fechas(
        request.args)

    def url_general(indicador_=None):
        """URL del tablero conservando la ruta y los filtros activos."""
        ruta = list(prefijo)
        if indicador_:
            ruta.append(indicador_)
        argumentos = {
            'linea': linea_actual,
            'tema': tema_actual,
        }
        if ruta:
            argumentos['resto'] = '/'.join(ruta)
        if anio_sel:
            argumentos['anio'] = anio_sel
        if desde_param:
            argumentos['d'] = desde_param.isoformat()
        if hasta_param:
            argumentos['h'] = hasta_param.isoformat()
        if (not anio_sel and not desde_param and not hasta_param
                and codigo_rango != RANGO_POR_DEFECTO):
            argumentos['r'] = codigo_rango
        return url_for('gestion_ambiental.general_tablero', **argumentos)

    migas = _migas(
        ('Módulos', url_for('gestion_ambiental.inicio')),
        ('General', url_for('gestion_ambiental.general_lineas')),
        (info_linea['nombre'],
         url_for('gestion_ambiental.general_temas', linea=linea_actual)),
    )
    if submodulos:
        migas.append({
            'nombre': info_linea['temas'][tema_actual]['nombre'],
            'url': url_pagina(),
        })
        if seccion:
            if hijo:
                migas.append({
                    'nombre': seccion['nombre'],
                    'url': url_pagina([seccion['clave']]),
                })
                migas.append({'nombre': hijo['nombre'], 'url': None})
            else:
                migas.append({'nombre': seccion['nombre'], 'url': None})
    else:
        migas.append({
            'nombre': info_linea['temas'][tema_actual]['nombre'],
            'url': None,
        })

    contexto = {
        'sedes_general': SEDES_GENERAL,
        'sede_general': sede_filtro,
        'linea': info_linea,
        'linea_slug': linea_actual,
        'tema': info_linea['temas'][tema_actual],
        'tema_slug': tema_actual,
        'titulo': titulo,
        'icono': icono,
        'migas': migas,
        'lineas': LINEAS_GENERAL,
        'urls_lineas': {
            clave: _url_linea_destino(clave, tema_actual, prefijo)
            for clave in LINEAS_GENERAL
        },
        'volver_url': volver_url,
        'volver_texto': volver_texto,
        'rangos': RANGOS,
        'rango': codigo_rango,
        'desde_iso': desde.isoformat() if desde else '',
        'hasta_iso': hasta.isoformat() if hasta else '',
        'desde_form': desde_param.isoformat() if desde_param else '',
        'hasta_form': hasta_param.isoformat() if hasta_param else '',
        'anio_sel': anio_sel,
        'anios': [],
        'hoy_iso': date.today().isoformat(),
        'filtros_activos': bool(anio_sel or desde_param or hasta_param),
        'rango_texto': _texto_filtro(
            desde, hasta, anio_sel, desde_param, hasta_param),
        'url_general': url_general,
        'url_actual': url_general(ind_foco['id'] if ind_foco else None),
        'error': None,
    }

    try:
        tablero_datos = construir_tablero_general(
            linea=linea_actual, tema=tema_actual, desde=desde, hasta=hasta,
            indicador_id=ind_foco['id'] if ind_foco else None,
            indicadores=lista,
        )
    except Exception as error:
        print('[GESTION AMBIENTAL] Error al consultar General: %s' % error)
        contexto['error'] = (
            'No fue posible consultar los indicadores de General. '
            'Verifica la conexión e inténtalo de nuevo.'
        )
        contexto.update({
            'kpi_foco': None,
            'secciones': [],
            'resumen': None,
            'grafico': None,
            'tabla_detalle': {'columnas': [], 'filas': []},
            'export_data': None,
            'historico': (None, None),
        })
        return render_template('gestion_ambiental/general_tablero.html', **contexto), 503

    if not tablero_datos['kpi_foco']:
        return redirect(url_pagina(prefijo), code=302)

    formato = (request.args.get('formato') or '').strip().lower()
    if formato == 'tabla':
        return jsonify(registros_detalle_general(
            tablero_datos['kpi_foco'], sede_filtro, desde, hasta))
    if formato == 'export':
        lista_kpis = [kpi for seccion in tablero_datos['secciones']
                      for kpi in seccion['indicadores']]
        export_data = datos_exportacion_general(
            tablero_datos['kpi_foco'], lista_kpis, sede_filtro,
            contexto['rango_texto'],
            etiqueta='General - %s' % info_linea['nombre'],
        )
        export_data['tabla'] = registros_detalle_general(
            tablero_datos['kpi_foco'], sede_filtro, desde, hasta)
        return jsonify(export_data)

    # Histórico completo también en General, para poder cambiar de año.
    contexto['anios'] = _anios_filtro(None, None)

    grafico = serie_para_grafico_general(tablero_datos['kpi_foco'], sede_filtro)
    grafico['opcionales'] = services.opcionales_para_grafico(
        tablero_datos['kpi_foco']['indicador'],
        sede_filtro,
        desde,
        hasta,
        grafico['fechas'],
    )

    contexto.update({
        'kpi_foco': tablero_datos['kpi_foco'],
        'resumen': tablero_datos['resumen'],
        'secciones': tablero_datos['secciones'],
        'grafico': grafico,
        'historico': (tablero_datos['resumen']['primera_fecha'],
                      tablero_datos['resumen']['ultima_fecha']),
    })
    return render_template('gestion_ambiental/general_tablero.html', **contexto)


@gestion_ambiental_bp.route('/ga/<sede>/<tema>')
@gestion_ambiental_bp.route('/ga/<sede>/<tema>/<indicador>')
@login_requerido
@gestion_ambiental_requerido
def tablero(sede, tema, indicador=None):
    """Tablero de indicadores de la sede y tema seleccionados."""
    sede_actual = (sede or '').strip().lower()
    if sede_actual == 'general':
        return redirect(url_for('gestion_ambiental.general_lineas'), code=302)
    if not _sede_valida(sede_actual):
        return redirect(url_for('gestion_ambiental.inicio'), code=302)

    tema_actual = (tema or '').strip().lower()

    # Compatibilidad con las URL anteriores (/ga/<sede>/<grupo>/<indicador>).
    if tema_actual in ('todo', 'diario', 'lab'):
        return redirect(
            url_for('gestion_ambiental.tablero', sede=sede_actual,
                    tema=TEMA_POR_DEFECTO, indicador=indicador),
            code=301,
        )

    if tema_actual not in TEMAS:
        return redirect(url_for('gestion_ambiental.temas', sede=sede_actual), code=302)

    # --- Indicador: debe existir y pertenecer a la sede ---
    ind_foco = None
    if indicador:
        ind_foco = obtener_indicador(indicador.strip().lower())
        if not ind_foco or sede_actual not in ind_foco.get('sedes', ('lourdes', 'vargas')):
            return redirect(
                url_for('gestion_ambiental.tablero', sede=sede_actual, tema=tema_actual),
                code=302,
            )

    # --- Filtros de fecha ---
    desde, hasta, anio_sel, desde_param, hasta_param, codigo_rango = _filtro_fechas(
        request.args)

    def url_vista(sede_, indicador_=None):
        """URL del tablero conservando los filtros activos."""
        argumentos = {'sede': sede_, 'tema': TEMA_POR_DEFECTO}
        if anio_sel:
            argumentos['anio'] = anio_sel
        if desde_param:
            argumentos['d'] = desde_param.isoformat()
        if hasta_param:
            argumentos['h'] = hasta_param.isoformat()
        if (not anio_sel and not desde_param and not hasta_param
                and codigo_rango != RANGO_POR_DEFECTO):
            argumentos['r'] = codigo_rango
        if indicador_:
            argumentos['indicador'] = indicador_
        return url_for('gestion_ambiental.tablero', **argumentos)

    contexto = {
        'sedes': SEDES,
        'sede': sede_actual,
        'tema': TEMAS[tema_actual],
        'tema_slug': tema_actual,
        'temas': TEMAS,
        'rangos': RANGOS,
        'rango': codigo_rango,
        'desde_iso': desde.isoformat() if desde else '',
        'hasta_iso': hasta.isoformat() if hasta else '',
        'desde_form': desde_param.isoformat() if desde_param else '',
        'hasta_form': hasta_param.isoformat() if hasta_param else '',
        'anio_sel': anio_sel,
        'anios': [],
        'hoy_iso': date.today().isoformat(),
        'filtros_activos': bool(anio_sel or desde_param or hasta_param),
        'rango_texto': _texto_filtro(
            desde, hasta, anio_sel, desde_param, hasta_param),
        'url_vista': url_vista,
        'error': None,
        'migas': _migas(
            ('Módulos', url_for('gestion_ambiental.inicio')),
            (SEDES[sede_actual]['nombre'],
             url_for('gestion_ambiental.temas', sede=sede_actual)),
            (TEMAS[tema_actual]['nombre'], None),
        ),
    }

    try:
        tablero_datos = services.construir_tablero(
            sede_actual, desde=desde, hasta=hasta,
            grupo='resumen',
            indicador_id=ind_foco['id'] if ind_foco else None,
        )
    except Exception as error:
        print('[GESTION AMBIENTAL] Error al consultar master_ga: %s' % error)
        contexto['error'] = (
            'No fue posible consultar la base de datos ambiental. '
            'Verifica la conexión e inténtalo de nuevo.'
        )
        contexto.update({
            'kpi_foco': None,
            'lista': [],
            'resumen': None,
            'grafico': None,
            'tabla_detalle': {'columnas': [], 'filas': []},
            'export_data': None,
            'historico': (None, None),
        })
        return render_template('gestion_ambiental/tablero.html', **contexto), 503

    # El selector de año debe ofrecer todo el histórico, no solo los años que
    # quedan dentro del filtro activo (si no, no se podria cambiar de año).
    contexto['anios'] = _anios_filtro(None, None)

    formato = (request.args.get('formato') or '').strip().lower()
    if formato == 'tabla':
        return jsonify(services.registros_detalle(
            tablero_datos['kpi_foco'], sede_actual, desde, hasta))
    if formato == 'export':
        export_data = services.datos_exportacion(
            tablero_datos,
            SEDES[sede_actual]['nombre'],
            contexto['rango_texto'],
        )
        export_data['tabla'] = services.registros_detalle(
            tablero_datos['kpi_foco'], sede_actual, desde, hasta)
        return jsonify(export_data)

    # Lista plana para la barra lateral: todos los indicadores de la sede.
    lista = []
    for ind in indicadores_de_sede(sede_actual):
        kpi = tablero_datos['kpis'].get(ind['id'])
        if not kpi:
            continue
        lista.append({
            'id': ind['id'],
            'nombre': ind['nombre'],
            'unidad': ind['unidad'],
            'estado': kpi['estado'],
            'ultimo_txt': kpi['ultimo_txt'],
        })

    grafico = services.serie_para_grafico(tablero_datos['kpi_foco'])
    grafico['opcionales'] = services.opcionales_para_grafico(
        tablero_datos['kpi_foco']['indicador'],
        sede_actual,
        desde,
        hasta,
        grafico['fechas'],
    )

    contexto.update({
        'kpi_foco': tablero_datos['kpi_foco'],
        'resumen': tablero_datos['resumen'],
        'grafico': grafico,
        'historico': (tablero_datos['resumen']['primera_fecha'],
                      tablero_datos['resumen']['ultima_fecha']),
        'lista': lista,
    })
    return render_template('gestion_ambiental/tablero.html', **contexto)
