from flask import Blueprint, render_template, request, session
from routes.routes import login_requerido
from models.semanal_levante.services import get_semanal_levante_all
from models.cabecera.services import get_cabecera_info
from models.lotes.services import get_lotes_distintos

semanal_levante_bp = Blueprint('semanal_levante', __name__)


@semanal_levante_bp.route('/semanal-levante', methods=['GET', 'POST'])
@login_requerido
def semanal_levante():
    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != '':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    return render_template(
        'produccion/sem_lev.html',
        filas=get_semanal_levante_all(lote_seleccionado),
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        cabecera=get_cabecera_info(lote_seleccionado)
    )


@semanal_levante_bp.route('/grafico-semanal-levante', methods=['GET', 'POST'])
@login_requerido
def grafico_semanal_levante():
    def to_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    if request.method == 'POST':
        lote_seleccionado = request.form.get('lote', '')
        if lote_seleccionado and lote_seleccionado != 'VACIO':
            session['ultimo_lote'] = lote_seleccionado
    else:
        lote_seleccionado = session.get('ultimo_lote', '')

    datos_grafico = None
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        filas = get_semanal_levante_all(lote_seleccionado)
        # Filtrar solo semanas 1-18
        filas = [f for f in filas if 1 <= int(f.get('sem', 0)) <= 18]

        # Crear diccionario para acceso rápido por semana
        datos_por_semana = {int(f['sem']): f for f in filas}

        # Generar lista completa de semanas 1-18
        etiquetas = [f"Semana {i}" for i in range(1, 19)]
        consumo_real = [to_float(datos_por_semana.get(i, {}).get('cons_gr_ave_ao')) for i in range(1, 19)]
        consumo_tab = [to_float(datos_por_semana.get(i, {}).get('cons_gr_ave_tab')) for i in range(1, 19)]
        peso_real = [to_float(datos_por_semana.get(i, {}).get('peso_ave_real')) for i in range(1, 19)]
        peso_tab = [to_float(datos_por_semana.get(i, {}).get('peso_ave_tab')) for i in range(1, 19)]

        # Calcular regresión lineal usando números de semana (1-18)
        puntos_validos = [(i, peso_tab[i-1]) for i in range(1, 19) if peso_tab[i-1] is not None and peso_tab[i-1] > 0]

        lineal_peso_tab = [None] * 18  # Inicializar con None
        if len(puntos_validos) > 1:
            n = len(puntos_validos)
            x_mean = sum(p[0] for p in puntos_validos) / n
            y_mean = sum(p[1] for p in puntos_validos) / n
            num = sum((p[0] - x_mean) * (p[1] - y_mean) for p in puntos_validos)
            den = sum((p[0] - x_mean) ** 2 for p in puntos_validos)
            pendiente = num / den if den != 0 else 0
            intercepto = y_mean - pendiente * x_mean
            for i in range(1, 19):
                lineal_peso_tab[i-1] = pendiente * i + intercepto

        datos_grafico = {
            'etiquetas': etiquetas,
            'consumo_real': consumo_real,
            'consumo_tab': consumo_tab,
            'peso_real': peso_real,
            'peso_tab': peso_tab,
            'lineal_peso_tab': lineal_peso_tab
        }

    return render_template(
        'graficas/grafico_sem_lev.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote_seleccionado,
        datos_grafico=datos_grafico
    )