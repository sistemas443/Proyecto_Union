"""API de catálogos con foto. Crear/editar/eliminar: EXCLUSIVO Superadmin."""
from flask import Blueprint, request, jsonify, url_for, redirect, Response
from routes.routes import login_requerido, superadmin_requerido
from models.base import get_db_connection
from models.catalogos import services

catalogos_bp = Blueprint('catalogos', __name__)


def _url_foto(tipo, id_item):
    """URL de la foto servida desde la BD (o el placeholder si no hay id)."""
    if id_item is None:
        return url_for('static', filename='img/placeholder-catalogo.png')
    return url_for('catalogos.foto_catalogo', tipo=tipo, id_item=id_item)


@catalogos_bp.route('/api/catalogos/<tipo>', methods=['GET'])
@login_requerido
def listar_catalogo(tipo):
    """Lista los valores activos de un catálogo (para el modal)."""
    if not services.schemas.obtener_tabla(tipo):
        return jsonify({'status': 'error', 'msg': 'Tipo de catálogo inválido.'}), 404
    items = services.listar_catalogo(tipo)
    return jsonify({
        'status': 'ok',
        'items': [{'id': i['id'], 'nombre': i['nombre'], 'foto_url': _url_foto(tipo, i['id'])}
                  for i in items]
    })


@catalogos_bp.route('/api/catalogos/<tipo>/<int:id_item>/foto')
@login_requerido
def foto_catalogo(tipo, id_item):
    """Sirve la foto de un catálogo desde la BD (BYTEA)."""
    tabla = services.schemas.obtener_tabla(tipo)
    if not tabla:
        return jsonify({'status': 'error', 'msg': 'Tipo de catálogo inválido.'}), 404
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT foto_data FROM {tabla} WHERE id = %s AND activo = TRUE", (id_item,))
        r = cur.fetchone()
        if r and r[0]:
            return Response(bytes(r[0]), mimetype='image/jpeg')
        return redirect(url_for('static', filename='img/placeholder-catalogo.png'))
    finally:
        cur.close()
        conn.close()


@catalogos_bp.route('/api/catalogos/<tipo>/crear', methods=['POST'])
@login_requerido
@superadmin_requerido
def crear_catalogo(tipo):
    """Crea un valor con foto OBLIGATORIA (multipart/form-data)."""
    ok, msg, datos = services.crear_catalogo(
        tipo, request.form.get('nombre'), request.files.get('foto'))
    if not ok:
        return jsonify({'status': 'error', 'msg': msg}), 400
    return jsonify({'status': 'ok', 'msg': msg,
                    'nombre': datos['nombre'], 'foto_url': _url_foto(tipo, datos['id'])})


@catalogos_bp.route('/api/catalogos/<tipo>/<int:id_item>/editar', methods=['POST'])
@login_requerido
@superadmin_requerido
def editar_catalogo(tipo, id_item):
    """Edita nombre y opcionalmente la foto."""
    ok, msg, datos = services.editar_catalogo(
        tipo, id_item, request.form.get('nombre'), request.files.get('foto'))
    if not ok:
        return jsonify({'status': 'error', 'msg': msg}), 400
    return jsonify({'status': 'ok', 'msg': msg,
                    'nombre': datos['nombre'], 'foto_url': _url_foto(tipo, id_item)})


@catalogos_bp.route('/api/catalogos/<tipo>/<int:id_item>/borrar', methods=['POST'])
@login_requerido
@superadmin_requerido
def borrar_catalogo(tipo, id_item):
    """Borrado lógico (el nombre permanece para lotes antiguos)."""
    ok, msg, datos = services.eliminar_catalogo(tipo, id_item)
    if not ok:
        return jsonify({'status': 'error', 'msg': msg}), 400
    return jsonify({'status': 'ok', 'msg': msg, 'nombre': datos['nombre']})
