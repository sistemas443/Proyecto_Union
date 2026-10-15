from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.primera_semana.services import get_primera_semana_by_lote, get_data_grafico_primera_semana
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos
from models.catalogos import model as catalogos_model, services as catalogos_services
from models.catalogos.schemas import obtener_tabla

primera_semana_bp = Blueprint('primera_semana', __name__)


def _foto_catalogo(tipo: str, nombre):
    """Busca la foto de un valor en su catálogo.
    Devuelve (nombre_mostrado, foto_url) con fallback al placeholder."""
    tabla = obtener_tabla(tipo)
    nombre_limpio = (nombre or '').strip()
    item = catalogos_model.buscar_por_nombre(tabla, nombre_limpio.upper()) if (tabla and nombre_limpio) else None
    foto = item['foto'] if item else None
    return (nombre_limpio or '---'), catalogos_services.url_foto(foto)


@primera_semana_bp.route('/primera-semana', methods=['GET', 'POST'])
@login_requerido
def primera_semana():
    # Tabla exclusiva para seguimiento estricto del arranque en granja de los primeros 7 días
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    filas = []
    cabecera = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        cabecera = get_cabecera_info(lote_seleccionado)
        filas = get_primera_semana_by_lote(lote_seleccionado)

    return render_template(
        'produccion/primera_semana.html',
        filas=filas,
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=cabecera
    )


@primera_semana_bp.route('/grafico-primera-semana', methods=['GET', 'POST'])
@login_requerido
def grafico_primera_semana():
    # Sistema de memoria para recordar el lote seleccionado
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    datos_grafico = None
    info_lote = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        datos_grafico = get_data_grafico_primera_semana(lote_seleccionado)
        cab = get_cabecera_info(lote_seleccionado) or {}
        n_nutri, f_nutri = _foto_catalogo('nutricionista_lev', cab.get('nutricionista'))
        n_var, f_var = _foto_catalogo('variedad', cab.get('variedad'))
        n_marca, f_marca = _foto_catalogo('marca_galpon', cab.get('marca_galpon'))
        info_lote = {
            'nutricionista': {'etiqueta': 'Nutricionista Levante', 'nombre': n_nutri, 'foto': f_nutri},
            'variedad': {'etiqueta': 'Variedad', 'nombre': n_var, 'foto': f_var},
            'marca': {'etiqueta': 'Marca Galpón', 'nombre': n_marca, 'foto': f_marca},
        }

    return render_template(
        'graficas/grafico_primera_semana.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        datos_grafico=datos_grafico,
        info_lote=info_lote
    )