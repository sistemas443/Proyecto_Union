import json
import os
from datetime import datetime

import psycopg2.extras
from flask import render_template, request, redirect, url_for, flash, jsonify, session

from models.base import get_db_connection
from routes.planta_alimentos.catalogo_a import planta_bp  # O la ruta donde tengas definido el Blueprint
from routes.routes import login_requerido
from models.planta_alimentos.maestros import MateriaPrima
from models.planta_alimentos.formulas import FormulaDetalle
from models.auditoria.services import registrar_cambio

ROLES_PRECIOS = ('Superadmin', 'Director de Planta')
CARPETA_RESPALDOS = 'respaldos'


def _fecha_o_hoy(valor):
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return datetime.now().date()


def _resumen_impacto(filas):
    versiones = {(f['item_id'], f['lote_id'], f['version']) for f in filas}
    dietas = {(f['item_id'], f['lote_id']) for f in filas}
    return {
        'filas': len(filas),
        'versiones': len(versiones),
        'dietas': len(dietas),
    }


def _resumen_ensayos(filas):
    """Cantidad de ensayos afectados y de dietas/lotes distintos."""
    dietas = {(f['item_id'], f['lote_id']) for f in filas}
    return {
        'ensayos': len(filas),
        'ensayos_dietas': len(dietas),
    }


