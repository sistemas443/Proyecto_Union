"""Grilla de Consolidados L+P. En Fase A ninguna vista destino existe:
todos los botones se muestran como Próximamente."""
from flask import Blueprint, render_template, request
from routes.routes import login_requerido

consolidados_bp = Blueprint('consolidados', __name__)

# Orden de la grilla: 4 filas x 6 botones (ver Excel de referencia).
# url=None -> botón deshabilitado con badge "Próximamente".
BOTONES = [
    # Fila 1
    {'titulo': 'PRIMER HUEVO (#1)', 'icono': '🥚', 'hoja': 'H2', 'endpoint': 'consolidados.primer_huevo'},
    {'titulo': 'HUEVOS SEMANAL', 'icono': '📦', 'hoja': 'H3', 'endpoint': 'consolidados.huevos_semanal'},
    {'titulo': 'KILOS SEMANAL', 'icono': '⚖️', 'hoja': 'H4', 'endpoint': 'consolidados.kilos_semanal'},
    {'titulo': '% MORTALIDAD', 'icono': '☠️', 'hoja': 'H10', 'endpoint': 'consolidados.mort_semanal'},
    {'titulo': 'PESO AVE', 'icono': '🐤', 'hoja': 'H6', 'endpoint': 'consolidados.peso_aves'},
    # Fila 2
    {'titulo': 'SALDO AVES', 'icono': '🐔', 'hoja': 'H8', 'endpoint': 'consolidados.saldo_aves'},
    {'titulo': '% PRODUCCIÓN', 'icono': '📈', 'hoja': 'H9', 'endpoint': 'consolidados.porc_produccion'},
    {'titulo': '% MORT. ACUMULADA', 'icono': '☠️', 'hoja': 'H11', 'endpoint': 'consolidados.mort_acumulada'},
    {'titulo': '% MORTALIDAD SEMANAL', 'icono': '📉', 'hoja': 'H5', 'endpoint': 'consolidados.mortalidad_semanal'},
    {'titulo': 'PESO HUEVO', 'icono': '⚪', 'hoja': 'PESO HUEVO', 'endpoint': 'consolidados.peso_huevo'},
    {'titulo': 'UNIFORMIDAD', 'icono': '🎯', 'hoja': 'Uniformidad', 'endpoint': 'consolidados.uniformidad'},
    # Fila 3
    {'titulo': 'CONVERSIÓN SEMANAL', 'icono': '🔄', 'hoja': 'H14', 'endpoint': 'consolidados.conv_semanal'},
    {'titulo': 'CONVERSIÓN ACUMULADA', 'icono': '🔁', 'hoja': 'H15', 'endpoint': 'consolidados.conv_acumulada'},
    {'titulo': 'MASA HUEVO SEMANAL', 'icono': '🧮', 'hoja': 'H16', 'endpoint': 'consolidados.masa_semanal'},
    {'titulo': 'MASA HUEVO ACUMULADA', 'icono': '🧮', 'hoja': 'H17', 'endpoint': 'consolidados.masa_acumulada'},
    {'titulo': 'PRIMERA SEMANA LEVANTE', 'icono': '🌱', 'hoja': 'H18', 'endpoint': 'consolidados.primera_semana_levante'},
    # Fila 4
    {'titulo': 'HUEVOS AVE ALOJADA', 'icono': '🥚', 'hoja': 'H12', 'endpoint': 'consolidados.huevos_ave_alojada'},
    {'titulo': 'GRAMOS AVES', 'icono': '🌾', 'hoja': 'H13', 'endpoint': 'consolidados.gramos_aves'},
    {'titulo': 'ACUMULADOS CLASIFICADORA', 'icono': '🗂️', 'hoja': 'ACUM. CLASIF.', 'endpoint': 'consolidados.acumulados_clasificadora'},
    {'titulo': 'ROTURA DE HUEVO', 'icono': '💔', 'hoja': 'ROTURA', 'endpoint': 'consolidados.rotura_huevo'},
    {'titulo': 'DATOS DE LEVANTE', 'icono': '📋', 'hoja': 'H19', 'endpoint': 'consolidados.datos_levante'},
    {'titulo': 'CONSOLIDADO CONSUMO DE AGUA', 'icono': '💧', 'hoja': 'H7', 'endpoint': 'consolidados.consumo_agua'},
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


@consolidados_bp.route('/consolidados/huevos-semanal')
@login_requerido
def huevos_semanal():
    """Renderiza la matriz de huevos semanales por lote."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_huevos_semanal_detalle()
    return render_template('consolidados/huevos_semanal.html', datos=datos)


@consolidados_bp.route('/consolidados/kilos-semanal')
@login_requerido
def kilos_semanal():
    """Renderiza la matriz de kilos semanales por lote."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_kilos_semanal_detalle()
    return render_template('consolidados/kilos_semanal.html', datos=datos)


@consolidados_bp.route('/consolidados/mortalidad-semanal')
@login_requerido
def mortalidad_semanal():
    """Renderiza la matriz de mortalidad semanal por lote."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_mortalidad_semanal_detalle()
    return render_template('consolidados/mortalidad_semanal.html', datos=datos)


@consolidados_bp.route('/consolidados/peso-aves')
@login_requerido
def peso_aves():
    """Renderiza la matriz de peso de aves con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_peso_aves_detalle()
    return render_template('consolidados/peso_aves.html', datos=datos)


@consolidados_bp.route('/consolidados/consumo-agua')
@login_requerido
def consumo_agua():
    """Renderiza la matriz de consumo de agua con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_consumo_agua_detalle()
    return render_template('consolidados/consumo_agua.html', datos=datos)


@consolidados_bp.route('/consolidados/saldo-aves')
@login_requerido
def saldo_aves():
    """Renderiza la matriz de saldo de aves por lote."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_saldo_aves_detalle()
    return render_template('consolidados/saldo_aves.html', datos=datos)


@consolidados_bp.route('/consolidados/porc-produccion')
@login_requerido
def porc_produccion():
    """Renderiza la matriz de % produccion con PROM geometrico y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_porc_produccion_detalle()
    return render_template('consolidados/porc_produccion.html', datos=datos)


@consolidados_bp.route('/consolidados/mort-acumulada')
@login_requerido
def mort_acumulada():
    """Renderiza la matriz de % mortalidad acumulada con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_mort_acumulada_detalle()
    return render_template('consolidados/mort_acumulada.html', datos=datos)


@consolidados_bp.route('/consolidados/mort-semanal')
@login_requerido
def mort_semanal():
    """Renderiza la matriz de % mortalidad semanal con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_mort_semanal_detalle()
    return render_template('consolidados/mort_semanal.html', datos=datos)


@consolidados_bp.route('/consolidados/huevos-ave-alojada')
@login_requerido
def huevos_ave_alojada():
    """Renderiza la matriz de huevos ave alojada con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_haa_detalle()
    return render_template('consolidados/haa.html', datos=datos)


@consolidados_bp.route('/consolidados/gramos-aves')
@login_requerido
def gramos_aves():
    """Renderiza la matriz de gramos/ave/dia con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_gramos_aves_detalle()
    return render_template('consolidados/gramos_aves.html', datos=datos)


@consolidados_bp.route('/consolidados/peso-huevo')
@login_requerido
def peso_huevo():
    """Renderiza la matriz de peso de huevo con PROM (sin TABLA)."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_peso_huevo_detalle()
    return render_template('consolidados/peso_huevo.html', datos=datos)


@consolidados_bp.route('/consolidados/uniformidad')
@login_requerido
def uniformidad():
    """Renderiza la matriz de % uniformidad con PROM (sin TABLA)."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_uniformidad_detalle()
    return render_template('consolidados/uniformidad.html', datos=datos)


@consolidados_bp.route('/consolidados/rotura-huevo')
@login_requerido
def rotura_huevo():
    """Renderiza la matriz de % rotura con PROM (sin TABLA)."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_rotura_huevo_detalle()
    return render_template('consolidados/rotura_huevo.html', datos=datos)


@consolidados_bp.route('/consolidados/acumulados-clasificadora')
@login_requerido
def acumulados_clasificadora():
    """Renderiza la matriz por categoria con selector (?categoria=)."""
    from flask import request
    from models.consolidados import services as consolidados_services
    categoria = request.args.get('categoria', 'SEGUNDAS')
    datos = consolidados_services.get_acumulados_clasificadora_detalle(categoria)
    return render_template('consolidados/acumulados_clasificadora.html', datos=datos)


@consolidados_bp.route('/consolidados/conv-semanal')
@login_requerido
def conv_semanal():
    """Renderiza la matriz de conversion semanal con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_conv_semanal_detalle()
    return render_template('consolidados/conv_semanal.html', datos=datos)


@consolidados_bp.route('/consolidados/conv-acumulada')
@login_requerido
def conv_acumulada():
    """Renderiza la matriz de conversion acumulada con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_conv_acumulada_detalle()
    return render_template('consolidados/conv_acumulada.html', datos=datos)


@consolidados_bp.route('/consolidados/masa-semanal')
@login_requerido
def masa_semanal():
    """Renderiza la matriz de masa de huevo semanal con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_masa_semanal_detalle()
    return render_template('consolidados/masa_semanal.html', datos=datos)


@consolidados_bp.route('/consolidados/masa-acumulada')
@login_requerido
def masa_acumulada():
    """Renderiza la matriz de masa de huevo acumulada con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_masa_acumulada_detalle()
    return render_template('consolidados/masa_acumulada.html', datos=datos)


@consolidados_bp.route('/consolidados/primera-semana-levante')
@login_requerido
def primera_semana_levante():
    """Renderiza la matriz Dia x Lote de peso corporal con PROM y TABLA."""
    from models.consolidados import services as consolidados_services
    datos = consolidados_services.get_primera_semana_levante_detalle()
    return render_template('consolidados/primera_semana_levante.html', datos=datos)


@consolidados_bp.route('/consolidados/datos-levante')
@login_requerido
def datos_levante():
    """Renderiza Datos de Levante con serie consolidada y consumo.

    Acepta ?lotes=69-10,70-12 para recalcular solo con incluidos.
    """
    from models.consolidados import services as consolidados_services
    param = request.args.get('lotes', '')
    lotes = [l.strip() for l in param.split(',') if l.strip()]
    datos = consolidados_services.get_datos_levante(lotes)
    return render_template('consolidados/datos_levante.html', datos=datos)
