from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from routes.routes import login_requerido, editor_requerido, superadmin_requerido
from models.base import get_db_connection
from models.catalogos import services as catalogos_services
from models.lotes import model as lotes_model
from models.lotes import clasificacion as lotes_clasificacion
from models.lotes.services import (
    get_todos_los_lotes, get_opciones_dinamicas,
    guardar_nuevo_lote, actualizar_lote, borrar_lote
)
from models.cabecera.services import update_cabecera_unificada

lotes_bp = Blueprint('lotes', __name__)


def _empresa_id_por_nombre(nombre):
    """Devuelve el id de la empresa por nombre (sin distinguir mayusculas)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM empresas WHERE UPPER(TRIM(nombre)) = %s LIMIT 1",
                (nombre.strip().upper(),)
            )
            fila = cur.fetchone()
            return fila[0] if fila else None
    finally:
        conn.close()


@lotes_bp.route('/lotes')
@login_requerido
def vista_lotes():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT nombre FROM catalogo_responsables ORDER BY nombre ASC")
        lista_responsables = [row[0] for row in cur.fetchall()]

        cur.execute("SELECT id, nombre FROM empresas ORDER BY nombre ASC")
        lista_empresas = [{'id': row[0], 'nombre': row[1]} for row in cur.fetchall()]

        # Los 4 catálogos con foto (solo activos) reutilizan la misma conexión
        cat_nutr_lev = catalogos_services.listar_catalogo('nutricionista_lev', cur)
        cat_nutr_prod = catalogos_services.listar_catalogo('nutricionista_prod', cur)
        cat_variedades = catalogos_services.listar_catalogo('variedad', cur)
        cat_marcas = catalogos_services.listar_catalogo('marca_galpon', cur)

        # Lotes y opciones de autocompletado, también en la misma conexión
        lotes = get_todos_los_lotes(cur)
        opciones = get_opciones_dinamicas(cur)
    except Exception as e:
        print(f"[ERROR CATALOGOS]: {e}")
        lista_responsables, lista_empresas = [], []
        cat_nutr_lev, cat_nutr_prod, cat_variedades, cat_marcas = [], [], [], []
        lotes, opciones = [], {}
    finally:
        cur.close()
        conn.close()

    # El rol PRODUCCION ve SAN MARTIN y los externos con Levante externo = SI
    rol = (session.get('user_rol') or '').strip()
    empresa_filtro = None
    if rol == 'PRODUCCION':
        empresa_filtro = next(
            (e['id'] for e in lista_empresas
             if e['nombre'].strip().upper() == 'SAN MARTIN'), None)
        if empresa_filtro:
            lotes = [
                l for l in lotes
                if l.get('empresa_id') == empresa_filtro
                or (l.get('empresa_id') != empresa_filtro and l.get('levante_externo'))
            ]
            ids_empresas = {l.get('empresa_id') for l in lotes if l.get('empresa_id')}
            lista_empresas = [
                e for e in lista_empresas
                if e['id'] == empresa_filtro or e['id'] in ids_empresas
            ]

    # Clasificación ACTIVO / CONCLUIDO para las pestañas de la lista
    estados = lotes_clasificacion.fetch_clasificacion_lotes([l['lote'] for l in lotes])
    for lote in lotes:
        lote['estado'] = estados.get(lote['lote'], {}).get('estado', 'ACTIVO')

    def _fotos(tipo, items):
        return {i['nombre']: catalogos_services.url_foto_por_id(tipo, i['id']) for i in items}

    fotos_catalogo = {
        'f_nutricionista': _fotos('nutricionista_lev', cat_nutr_lev),
        'f_nutricionista_prod': _fotos('nutricionista_prod', cat_nutr_prod),
        'f_variedad': _fotos('variedad', cat_variedades),
        'f_marca_galpon': _fotos('marca_galpon', cat_marcas),
    }

    return render_template(
        'produccion/lotes.html',
        lotes=lotes,
        opciones=opciones,
        cat_responsables=lista_responsables,
        empresas=lista_empresas,
        empresas_map={emp['id']: emp['nombre'] for emp in lista_empresas},
        cat_nutr_lev=cat_nutr_lev,
        cat_nutr_prod=cat_nutr_prod,
        cat_variedades=cat_variedades,
        cat_marcas=cat_marcas,
        fotos_catalogo=fotos_catalogo,
        user_rol=session.get('user_rol'),
        empresa_filtro=empresa_filtro
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

    # Las empresas se guardan en su propia tabla (el select usa el id)
    if tipo == 'empresa':
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM empresas WHERE UPPER(TRIM(nombre)) = %s", (nombre,))
            if cur.fetchone():
                return jsonify({'status': 'error', 'msg': 'Esta empresa ya existe.'}), 400

            cur.execute("INSERT INTO empresas (nombre) VALUES (%s) RETURNING id", (nombre,))
            empresa_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({'status': 'ok', 'nombre': nombre, 'id': empresa_id})
        except Exception as e:
            conn.rollback()
            if "unique constraint" in str(e).lower():
                return jsonify({'status': 'error', 'msg': 'Esta empresa ya existe.'}), 400
            print(f"[ERROR CREANDO EMPRESA]: {e}")
            return jsonify({'status': 'error', 'msg': 'Error interno al guardar.'}), 500
        finally:
            cur.close()
            conn.close()

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

    # Reglas de empresa:
    # - PRODUCCION crea solo lotes SAN MARTIN y conserva la empresa al editar.
    # - SAN MARTIN nunca lleva Levante externo.
    rol = (session.get('user_rol') or '').strip()
    san_martin_id = _empresa_id_por_nombre('SAN MARTIN')
    if rol == 'PRODUCCION':
        if id_lote:
            existente = lotes_model.fetch_lote_por_id(id_lote)
            if existente and existente.get('empresa_id'):
                datos['empresa_id'] = str(existente['empresa_id'])
            elif san_martin_id:
                datos['empresa_id'] = str(san_martin_id)
        elif san_martin_id:
            datos['empresa_id'] = str(san_martin_id)

    if san_martin_id and str(datos.get('empresa_id') or '').strip() == str(san_martin_id):
        datos['levante_externo'] = 'NO'

    usuario_id = session.get('user_id')
    usuario_nombre = session.get('user_nombre', 'Desconocido')
    success, msg = actualizar_lote(id_lote, datos,
                                   usuario_id=usuario_id,
                                   usuario_nombre=usuario_nombre) if id_lote else guardar_nuevo_lote(
                                       datos, usuario_id=usuario_id, usuario_nombre=usuario_nombre)
    if not success:
        flash(msg, "error")
        return redirect(url_for('lotes.vista_lotes'))
    flash(msg, "success")
    return redirect(url_for('lotes.vista_lotes'))


@lotes_bp.route('/api/borrar-lote/<int:id>', methods=['POST'])
@login_requerido
@superadmin_requerido
def api_borrar_lote(id):
    if borrar_lote(id):
        return jsonify({'status': 'ok'}), 200

    from models.auditoria.services import registrar_error
    registrar_error(
        tabla='cabecera_lotes',
        contexto='Borrar lote',
        mensaje=f'Operación rechazada al intentar borrar el registro {id}',
        usuario_id=session.get('user_id'),
        usuario_nombre=session.get('user_nombre', 'Desconocido'),
    )
    return jsonify({'status': 'error', 'msg': 'Dato protegido o inexistente'}), 500


@lotes_bp.route('/api/lotes/<int:id>/estado-manual', methods=['POST'])
@login_requerido
@superadmin_requerido
def cambiar_estado_manual(id):
    """Cambia manualmente un lote entre ACTIVO y CONCLUIDO (solo Superadmin)."""
    data = request.get_json(silent=True) or {}
    estado = (data.get('estado') or '').strip().upper()
    if estado not in ('ACTIVO', 'CONCLUIDO'):
        return jsonify({'status': 'error', 'msg': 'Estado no válido.'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE cabecera_lotes SET estado_manual = %s WHERE id = %s RETURNING id, lote",
            (estado, id),
        )
        fila = cur.fetchone()
        if not fila:
            conn.rollback()
            return jsonify({'status': 'error', 'msg': 'Lote no encontrado.'}), 404

        from models.auditoria.services import registrar_cambio
        registrar_cambio(
            usuario_id=session.get('user_id'),
            usuario_nombre=session.get('user_nombre', 'Desconocido'),
            tabla='cabecera_lotes',
            id_registro=id,
            campo='estado_manual',
            valor_anterior=None,
            valor_nuevo=estado,
            accion='UPDATE',
            cursor=cur,
        )
        conn.commit()
        return jsonify({'status': 'ok', 'estado': estado})
    except Exception as e:
        conn.rollback()
        print(f"[ESTADO MANUAL] {e}")
        return jsonify({'status': 'error', 'msg': 'No se pudo cambiar el estado.'}), 500
    finally:
        cur.close()
        conn.close()


@lotes_bp.route('/api/cabecera/actualizar', methods=['POST'])
@login_requerido
@editor_requerido
def actualizar_cabecera():
    from flask import request
    data = request.get_json(silent=True) or {}
    lote, columna, valor = data.get('lote'), data.get('columna'), data.get('valor')
    if not lote or not columna:
        return jsonify({'status': 'error', 'msg': 'Faltan datos'}), 400

    # Un usuario de PRODUCCION no puede mover el lote a otra empresa
    if (session.get('user_rol') or '').strip() == 'PRODUCCION' and columna == 'empresa_id':
        return jsonify({
            'status': 'error',
            'msg': 'No tiene permisos para cambiar la empresa del lote.'
        }), 403
    success, msg = update_cabecera_unificada(
        lote, columna, valor,
        usuario_id=session.get('user_id'),
        usuario_nombre=session.get('user_nombre', 'Desconocido'),
    )
    if success:
        return jsonify({'status': 'ok'}), 200

    from models.auditoria.services import registrar_error
    registrar_error(
        tabla='cabecera_lotes',
        contexto='Guardar dato de cabecera',
        mensaje=f"{lote} - {columna}: {msg}",
        usuario_id=session.get('user_id'),
        usuario_nombre=session.get('user_nombre', 'Desconocido'),
    )
    return jsonify({'status': 'error', 'msg': msg}), 500