from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from routes.routes import login_requerido, editor_requerido
from models.base import get_db_connection
from models.lotes.services import (
    get_todos_los_lotes, get_opciones_dinamicas,
    guardar_nuevo_lote, actualizar_lote, borrar_lote
)
from models.cabecera.services import update_cabecera_unificada

lotes_bp = Blueprint('lotes', __name__)


@lotes_bp.route('/lotes')
@login_requerido
def vista_lotes():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT nombre FROM catalogo_nutricionistas ORDER BY nombre ASC")
        lista_nutricionistas = [row[0] for row in cur.fetchall()]

        cur.execute("SELECT nombre FROM catalogo_responsables ORDER BY nombre ASC")
        lista_responsables = [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERROR CATALOGOS]: {e}")
        lista_nutricionistas, lista_responsables = [], []
    finally:
        cur.close()
        conn.close()

    return render_template(
        'produccion/lotes.html',
        lotes=get_todos_los_lotes(),
        opciones=get_opciones_dinamicas(),
        cat_nutricionistas=lista_nutricionistas,
        cat_responsables=lista_responsables
    )


@lotes_bp.route('/api/catalogos/crear', methods=['POST'])
@login_requerido
@editor_requerido
def crear_catalogo():
    from flask import request
    data = request.get_json(silent=True) or {}
    tipo = data.get('tipo')
    nombre = data.get('nombre', '').strip().upper()

    if not nombre:
        return jsonify({'status': 'error', 'msg': 'El nombre no puede estar vacío.'}), 400

    tabla = 'catalogo_nutricionistas' if tipo == 'nutricionista' else 'catalogo_responsables'

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"INSERT INTO {tabla} (nombre) VALUES (%s)", (nombre,))
        conn.commit()
        return jsonify({'status': 'ok', 'nombre': nombre})
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower():
            return jsonify({'status': 'error', 'msg': 'Esta persona ya existe en el catálogo.'}), 400
        print(f"[ERROR CREANDO CATALOGO]: {e}")
        return jsonify({'status': 'error', 'msg': 'Error interno al guardar.'}), 500
    finally:
        cur.close()
        conn.close()


@lotes_bp.route('/guardar-lote', methods=['POST'])
@login_requerido
@editor_requerido
def guardar_lote():
    from flask import request
    datos = request.form.to_dict()
    id_lote = request.form.get('id')
    success, msg = actualizar_lote(id_lote, datos, 
                                   usuario_id=session.get('user_id'),
                                   usuario_nombre=session.get('user_nombre', 'Desconocido')) if id_lote else guardar_nuevo_lote(datos)
    if not success:
        flash(msg, "error")
        return redirect(url_for('lotes.vista_lotes'))
    flash(msg, "success")
    return redirect(url_for('lotes.vista_lotes'))


@lotes_bp.route('/api/borrar-lote/<int:id>', methods=['POST'])
@login_requerido
@editor_requerido
def api_borrar_lote(id):
    return jsonify({'status': 'ok'}) if borrar_lote(id) else jsonify({'status': 'error', 'msg': 'Dato protegido o inexistente'}), 500


@lotes_bp.route('/api/cabecera/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_cabecera():
    from flask import request
    data = request.get_json(silent=True) or {}
    lote, columna, valor = data.get('lote'), data.get('columna'), data.get('valor')
    if not lote or not columna:
        return jsonify({'status': 'error', 'msg': 'Faltan datos'}), 400
    success, msg = update_cabecera_unificada(lote, columna, valor)
    return jsonify({'status': 'ok'}) if success else jsonify({'status': 'error', 'msg': msg}), 500