@planta_bp.route('/consolidado-precios/precio', methods=['POST'])
@login_requerido
def consolidado_precio_editar():
    """
    Corrige el precio (neto, IVA y flete) de una materia prima en las dietas
    del rango consultado o en todas, opcionalmente tambien en el maestro.

    Con 'solo_contar' devuelve unicamente el impacto, sin escribir nada.
    """
    if session.get('user_rol') not in ROLES_PRECIOS:
        return jsonify({'status': 'error', 'msg': 'No tiene permisos para corregir precios.'}), 403

    datos = request.get_json(silent=True) or {}

    try:
        materia_prima_id = int(datos.get('materia_prima_id'))
        precio = float(datos.get('precio'))
        iva = float(datos.get('iva') or 1)
        flete = float(datos.get('flete') or 0)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'Datos inválidos.'}), 400

    if precio < 0 or flete < 0 or iva < 1 or iva > 1.5:
        return jsonify({
            'status': 'error',
            'msg': 'Revise los valores: precio y flete no pueden ser negativos y el IVA debe estar entre 1 y 1,5.'
        }), 400

    alcance = 'todas' if datos.get('alcance') == 'todas' else 'rango'
    actualizar_maestro = bool(datos.get('maestro'))
    solo_contar = bool(datos.get('solo_contar'))
    motivo = (datos.get('motivo') or '').strip()[:200]
    desde = _fecha_o_hoy(datos.get('desde'))
    hasta = _fecha_o_hoy(datos.get('hasta'))
    if desde > hasta:
        desde, hasta = hasta, desde

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, nombre, precio_actual_kg, iva, flete
                FROM materias_primas WHERE id = %s
            """, (materia_prima_id,))
            materia = cur.fetchone()
            if not materia:
                return jsonify({'status': 'error', 'msg': 'Materia prima no encontrada.'}), 404

            if alcance == 'todas':
                condicion = "fd.materia_prima_id = %s"
                parametros = [materia_prima_id]
            else:
                condicion = ("fd.materia_prima_id = %s "
                             "AND fd.fecha_vencimiento BETWEEN %s AND %s")
                parametros = [materia_prima_id, desde, hasta]

            cur.execute(f"""
                SELECT fd.id, fd.item_id, fd.lote_id, fd.version,
                       fd.precio_guardado, fd.iva_guardado, fd.flete_guardado
                FROM formula_detalle fd
                WHERE {condicion}
            """, parametros)
            filas = cur.fetchall()

            # Insumos de ensayo del mismo producto (no viven en formula_detalle)
            if alcance == 'todas':
                condicion_ens = "e.materia_prima_id = %s AND e.eliminado_en IS NULL"
                parametros_ens = [materia_prima_id]
            else:
                condicion_ens = (
                    "e.materia_prima_id = %s AND e.eliminado_en IS NULL "
                    "AND EXISTS (SELECT 1 FROM formula_ensayo_rangos r "
                    "            WHERE r.ensayo_id = e.id "
                    "              AND r.desde <= %s AND r.hasta >= %s)"
                )
                parametros_ens = [materia_prima_id, hasta, desde]

            cur.execute(f"""
                SELECT e.id, e.item_id, e.lote_id,
                       e.precio_guardado, e.iva_guardado, e.flete_guardado
                FROM formula_ensayos e
                WHERE {condicion_ens}
            """, parametros_ens)
            ensayos = cur.fetchall()

            impacto = _resumen_impacto(filas)
            impacto.update(_resumen_ensayos(ensayos))
            impacto['materia'] = materia['nombre']

            if solo_contar:
                impacto.update({
                    'status': 'ok',
                    'precio_actual': float(materia['precio_actual_kg'] or 0),
                    'iva_actual': float(materia['iva'] or 1),
                    'flete_actual': float(materia['flete'] or 0),
                })
                return jsonify(impacto)

            if not filas and not ensayos and not actualizar_maestro:
                return jsonify({
                    'status': 'error',
                    'msg': 'No hay dietas ni ensayos para actualizar con ese alcance.'
                }), 400

            os.makedirs(CARPETA_RESPALDOS, exist_ok=True)
            marca = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_respaldo = f'ajuste_precio_{materia_prima_id}_{marca}.json'
            ruta_respaldo = os.path.join(CARPETA_RESPALDOS, nombre_respaldo)
            contenido = {
                'usuario_id': session.get('user_id'),
                'usuario_nombre': session.get('user_nombre'),
                'fecha': datetime.now().isoformat(timespec='seconds'),
                'materia_prima_id': materia_prima_id,
                'materia': materia['nombre'],
                'motivo': motivo,
                'alcance': alcance,
                'desde': str(desde),
                'hasta': str(hasta),
                'maestro': {
                    'actualizado': actualizar_maestro,
                    'precio': float(materia['precio_actual_kg'] or 0),
                    'iva': float(materia['iva'] or 1),
                    'flete': float(materia['flete'] or 0),
                },
                'filas': [{
                    'id': f['id'],
                    'item_id': f['item_id'],
                    'lote_id': f['lote_id'],
                    'version': f['version'],
                    'precio': float(f['precio_guardado']) if f['precio_guardado'] is not None else None,
                    'iva': float(f['iva_guardado']) if f['iva_guardado'] is not None else None,
                    'flete': float(f['flete_guardado']) if f['flete_guardado'] is not None else None,
                } for f in filas],
                'ensayos': [{
                    'id': e['id'],
                    'item_id': e['item_id'],
                    'lote_id': e['lote_id'],
                    'precio': float(e['precio_guardado']) if e['precio_guardado'] is not None else None,
                    'iva': float(e['iva_guardado']) if e['iva_guardado'] is not None else None,
                    'flete': float(e['flete_guardado']) if e['flete_guardado'] is not None else None,
                } for e in ensayos],
            }
            with open(ruta_respaldo, 'w', encoding='utf-8') as archivo:
                json.dump(contenido, archivo, indent=2, ensure_ascii=False)

            if filas:
                cur.executemany("""
                    UPDATE formula_detalle
                    SET precio_guardado = %s, iva_guardado = %s, flete_guardado = %s
                    WHERE id = %s
                """, [(precio, iva, flete, f['id']) for f in filas])

            if ensayos:
                cur.executemany("""
                    UPDATE formula_ensayos
                    SET precio_guardado = %s, iva_guardado = %s, flete_guardado = %s
                    WHERE id = %s
                """, [(precio, iva, flete, e['id']) for e in ensayos])

            if actualizar_maestro:
                cur.execute("""
                    UPDATE materias_primas
                    SET precio_actual_kg = %s, iva = %s, flete = %s,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (precio, iva, flete, materia_prima_id))

            registrar_cambio(
                session.get('user_id'),
                session.get('usuario_nombre') or session.get('user_nombre') or 'Sistema',
                'formula_detalle',
                materia_prima_id,
                f'precio_guardado x{impacto["filas"]} filas, x{len(ensayos)} ensayos',
                f"{float(materia['precio_actual_kg'] or 0):.2f}",
                f"{precio:.2f}" + (' (y maestro)' if actualizar_maestro else ''),
                'UPDATE',
                cur
            )

        conn.commit()
        impacto.update({
            'status': 'ok',
            'respaldo': nombre_respaldo,
            'maestro_actualizado': actualizar_maestro,
            'ensayos_actualizados': len(ensayos),
        })
        return jsonify(impacto)
    except Exception as e:
        conn.rollback()
        print(f"[ERROR AJUSTE PRECIO]: {e}")
        return jsonify({'status': 'error', 'msg': 'No se pudo guardar el ajuste.'}), 500
    finally:
        conn.close()


