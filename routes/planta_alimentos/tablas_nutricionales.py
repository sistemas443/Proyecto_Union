# -*- coding: utf-8 -*-
"""Tablas Nutricionales: vista de datos (Fase 1)."""
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify

from routes.routes import login_requerido
from models.planta_alimentos.tablas_nutricionales import (
    TablaNutricional, columnas_nutrientes, SUBS_EDITABLES, CORE_EDITABLES, GRAFICOS,
)

tn_bp = Blueprint('tablas_nutricionales', __name__, url_prefix='/tablas-nutricionales')


@tn_bp.route('/')
@login_requerido
def vista():
    lotes = TablaNutricional.lotes_disponibles()
    disponibles = [l['lote'] for l in lotes]

    lote = (request.args.get('lote') or '').strip()
    if not lote or lote not in disponibles:
        con_datos = next((l['lote'] for l in lotes if l.get('tiene_datos')), None)
        lote = con_datos or (disponibles[0] if disponibles else '')

    datos = TablaNutricional.obtener_datos_lote(lote) if lote else None

    vista = (request.args.get('vista') or 'datos').strip()
    if vista not in ('datos', 'analisis', 'precio_huevo'):
        vista = 'datos'
    grafico = (request.args.get('grafico') or 'peso_consumo').strip()
    if grafico not in [g['codigo'] for g in GRAFICOS]:
        grafico = GRAFICOS[0]['codigo']

    chart = TablaNutricional.datos_grafico(datos, grafico) if (datos and vista == 'analisis') else None
    precios_huevo = TablaNutricional.precios_huevo(lote) if (lote and vista == 'precio_huevo') else None

    return render_template(
        'planta_alimentos/tablas_nutricionales.html',
        lotes=lotes,
        lote=lote,
        datos=datos,
        columnas=columnas_nutrientes(),
        subs_editables=SUBS_EDITABLES,
        core_editables=CORE_EDITABLES,
        puede_editar=(session.get('user_rol') or '') != 'Lector',
        vista=vista,
        grafico=grafico,
        graficos=GRAFICOS,
        chart=chart,
        precios_huevo=precios_huevo,
    )


@tn_bp.route('/guardar', methods=['POST'])
@login_requerido
def guardar_celda():
    """Guarda un valor editable y devuelve la fila recalculada."""
    if (session.get('user_rol') or '').strip() == 'Lector':
        return jsonify({'status': 'error', 'msg': 'Modo lectura: no puede editar.'}), 403

    datos = request.get_json(silent=True) or {}
    lote = (datos.get('lote') or '').strip()
    campo = (datos.get('campo') or '').strip()
    try:
        semana = int(datos.get('semana'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'Semana inválida.'}), 400

    if not lote or not campo:
        return jsonify({'status': 'error', 'msg': 'Faltan datos.'}), 400

    usuario = session.get('usuario_nombre') or session.get('user_nombre') or 'Sistema'
    resultado = TablaNutricional.actualizar_celda(
        lote, semana, campo, datos.get('valor'), usuario
    )
    if not resultado.get('ok'):
        return jsonify({'status': 'error', 'msg': resultado.get('msg', 'No se pudo guardar.')}), 400
    return jsonify({'status': 'ok', 'valores': resultado.get('valores', {})})


@tn_bp.route('/importar', methods=['POST'])
@login_requerido
def importar():
    if (session.get('user_rol') or '').strip() == 'Lector':
        flash('No tiene permisos para importar tablas nutricionales.', 'warning')
        return redirect(url_for('tablas_nutricionales.vista'))

    archivo = request.files.get('archivo')
    lote_actual = (request.form.get('lote') or '').strip()

    if not archivo or not archivo.filename:
        flash('Seleccione el archivo de Excel (.xlsm o .xlsx).', 'warning')
        return redirect(url_for('tablas_nutricionales.vista', lote=lote_actual))

    nombre = os.path.basename(archivo.filename)
    if not nombre.lower().endswith(('.xlsm', '.xlsx')):
        flash('El archivo debe ser de Excel (.xlsm o .xlsx).', 'warning')
        return redirect(url_for('tablas_nutricionales.vista', lote=lote_actual))

    usuario = session.get('usuario_nombre') or session.get('user_nombre') or 'Sistema'
    try:
        resultado = TablaNutricional.importar_excel(archivo.read(), nombre, usuario)
    except Exception as e:
        print(f'[ERROR IMPORTAR TN]: {e}')
        flash('No se pudo procesar el archivo.', 'danger')
        return redirect(url_for('tablas_nutricionales.vista', lote=lote_actual))

    if not resultado.get('ok'):
        flash(resultado.get('msg', 'No se pudo importar el archivo.'), 'danger')
        return redirect(url_for('tablas_nutricionales.vista', lote=lote_actual))

    flash(
        f"Se importaron {resultado['semanas']} semanas del lote {resultado['lote']} "
        f"({nombre}).",
        'success'
    )
    return redirect(url_for('tablas_nutricionales.vista', lote=resultado['lote']))
