# routes/eventualidades/vistas.py
from flask import Blueprint, jsonify, request, session

from routes.routes import login_requerido
from models.eventualidades import services

eventualidades_bp = Blueprint('eventualidades', __name__)


@eventualidades_bp.route('/eventualidades/api/listar')
@login_requerido
def api_listar():
    lote = (request.args.get('lote') or '').strip()
    ambito = (request.args.get('ambito') or 'PRODUCCION').strip().upper()

    try:
        return jsonify(services.listar(lote, ambito))
    except ValueError as e:
        return jsonify({'status': 'error', 'mensaje': str(e)}), 400
    except Exception as e:
        print(f"[ERROR EVENTUALIDADES LISTAR]: {e}")
        return jsonify({
            'status': 'error',
            'mensaje': 'No se pudieron cargar las eventualidades.',
        }), 500


@eventualidades_bp.route('/eventualidades/api/crear', methods=['POST'])
@login_requerido
def api_crear():
    datos = request.get_json(silent=True) or {}
    try:
        resultado = services.crear(
            datos,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre'),
        )
        return jsonify(resultado)
    except ValueError as e:
        return jsonify({'status': 'error', 'mensaje': str(e)}), 400
    except Exception as e:
        print(f"[ERROR EVENTUALIDADES CREAR]: {e}")
        return jsonify({
            'status': 'error',
            'mensaje': 'No se pudo guardar la eventualidad.',
        }), 500


@eventualidades_bp.route('/eventualidades/api/<int:id_evento>/editar', methods=['POST'])
@login_requerido
def api_editar(id_evento):
    datos = request.get_json(silent=True) or {}
    try:
        resultado = services.actualizar(
            id_evento,
            datos,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre'),
        )
        return jsonify(resultado)
    except ValueError as e:
        return jsonify({'status': 'error', 'mensaje': str(e)}), 400
    except Exception as e:
        print(f"[ERROR EVENTUALIDADES EDITAR]: {e}")
        return jsonify({
            'status': 'error',
            'mensaje': 'No se pudo actualizar la eventualidad.',
        }), 500


@eventualidades_bp.route('/eventualidades/api/<int:id_evento>/eliminar', methods=['POST'])
@login_requerido
def api_eliminar(id_evento):
    try:
        resultado = services.eliminar(
            id_evento,
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre'),
        )
        return jsonify(resultado)
    except ValueError as e:
        return jsonify({'status': 'error', 'mensaje': str(e)}), 400
    except Exception as e:
        print(f"[ERROR EVENTUALIDADES ELIMINAR]: {e}")
        return jsonify({
            'status': 'error',
            'mensaje': 'No se pudo eliminar la eventualidad.',
        }), 500


@eventualidades_bp.route('/eventualidades/api/tipos', methods=['GET', 'POST'])
@login_requerido
def api_tipos():
    if request.method == 'GET':
        try:
            return jsonify(services.tipos())
        except Exception as e:
            print(f"[ERROR EVENTUALIDADES TIPOS]: {e}")
            return jsonify({'status': 'error', 'mensaje': 'No se pudieron cargar los tipos.'}), 500

    datos = request.get_json(silent=True) or {}
    try:
        resultado = services.crear_tipo(
            datos.get('nombre'),
            datos.get('color'),
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre'),
        )
        return jsonify(resultado)
    except ValueError as e:
        return jsonify({'status': 'error', 'mensaje': str(e)}), 400
    except Exception as e:
        print(f"[ERROR EVENTUALIDADES CREAR TIPO]: {e}")
        return jsonify({'status': 'error', 'mensaje': 'No se pudo crear el tipo.'}), 500
