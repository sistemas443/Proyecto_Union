# routes/reporte_diario/vistas.py
from datetime import date

from flask import Blueprint, jsonify, render_template, request, session

from routes.routes import login_requerido
from models.lotes.services import get_lotes_distintos
from models.reporte_diario import (
    MESES,
    cabecera_lote,
    estado_mes,
    guardar_campo,
    listar_mes,
    mort_total_de,
    saldo_inicial,
    tabla_disponible,
)

reporte_diario_bp = Blueprint('reporte_diario', __name__)


@reporte_diario_bp.route('/reporte-diario', methods=['GET', 'POST'])
@login_requerido
def reporte_diario():
    # --- Lote seleccionado ---------------------------------------------------
    if request.method == 'POST':
        lote = (request.form.get('lote') or '').strip()
        mes_txt = (request.form.get('mes') or '').strip()
        if lote and lote != 'VACIO':
            session['ultimo_lote'] = lote
    else:
        lote = (request.args.get('lote') or '').strip()
        mes_txt = (request.args.get('mes') or '').strip()
        if not lote:
            lote = session.get('ultimo_lote', '')

    # --- Mes visualizado (por defecto, el actual) ----------------------------
    hoy = date.today()
    anio, mes = hoy.year, hoy.month

    if len(mes_txt) == 7 and mes_txt[4] == '-':
        try:
            anio_tmp = int(mes_txt[:4])
            mes_tmp = int(mes_txt[5:7])
            if 1 <= mes_tmp <= 12 and 2000 <= anio_tmp <= 2100:
                anio, mes = anio_tmp, mes_tmp
        except ValueError:
            pass

    # --- Datos ---------------------------------------------------------------
    hay_tabla = tabla_disponible()
    cabecera = None
    filas = []
    totales = {}
    aves_encasetadas = 0
    hay_desinfeccion = False

    if lote and lote != 'VACIO' and hay_tabla:
        cabecera = cabecera_lote(lote)
        if cabecera:
            aves_encasetadas = (
                cabecera.get('no_aves_encasetadas')
                or cabecera.get('no_pollitas_recibidas')
                or 0
            )
            saldo_apertura = saldo_inicial(cabecera.get('id'), anio, mes)
            if saldo_apertura is None:
                saldo_apertura = aves_encasetadas

            filas, totales = listar_mes(cabecera.get('id'), anio, mes, saldo_apertura)

            if aves_encasetadas > 0:
                totales['porc_mort'] = round(
                    (aves_encasetadas - totales.get('saldo_final', 0)) / aves_encasetadas * 100, 3
                )
            else:
                totales['porc_mort'] = 0.0
            totales['saldo_apertura'] = saldo_apertura
            hay_desinfeccion = any(
                (f['datos'] or {}).get('desinfeccion') == 'Sí' for f in filas
            )

    return render_template(
        'produccion/reporte_diario.html',
        lotes=get_lotes_distintos(),
        lote_seleccionado=lote,
        cabecera=cabecera,
        filas=filas,
        totales=totales,
        aves_encasetadas=aves_encasetadas,
        anio=anio,
        mes=mes,
        mes_nombre=MESES[mes - 1],
        mes_valor=f'{anio:04d}-{mes:02d}',
        hay_tabla=hay_tabla,
        hoy=hoy,
        hay_desinfeccion=hay_desinfeccion,
    )


@reporte_diario_bp.route('/reporte-diario/guardar', methods=['POST'])
@login_requerido
def guardar():
    """Guarda una celda del reporte y devuelve el mes recalculado."""
    datos = request.get_json(silent=True) or {}
    lote = (datos.get('lote') or '').strip()
    fecha_txt = (datos.get('fecha') or '').strip()
    campo = (datos.get('campo') or '').strip()
    valor = datos.get('valor')

    if not lote or not fecha_txt or not campo:
        return jsonify(ok=False, error='Faltan datos para guardar'), 400

    try:
        fecha = date.fromisoformat(fecha_txt)
    except ValueError:
        return jsonify(ok=False, error='Fecha inválida'), 400

    cabecera = cabecera_lote(lote)
    if not cabecera:
        return jsonify(ok=False, error='No se encontró el lote'), 404

    aves = cabecera.get('no_aves_encasetadas') or cabecera.get('no_pollitas_recibidas') or 0
    saldo_ap = saldo_inicial(cabecera['id'], fecha.year, fecha.month)
    if saldo_ap is None:
        saldo_ap = aves

    filas, _ = listar_mes(cabecera['id'], fecha.year, fecha.month, saldo_ap)
    indice = next((i for i, f in enumerate(filas) if f['fecha'] == fecha), None)
    if indice is None:
        return jsonify(ok=False, error='La fecha no pertenece al mes mostrado'), 400

    saldo_previo = filas[indice - 1]['saldo'] if indice > 0 else saldo_ap
    actual = filas[indice]['datos'] or {}

    # Validación: las muertes (y las "otras" que descuentan) no pueden superar el saldo
    if campo in ('mort_m1', 'mort_m2', 'mort_m3', 'mort_m4', 'otras'):
        def a_entero(v):
            limpio = ''.join(c for c in str(v if v is not None else '') if c.isdigit())
            return int(limpio) if limpio else 0

        modulos = {
            k: a_entero(actual.get(k))
            for k in ('mort_m1', 'mort_m2', 'mort_m3', 'mort_m4')
        }
        otras = a_entero(actual.get('otras'))
        afecta = actual.get('afecta_saldo', True)

        if campo == 'otras':
            otras = a_entero(valor)
        else:
            modulos[campo] = a_entero(valor)

        total = sum(modulos.values()) + (otras if afecta else 0)
        if total > saldo_previo:
            return jsonify(
                ok=False,
                error=f'Las muertes del día ({total:,}) superan el saldo disponible ({saldo_previo:,}).',
            ), 400

    try:
        guardar_campo(cabecera['id'], lote, fecha_txt, campo, valor)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400

    saldos, totales = estado_mes(cabecera['id'], fecha.year, fecha.month, saldo_ap)
    if aves:
        totales['porc_mort'] = round(
            (aves - totales.get('saldo_final', 0)) / aves * 100, 3
        )

    return jsonify(
        ok=True,
        mort_total=mort_total_de(cabecera['id'], fecha_txt),
        saldos=saldos,
        totales=totales,
    )
