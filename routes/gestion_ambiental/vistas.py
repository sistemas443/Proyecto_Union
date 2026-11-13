"""
Vistas del modulo de Gestion Ambiental.

El modulo es de solo lectura: lee los indicadores migrados desde los
aplicativos de AppSheet (base `master_ga`) y los presenta en un tablero.

Las URL son cortas y validadas contra listas blancas:
    /ga/<sede>/<grupo>/<indicador>?r=<rango>&d=<desde>&h=<hasta>

    sede      lourdes | vargas
    grupo     todo | diario | lab
    indicador id del catalogo (ej. nitratos)
    rango     h (historico) | a (ano actual) | 12 (12 meses) | m (mes) | p
    d, h      fechas compactas AAAAMMDD, solo con rango p
"""

from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from models.gestion_ambiental import services
from models.gestion_ambiental.consultas import rango_historico
from models.gestion_ambiental.indicadores import (
    GRUPO_A_SLUG,
    GRUPO_POR_DEFECTO,
    GRUPOS,
    SEDE_POR_DEFECTO,
    SEDES,
    SLUG_A_GRUPO,
    indicadores_del_grupo,
    obtener_indicador,
)
from routes.routes import login_requerido

gestion_ambiental_bp = Blueprint('gestion_ambiental', __name__)

ROLES_CON_ACCESO = ('Gestion Ambiental', 'Superadmin')

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


@gestion_ambiental_bp.route('/gestion-ambiental')
@login_requerido
def tablero_largo():
    """Compatibilidad: la URL larga redirige a la corta."""
    return redirect(url_for('gestion_ambiental.tablero'), code=301)


@gestion_ambiental_bp.route('/ga')
@gestion_ambiental_bp.route('/ga/<sede>')
@gestion_ambiental_bp.route('/ga/<sede>/<grupo>')
@gestion_ambiental_bp.route('/ga/<sede>/<grupo>/<indicador>')
@login_requerido
@gestion_ambiental_requerido
def tablero(sede=None, grupo=None, indicador=None):
    """Tablero de indicadores ambientales de la sede seleccionada."""
    # --- Sede: solo slugs conocidos y activos ---
    sede_actual = (sede or SEDE_POR_DEFECTO).strip().lower()
    if sede_actual not in SEDES or not SEDES[sede_actual]['activa']:
        return redirect(url_for('gestion_ambiental.tablero'), code=302)

    # --- Grupo: slug corto a nombre interno ---
    grupo_actual = SLUG_A_GRUPO.get((grupo or 'todo').strip().lower())
    if not grupo_actual:
        return redirect(url_for('gestion_ambiental.tablero', sede=sede_actual), code=302)

    # --- Indicador: debe existir en el catalogo ---
    ind_foco = None
    if indicador:
        ind_foco = obtener_indicador(indicador.strip().lower())
        if not ind_foco:
            return redirect(
                url_for('gestion_ambiental.tablero', sede=sede_actual,
                        grupo=GRUPO_A_SLUG[grupo_actual]),
                code=302,
            )
        if sede_actual not in ind_foco.get('sedes', ('lourdes', 'vargas')):
            return redirect(
                url_for('gestion_ambiental.tablero', sede=sede_actual,
                        grupo=GRUPO_A_SLUG[grupo_actual]),
                code=302,
            )
        # Si el indicador pertenece a otro grupo, se corrige la URL
        if grupo_actual not in ('resumen', ind_foco['grupo']):
            return redirect(
                url_for('gestion_ambiental.tablero', sede=sede_actual,
                        grupo=GRUPO_A_SLUG[ind_foco['grupo']], indicador=ind_foco['id']),
                code=302,
            )

    # --- Rango de fechas ---
    codigo_rango = request.args.get('r', RANGO_POR_DEFECTO)
    if codigo_rango not in RANGOS:
        codigo_rango = RANGO_POR_DEFECTO
    desde_txt = request.args.get('d', '')
    hasta_txt = request.args.get('h', '')
    desde, hasta = _rango(codigo_rango, desde_txt, hasta_txt)

    grupo_slug = GRUPO_A_SLUG[grupo_actual]

    def url_vista(sede_, grupo_, indicador_):
        """URL corta conservando el rango activo."""
        argumentos = {'sede': sede_, 'r': codigo_rango}
        if codigo_rango == 'p':
            if desde:
                argumentos['d'] = desde.strftime('%Y%m%d')
            if hasta:
                argumentos['h'] = hasta.strftime('%Y%m%d')
        if grupo_:
            argumentos['grupo'] = grupo_
        if indicador_:
            argumentos['indicador'] = indicador_
        return url_for('gestion_ambiental.tablero', **argumentos)

    def url_indicador(kpi):
        """URL del indicador en su grupo real (o en Resumen si estamos ahí)."""
        if grupo_actual == 'resumen':
            slug = 'todo'
        else:
            slug = GRUPO_A_SLUG[kpi['indicador']['grupo']]
        return url_vista(sede_actual, slug, kpi['indicador']['id'])

    contexto = {
        'sedes': SEDES,
        'sede': sede_actual,
        'grupo_slug': grupo_slug,
        'grupos': GRUPOS,
        'rangos': RANGOS,
        'rango': codigo_rango,
        'desde_txt': desde.strftime('%Y%m%d') if desde else '',
        'hasta_txt': hasta.strftime('%Y%m%d') if hasta else '',
        'desde_iso': desde.isoformat() if desde else '',
        'hasta_iso': hasta.isoformat() if hasta else '',
        'rango_texto': _texto_rango(desde, hasta),
        'url_vista': url_vista,
        'url_indicador': url_indicador,
        'error': None,
    }

    try:
        tablero_datos = services.construir_tablero(
            sede_actual, desde=desde, hasta=hasta,
            grupo=grupo_actual,
            indicador_id=ind_foco['id'] if ind_foco else None,
        )
    except Exception as error:
        print('[GESTION AMBIENTAL] Error al consultar master_ga: %s' % error)
        contexto['error'] = (
            'No fue posible consultar la base de datos ambiental. '
            'Verifica la conexión e inténtalo de nuevo.'
        )
        contexto.update({
            'grupo_actual': grupo_actual,
            'kpi_foco': None,
            'grupos_datos': {'diario': [], 'laboratorio': []},
            'resumen': None,
            'grafico': None,
            'registros': [],
            'export_data': None,
            'historico': (None, None),
        })
        return render_template('gestion_ambiental/tablero.html', **contexto), 503

    grafico = services.serie_para_grafico(tablero_datos['kpi_foco'])
    grafico['opcionales'] = services.opcionales_para_grafico(
        tablero_datos['kpi_foco']['indicador'],
        sede_actual,
        desde,
        hasta,
        grafico['fechas'],
    )

    contexto.update({
        'grupo_actual': tablero_datos['grupo_actual'],
        'grupos_datos': tablero_datos['grupos'],
        'kpi_foco': tablero_datos['kpi_foco'],
        'resumen': tablero_datos['resumen'],
        'grafico': grafico,
        'registros': services.registros_tabla(tablero_datos['kpi_foco']),
        'export_data': services.datos_exportacion(
            tablero_datos,
            SEDES[sede_actual]['nombre'],
            contexto['rango_texto'],
        ),
        'historico': rango_historico(sede_actual),
    })
    return render_template('gestion_ambiental/tablero.html', **contexto)
