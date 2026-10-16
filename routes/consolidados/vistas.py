"""Grilla de Consolidados L+P. En Fase A ninguna vista destino existe:
todos los botones se muestran como Próximamente."""
from flask import Blueprint, render_template
from routes.routes import login_requerido

consolidados_bp = Blueprint('consolidados', __name__)

# Orden de la grilla: 4 filas x 6 botones (ver Excel de referencia).
# url=None -> botón deshabilitado con badge "Próximamente".
BOTONES = [
    # Fila 1
    {'titulo': 'PRIMER HUEVO (#1)', 'icono': '🥚', 'hoja': 'H2', 'endpoint': 'consolidados.primer_huevo'},
    {'titulo': 'HUEVOS SEMANAL', 'icono': '📦', 'hoja': 'H3', 'url': None},
    {'titulo': 'KILOS SEMANAL', 'icono': '⚖️', 'hoja': 'H4', 'url': None},
    {'titulo': '% MORTALIDAD', 'icono': '☠️', 'hoja': 'H10/H11', 'url': None},
    {'titulo': 'PESO AVE', 'icono': '🐤', 'hoja': 'H6', 'url': None},
    {'titulo': 'EVALUACIÓN SISTEMA DIGESTIVO SEMANA 6', 'icono': '🔬', 'hoja': 'EV. DIG. 6', 'url': None},
    # Fila 2
    {'titulo': 'SALDO AVES', 'icono': '🐔', 'hoja': 'H8', 'url': None},
    {'titulo': '% PRODUCCIÓN', 'icono': '📈', 'hoja': 'H9', 'url': None},
    {'titulo': '% MORTALIDAD', 'icono': '☠️', 'hoja': 'H10/H11', 'url': None},
    {'titulo': '% MORTALIDAD SEMANAL', 'icono': '📉', 'hoja': 'H5', 'url': None},
    {'titulo': 'PESO HUEVO', 'icono': '⚪', 'hoja': '% ACUM. CLASIF.', 'url': None},
    {'titulo': 'EVALUACIÓN SISTEMA DIGESTIVO SEMANA 12', 'icono': '🔬', 'hoja': 'EV. DIG. 12', 'url': None},
    # Fila 3
    {'titulo': 'CONVERSIÓN SEMANAL', 'icono': '🔄', 'hoja': 'H14', 'url': None},
    {'titulo': 'CONVERSIÓN ACUMULADA', 'icono': '🔁', 'hoja': 'H15', 'url': None},
    {'titulo': 'MASA HUEVO SEMANAL', 'icono': '🧮', 'hoja': 'H16', 'url': None},
    {'titulo': 'MASA HUEVO ACUMULADA', 'icono': '🧮', 'hoja': 'H17', 'url': None},
    {'titulo': 'PRIMERA SEMANA LEVANTE', 'icono': '🌱', 'hoja': 'H18', 'url': None},
    {'titulo': 'INDICADOR DE MORTALIDAD GENERAL', 'icono': '📊', 'hoja': 'MORT. GRAL.', 'url': None},
    # Fila 4
    {'titulo': 'HUEVOS AVE ALOJADA', 'icono': '🥚', 'hoja': 'H12', 'url': None},
    {'titulo': 'GRAMOS AVES', 'icono': '🌾', 'hoja': 'H13', 'url': None},
    {'titulo': 'ACUMULADOS CLASIFICADORA', 'icono': '🗂️', 'hoja': 'ACUM. CLASIF.', 'url': None},
    {'titulo': 'ROTURA DE HUEVO', 'icono': '💔', 'hoja': 'ROTURA', 'url': None},
    {'titulo': 'DATOS DE LEVANTE', 'icono': '📋', 'hoja': 'H19', 'url': None},
    {'titulo': 'CONSOLIDADO CONSUMO DE AGUA', 'icono': '💧', 'hoja': 'H7', 'url': None},
]


@consolidados_bp.route('/consolidados')
@login_requerido
def vista_consolidados():
    """Muestra la grilla de botones de Consolidados L+P."""
    return render_template('consolidados/index.html', botones=BOTONES)


@consolidados_bp.route('/consolidados/primer-huevo')
@login_requerido
def primer_huevo():
    """Renderiza la vista Primer Huevo con indicadores y matriz por dia."""
    from models.consolidados import services as consolidados_services
    matriz = consolidados_services.get_matriz_primer_huevo()
    return render_template('consolidados/primer_huevo.html', matriz=matriz)
