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
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from models.gestion_ambiental import services
from models.gestion_ambiental.consultas import rango_historico
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
    """Portada: una tarjeta por sede activa."""
    conteos = {clave: len(indicadores_de_sede(clave)) for clave in SEDES}
    return render_template(
        'gestion_ambiental/inicio.html',
        sedes=SEDES,
        conteos=conteos,
    )


@gestion_ambiental_bp.route('/ga/<sede>')
@login_requerido
@gestion_ambiental_requerido
def temas(sede):
    """Temas disponibles en la sede (por ahora solo Parámetros del agua)."""
    sede_actual = (sede or '').strip().lower()
    if not _sede_valida(sede_actual):
        return redirect(url_for('gestion_ambiental.inicio'), code=302)

    conteos = {clave: len(indicadores_de_sede(clave)) for clave in SEDES}
    return render_template(
        'gestion_ambiental/temas.html',
        sedes=SEDES,
        sede=sede_actual,
        temas=TEMAS,
        indicadores=conteos[sede_actual],
    )


@gestion_ambiental_bp.route('/ga/<sede>/<tema>')
@gestion_ambiental_bp.route('/ga/<sede>/<tema>/<indicador>')
@login_requerido
@gestion_ambiental_requerido
def tablero(sede, tema, indicador=None):
    """Tablero de indicadores de la sede y tema seleccionados."""
    sede_actual = (sede or '').strip().lower()
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

    # --- Rango de fechas ---
    codigo_rango = request.args.get('r', RANGO_POR_DEFECTO)
    if codigo_rango not in RANGOS:
        codigo_rango = RANGO_POR_DEFECTO
    desde, hasta = _rango(codigo_rango, request.args.get('d', ''), request.args.get('h', ''))

    def url_vista(sede_, indicador_=None):
        """URL del tablero conservando el rango activo."""
        argumentos = {'sede': sede_, 'tema': TEMA_POR_DEFECTO, 'r': codigo_rango}
        if codigo_rango == 'p':
            if desde:
                argumentos['d'] = desde.strftime('%Y%m%d')
            if hasta:
                argumentos['h'] = hasta.strftime('%Y%m%d')
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
        'rango_texto': _texto_rango(desde, hasta),
        'url_vista': url_vista,
        'error': None,
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
        'tabla_detalle': services.registros_detalle(
            tablero_datos['kpi_foco'], sede_actual, desde, hasta,
        ),
        'export_data': services.datos_exportacion(
            tablero_datos,
            SEDES[sede_actual]['nombre'],
            contexto['rango_texto'],
        ),
        'historico': (tablero_datos['resumen']['primera_fecha'],
                      tablero_datos['resumen']['ultima_fecha']),
        'lista': lista,
    })
    return render_template('gestion_ambiental/tablero.html', **contexto)