@planta_bp.route('/consolidado-precios/precio/deshacer', methods=['POST'])
@login_requerido
def consolidado_precio_deshacer():
    """Restaura los valores guardados en el respaldo de un ajuste de precio."""
    if session.get('user_rol') not in ROLES_PRECIOS:
        return jsonify({'status': 'error', 'msg': 'No tiene permisos para deshacer ajustes.'}), 403

    datos = request.get_json(silent=True) or {}
    nombre = os.path.basename(datos.get('respaldo') or '')
    if not (nombre.startswith('ajuste_precio_') and nombre.endswith('.json')):
        return jsonify({'status': 'error', 'msg': 'Respaldo no válido.'}), 400

    ruta = os.path.join(CARPETA_RESPALDOS, nombre)
    if not os.path.exists(ruta):
        return jsonify({'status': 'error', 'msg': 'No se encontró el respaldo.'}), 404

    with open(ruta, encoding='utf-8') as archivo:
        contenido = json.load(archivo)

    if (contenido.get('usuario_id') != session.get('user_id')
            and session.get('user_rol') != 'Superadmin'):
        return jsonify({'status': 'error', 'msg': 'Este ajuste lo hizo otro usuario.'}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            filas = contenido.get('filas') or []
            if filas:
                cur.executemany("""
                    UPDATE formula_detalle
                    SET precio_guardado = %s, iva_guardado = %s, flete_guardado = %s
                    WHERE id = %s
                """, [(f['precio'], f['iva'], f['flete'], f['id']) for f in filas])

            ensayos = contenido.get('ensayos') or []
            if ensayos:
                cur.executemany("""
                    UPDATE formula_ensayos
                    SET precio_guardado = %s, iva_guardado = %s, flete_guardado = %s
                    WHERE id = %s
                """, [(e['precio'], e['iva'], e['flete'], e['id']) for e in ensayos])

            maestro = contenido.get('maestro') or {}
            if maestro.get('actualizado'):
                cur.execute("""
                    UPDATE materias_primas
                    SET precio_actual_kg = %s, iva = %s, flete = %s,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (maestro['precio'], maestro['iva'], maestro['flete'],
                      contenido.get('materia_prima_id')))

            registrar_cambio(
                session.get('user_id'),
                session.get('user_nombre') or 'Sistema',
                'formula_detalle',
                contenido.get('materia_prima_id'),
                'precio_guardado (deshacer)',
                'ajuste',
                'valor anterior restaurado',
                'UPDATE',
                cur
            )

        conn.commit()
        return jsonify({'status': 'ok', 'filas': len(filas) + len(ensayos)})
    except Exception as e:
        conn.rollback()
        print(f"[ERROR DESHACER AJUSTE PRECIO]: {e}")
        return jsonify({'status': 'error', 'msg': 'No se pudo deshacer el ajuste.'}), 500
    finally:
        conn.close()



@planta_bp.route('/costos/por-dieta', methods=['GET'])
@login_requerido
def costos_por_dieta():
    """Lista las dietas de un lote con el detalle de costos de cada version."""
    lote = (request.args.get('lote') or '').strip()
    lotes = FormulaDetalle.lotes_con_formulas()

    if lote and lote not in lotes:
        lote = ''

    dietas = FormulaDetalle.costos_por_lote(lote) if lote else []

    # Agrupacion: Mes -> Dieta (item) -> Versiones
    grupos = []
    indice_mes = {}
    for d in dietas:
        vencimiento = d.get('fecha_vencimiento')
        clave_mes = vencimiento.strftime('%Y-%m') if vencimiento else 'sin-fecha'

        if clave_mes not in indice_mes:
            grupo = {
                'clave': clave_mes,
                'mes': d.get('mes') or 'Sin fecha',
                'dietas': [],
                'indice': {},
                'n_versiones': 0,
            }
            indice_mes[clave_mes] = grupo
            grupos.append(grupo)

        grupo = indice_mes[clave_mes]
        item = d['item_id']

        if item not in grupo['indice']:
            dieta_grupo = {
                'item_id': item,
                'nombre_dieta': d['nombre_dieta'],
                'versiones': [],
                'ultima_version': d['version'],
                'total_actual': d['total_iva_flete'],
                'n_versiones': 0,
            }
            grupo['indice'][item] = dieta_grupo
            grupo['dietas'].append(dieta_grupo)

        dieta_grupo = grupo['indice'][item]
        dieta_grupo['versiones'].append(d)
        dieta_grupo['n_versiones'] += 1
        grupo['n_versiones'] += 1

        if d['version'] >= dieta_grupo['ultima_version']:
            dieta_grupo['ultima_version'] = d['version']
            dieta_grupo['total_actual'] = d['total_iva_flete']

    for grupo in grupos:
        grupo['n_dietas'] = len(grupo['dietas'])
        for dieta_grupo in grupo['dietas']:
            dieta_grupo['versiones'].sort(key=lambda v: v['version'], reverse=True)

    return render_template(
        'planta_alimentos/costos_por_dieta.html',
        lotes=lotes,
        lote=lote,
        dietas=dietas,
        grupos=grupos
    )


@planta_bp.route('/consolidado-precios/dieta-costos', methods=['POST'])
@login_requerido
def consolidado_dieta_costos():
    """
    Guarda la maquila y el flete (por tonelada) de una dieta y lote concretos.

    - maquila_ton vacio o null: se usa la maquila de la empresa.
    - flete_ton: se suma solo en la columna PRECIO + FLETE.
    """
    if session.get('user_rol') not in ROLES_PRECIOS:
        return jsonify({'status': 'error', 'msg': 'No tiene permisos para modificar estos valores.'}), 403

    datos = request.get_json(silent=True) or {}

    try:
        item_id = int(datos.get('item_id'))
        version = int(datos.get('version'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'Datos inválidos.'}), 400

    lote_id = (datos.get('lote_id') or '').strip()
    if not lote_id:
        return jsonify({'status': 'error', 'msg': 'Falta el lote.'}), 400

    maquila_raw = datos.get('maquila_ton')
    if maquila_raw in (None, ''):
        maquila_ton = None
    else:
        try:
            maquila_ton = float(maquila_raw)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'msg': 'Maquila inválida.'}), 400
        if maquila_ton < 0:
            return jsonify({'status': 'error', 'msg': 'La maquila no puede ser negativa.'}), 400

    try:
        flete_ton = float(datos.get('flete_ton') or 0)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'Flete inválido.'}), 400

    if flete_ton < 0:
        return jsonify({'status': 'error', 'msg': 'El flete no puede ser negativo.'}), 400

    motivo = (datos.get('motivo') or '').strip()[:200]

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT maquila_ton, flete_ton
                FROM dieta_costos_extra
                WHERE item_id = %s AND lote_id = %s AND version = %s
            """, (item_id, lote_id, version))
            anterior = cur.fetchone()

            cur.execute("""
                INSERT INTO dieta_costos_extra
                    (item_id, lote_id, version, maquila_ton, flete_ton, usuario, actualizado_en)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (item_id, lote_id, version)
                DO UPDATE SET maquila_ton = EXCLUDED.maquila_ton,
                              flete_ton = EXCLUDED.flete_ton,
                              usuario = EXCLUDED.usuario,
                              actualizado_en = CURRENT_TIMESTAMP
            """, (item_id, lote_id, version, maquila_ton, flete_ton,
                  session.get('usuario_nombre') or session.get('user_nombre') or 'Sistema'))

            registrar_cambio(
                session.get('user_id'),
                session.get('usuario_nombre') or session.get('user_nombre') or 'Sistema',
                'dieta_costos_extra',
                item_id,
                f'maquila/flete {lote_id} v{version}',
                f"maquila={anterior[0] if anterior else 'empresa'} flete={anterior[1] if anterior else 0}",
                f"maquila={maquila_ton if maquila_ton is not None else 'empresa'} flete={flete_ton}",
                'UPDATE',
                cur
            )

        conn.commit()
        return jsonify({
            'status': 'ok',
            'maquila_ton': maquila_ton,
            'flete_ton': flete_ton,
            'motivo': motivo,
        })
    except Exception as e:
        conn.rollback()
        print(f"[ERROR DIETA COSTOS EXTRA]: {e}")
        return jsonify({'status': 'error', 'msg': 'No se pudo guardar el valor.'}), 500
    finally:
        conn.close()

@planta_bp.route('/revision-costos/<int:item_id>/<string:lote_id>', methods=['GET'])
@login_requerido
def revision_costos(item_id, lote_id):
    insumos = FormulaDetalle.obtener_costos_detallados(item_id, lote_id)
    
    # Variables para los totales
    nombre_dieta = insumos[0]['nombre_dieta'] if insumos else f"Dieta {item_id}"
    totales = {'cantidad': 0, 'c_iva': 0, 'c_flete': 0, 'c_iva_flete': 0}
    totales_sin_maquila = {'c_iva': 0, 'c_flete': 0, 'c_iva_flete': 0}

    for fila in insumos:
        cant = float(fila['cantidad'])
        precio = float(fila['precio'])
        iva_mult = float(fila['iva']) # Asumiendo que 1.00 es sin IVA extra
        flete = float(fila['flete'])

        # Las cantidades estan en gramos por tonelada y el precio en $/kg:
        # el total representa el costo de 1.000 toneladas (misma escala que Costos por dieta).
        costo_iva = cant * (precio * iva_mult)
        costo_flete = cant * (precio + flete)
        costo_iva_flete = cant * ((precio * iva_mult) + flete)

        # Guardamos en la fila para mostrarlos en la tabla
        fila['costo_iva'] = costo_iva
        fila['costo_flete'] = costo_flete
        fila['costo_iva_flete'] = costo_iva_flete

        # Sumamos a los totales generales
        totales['cantidad'] += cant
        totales['c_iva'] += costo_iva
        totales['c_flete'] += costo_flete
        totales['c_iva_flete'] += costo_iva_flete

        # Sumamos a los totales sin maquila si corresponde
        if not fila['es_maquila']:
            totales_sin_maquila['c_iva'] += costo_iva
            totales_sin_maquila['c_flete'] += costo_flete
            totales_sin_maquila['c_iva_flete'] += costo_iva_flete

    return render_template(
        'planta_alimentos/revision_costos.html',
        item_id=item_id,
        lote_id=lote_id,
        nombre_dieta=nombre_dieta,
        insumos=insumos,
        totales=totales,
        totales_sin_maquila=totales_sin_maquila
    )
    
    
@planta_bp.route('/consolidado-precios')
@login_requerido
def consolidado_precios():
    # 0. Rango de fechas consultado (por defecto hoy)
    def _fecha(valor):
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return hoy

    hoy = datetime.now().date()
    desde = _fecha(request.args.get('desde'))
    hasta = _fecha(request.args.get('hasta'))
    if desde > hasta:
        desde, hasta = hasta, desde

    # 1. Precios materias primas - separar destacadas vs otras.
    #    Si la fecha consultada no es hoy, se usan los precios congelados en las
    #    versiones de receta cuya fecha_vencimiento cae en el rango.
    #    Un solo dia (por ejemplo la vista "Hoy") = dietas y precios no vencidos ese dia.
    solo_vigentes = (desde == hasta)
    precios_historicos = FormulaDetalle.obtener_precios_historicos(desde, hasta, solo_vigentes)
    precios_mp_todas = []
    for mp in MateriaPrima.get_all():
        fila = dict(mp)
        historico = precios_historicos.get(fila['id'])
        fila['precio_historico'] = False
        if historico:
            precio = historico['precio']
            iva = historico['iva']
            flete = historico['flete']
            fila['precio_actual_kg'] = precio
            fila['iva'] = iva
            fila['flete'] = flete
            fila['p_iva'] = precio * iva
            fila['p_iva_flete'] = (precio * iva) + flete
            fila['precio_neto'] = precio
            fila['p_flete'] = precio + flete
            fila['precio_historico'] = True
        precios_mp_todas.append(fila)

    materias_destacadas = [mp for mp in precios_mp_todas if mp.get('destacada_en_consolidado')]
    materias_otras = [mp for mp in precios_mp_todas if not mp.get('destacada_en_consolidado')]

    # 2. Costos consolidados para el rango consultado
    costos_dietas = FormulaDetalle.obtener_consolidado_costos(desde, hasta, solo_vigentes)
    
    # 3. Filtrar en 3 grupos fijos por empresa
    EMPRESAS_ASIGNADAS = ('SAN MARTIN', 'COUNTRY', 'DOS CRESTAS SANTUARIO')
    dietas_san_martin = [d for d in costos_dietas if d['nombre_empresa'] == 'SAN MARTIN']
    dietas_country = [d for d in costos_dietas if d['nombre_empresa'] == 'COUNTRY']
    dietas_dos_crestas = [d for d in costos_dietas if d['nombre_empresa'] == 'DOS CRESTAS SANTUARIO']

    # 4. Dietas que no se pueden ubicar en ninguna empresa (se perderían en silencio)
    dietas_sin_asignar = [
        d for d in costos_dietas
        if (d.get('nombre_empresa') or '') not in EMPRESAS_ASIGNADAS
    ]

    return render_template(
        'planta_alimentos/consolidado_precios.html',
        materias_destacadas=materias_destacadas,
        materias_otras=materias_otras,
        dietas_san_martin=dietas_san_martin,
        dietas_country=dietas_country,
        dietas_dos_crestas=dietas_dos_crestas,
        dietas_sin_asignar=dietas_sin_asignar,
        desde=desde,
        hasta=hasta,
        es_hoy=(desde == hoy and hasta == hoy),
        solo_vigentes=solo_vigentes
    )


@planta_bp.route('/materia-prima/<int:mp_id>/toggle-destacada', methods=['POST'])
@login_requerido
def toggle_materia_destacada(mp_id):
    """Toggle materia prima como destacada en consolidado"""
    data = request.get_json(silent=True) or {}
    destacada = data.get('destacada', False)
    
    print(f"[DEBUG toggle] mp_id={mp_id}, destacada={destacada}, session_user={session.get('user_id')}")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE materias_primas SET destacada_en_consolidado = %s WHERE id = %s",
                (destacada, mp_id)
            )
            conn.commit()
        print(f"[DEBUG toggle] OK mp_id={mp_id}")
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error toggle destacada: {e}")
        return jsonify({'success': False, 'msg': str(e)}), 500
    finally:
        conn.close()