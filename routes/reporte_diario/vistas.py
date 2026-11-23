# routes/reporte_diario/vistas.py
from datetime import date

from flask import Blueprint, jsonify, render_template, request, session

from routes.routes import login_requerido
from models.lotes.services import get_lotes_distintos, get_lotes_agrupados
from models.reporte_diario import (
    MESES,
    cabecera_lote,
    crear_desinfectante,
    estado_mes,
    guardar_campo,
    guardar_modulos_entrada,
    listar_desinfectantes,
    listar_mes,
    modulos_entrada,
    mort_total_de,
    saldo_inicial,
    sincronizar_diario,
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
    mods_entrada = []

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
            mods_entrada = modulos_entrada(cabecera.get('id'))

    return render_template(
        'produccion/reporte_diario.html',
        lotes=get_lotes_distintos(),
        lotes_agrupados=get_lotes_agrupados(session.get('user_rol')),
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
        mods_entrada=mods_entrada,
        desinfectantes=listar_desinfectantes(),
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
    if campo in ('muertas', 'otras'):
        def a_entero(v):
            limpio = ''.join(c for c in str(v if v is not None else '') if c.isdigit())
            return int(limpio) if limpio else 0

        muertas = a_entero(actual.get('muertas'))
        otras = a_entero(actual.get('otras'))
        afecta = actual.get('afecta_saldo', True)

        if campo == 'muertas':
            muertas = a_entero(valor)
        else:
            otras = a_entero(valor)

        total = muertas + (otras if afecta else 0)
        if total > saldo_previo:
            return jsonify(
                ok=False,
                error=f'Las muertes del día ({total:,}) superan el saldo disponible ({saldo_previo:,}).',
            ), 400

    try:
        guardar_campo(cabecera['id'], lote, fecha_txt, campo, valor)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400

    # Reporte Diario es la primera captura del día: los campos operativos se
    # replican en el Diario con su misma cascada de cálculo.
    aviso_diario = {'sincronizado': False, 'motivo': 'no_aplica'}
    if campo in ('produccion', 'alimento', 'muertas', 'agua', 'otras'):
        afecta = actual.get('afecta_saldo')
        if afecta is None:
            afecta = True
        aviso_diario = sincronizar_diario(cabecera['id'], fecha, campo, valor, afecta)

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
        diario=aviso_diario,
    )


@reporte_diario_bp.route('/reporte-diario/config-entrada', methods=['POST'])
@login_requerido
def config_entrada():
    """Marca qué módulos tienen la puerta/entrada del galpón."""
    datos = request.get_json(silent=True) or {}
    lote = (datos.get('lote') or '').strip()
    modulos = datos.get('modulos') or []

    if not lote:
        return jsonify(ok=False, error='Falta el lote'), 400
    if not isinstance(modulos, list):
        modulos = [modulos]

    cabecera = cabecera_lote(lote)
    if not cabecera:
        return jsonify(ok=False, error='No se encontró el lote'), 404

    limpios = guardar_modulos_entrada(cabecera['id'], modulos)
    return jsonify(ok=True, modulos=limpios)


@reporte_diario_bp.route('/reporte-diario/desinfectantes', methods=['POST'])
@login_requerido
def crear_desinfectante_api():
    """Agrega un producto al catalogo de desinfectantes."""
    datos = request.get_json(silent=True) or {}
    nombre = (datos.get('nombre') or '').strip()

    if not nombre:
        return jsonify(ok=False, error='Escribe el nombre del producto'), 400

    try:
        producto = crear_desinfectante(nombre)
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo crear el desinfectante: {e}")
        return jsonify(ok=False, error='No se pudo guardar el producto'), 400

    return jsonify(ok=True, desinfectante=producto)
