from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from routes.routes import login_requerido
from models.base import traducir_error, get_db_connection
from models.lotes.services import get_lotes_distintos

carga_datos_bp = Blueprint('carga_datos', __name__)


def _lotes_con_dia2():
    """Lotes que ya tienen generada la tabla del Día 2 de Primera Semana."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT lote FROM primera_semana_dia2 ORDER BY lote")
        return [fila[0] for fila in cur.fetchall()]
    except Exception as e:
        print(f"[ERROR CONSULTANDO LOTES DÍA 2]: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def _registrar_fallo(tabla, contexto, mensaje, lote_nombre=None, usuario_id=None, usuario_nombre=None):
    """
    Guarda un fallo de carga en el historial de auditoría con la acción ERROR.
    Nunca rompe la respuesta al usuario: si falla el registro, solo imprime el aviso.
    """
    try:
        from models.auditoria.services import registrar_error
        id_lote = None
        if lote_nombre:
            from models.cabecera.model import fetch_cabecera_by_lote
            cabecera = fetch_cabecera_by_lote(lote_nombre)
            id_lote = cabecera.get('id') if cabecera else None

        registrar_error(
            tabla=tabla,
            contexto=contexto,
            mensaje=mensaje,
            id_lote=id_lote,
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre,
        )
    except Exception as e:
        print(f"[ERROR REGISTRANDO FALLO DE CARGA]: {e}")


@carga_datos_bp.route('/carga-datos', methods=['GET'])
@login_requerido
def carga_datos_vista():
    if session.get('user_rol') != 'Superadmin':
        return "Acceso denegado. Solo Superadmin.", 403

    return render_template('generales/carga_datos.html', lotes=get_lotes_distintos(),
                           lotes_con_dia2=_lotes_con_dia2())


@carga_datos_bp.route('/api-subir-excel', methods=['POST'])
@login_requerido
def procesar_carga():
    if session.get('user_rol') != 'Superadmin':
        return "Acceso denegado. Solo Superadmin.", 403

    modulo_seleccionado = request.form.get('modulo')
    archivo = request.files.get('archivo_excel')
    lote_seleccionado = request.form.get('lote')

    if not modulo_seleccionado:
        flash("Por favor, selecciona el tipo de informe.", "danger")
        return redirect(url_for('carga_datos.carga_datos_vista'), code=303)

    if not archivo or archivo.filename == '':
        flash("Por favor, selecciona un archivo Excel válido.", "danger")
        return redirect(url_for('carga_datos.carga_datos_vista'), code=303)

    extension = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
    if extension not in ('xlsx', 'xlsm', 'xls'):
        flash("El archivo debe ser de Excel (.xlsx, .xlsm o .xls).", "danger")
        return redirect(url_for('carga_datos.carga_datos_vista'), code=303)

    if not lote_seleccionado:
        flash("Selecciona el lote al que pertenece el archivo.", "danger")
        return redirect(url_for('carga_datos.carga_datos_vista'), code=303)

    # Candado de seguridad: el lote dentro del Excel debe coincidir con el seleccionado.
    try:
        from models.carga_datos.validador import validar_lote_archivo
        ok_lote, msg_lote, lote_detectado = validar_lote_archivo(
            archivo, lote_seleccionado, modulo_seleccionado
        )
    except Exception as e:
        ok_lote = False
        msg_lote = f"No se pudo verificar el lote del archivo: {e}"
        lote_detectado = None

    # El validador consume el stream del archivo; lo devolvemos al inicio para la importación.
    try:
        archivo.stream.seek(0)
    except Exception:
        pass

    if not ok_lote:
        _registrar_fallo(
            'carga_datos', 'Validación de lote', msg_lote, lote_seleccionado,
            session.get('user_id'), session.get('user_nombre')
        )
        flash(msg_lote, "danger")
        return redirect(url_for('carga_datos.carga_datos_vista'), code=303)

    if modulo_seleccionado == 'diario':
        tabla_carga, contexto_carga = 'data_diario', 'Carga Excel de diario'
        try:
            from models.diario.services import procesar_excel_diario
            exito, msj_resultado = procesar_excel_diario(
                archivo, lote_seleccionado,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido')
            )
            if not exito:
                _registrar_fallo(tabla_carga, contexto_carga, msj_resultado, lote_seleccionado,
                                 session.get('user_id'), session.get('user_nombre'))
            flash(traducir_error(msj_resultado), "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando diario: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"No se pudo cargar el archivo de diario. {traducir_error(str(e))}", "danger")

    elif modulo_seleccionado == 'semanal_prod':
        tabla_carga, contexto_carga = 'bd_vargas', 'Carga Excel de producción'
        try:
            from models.semanal.services import procesar_excel_semanal_produccion
            exito, msj_resultado = procesar_excel_semanal_produccion(
                archivo, lote_seleccionado,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido')
            )
            if not exito:
                _registrar_fallo(tabla_carga, contexto_carga, msj_resultado, lote_seleccionado,
                                 session.get('user_id'), session.get('user_nombre'))
            flash(traducir_error(msj_resultado), "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando semanal producción: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"No se pudo cargar el archivo de producción semanal. {traducir_error(str(e))}", "danger")

    elif modulo_seleccionado == 'primera_semana':
        es_dia2 = request.form.get('tabla_dia') == 'dia2'
        tabla_carga = 'primera_semana_dia2' if es_dia2 else 'primera_semana'
        contexto_carga = ('Carga Excel de primera semana (Día 2)' if es_dia2
                          else 'Carga Excel de primera semana')
        try:
            from models.primera_semana.services import procesar_excel_primera_semana
            exito, msj_resultado = procesar_excel_primera_semana(
                archivo, lote_seleccionado,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido'),
                dia2=es_dia2,
            )
            if not exito:
                _registrar_fallo(tabla_carga, contexto_carga, msj_resultado, lote_seleccionado,
                                 session.get('user_id'), session.get('user_nombre'))
            flash(traducir_error(msj_resultado), "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando primera semana: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"No se pudo cargar el archivo de primera semana. {traducir_error(str(e))}", "danger")

    elif modulo_seleccionado == 'semanal_levante':
        tabla_carga, contexto_carga = 'semanal_levante', 'Carga Excel de semanal levante'
        try:
            from models.semanal_levante.services import procesar_excel_semanal_levante
            exito, msj_resultado = procesar_excel_semanal_levante(
                archivo, lote_seleccionado,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido')
            )
            if not exito:
                _registrar_fallo(tabla_carga, contexto_carga, msj_resultado, lote_seleccionado,
                                 session.get('user_id'), session.get('user_nombre'))
            flash(traducir_error(msj_resultado), "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando semanal levante: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"No se pudo cargar el archivo de semanal levante. {traducir_error(str(e))}", "danger")

    elif modulo_seleccionado == 'clasificacion':
        tabla_carga, contexto_carga = 'clasificacion_produccion', 'Carga Excel de clasificación'
        try:
            from models.clasificacion.services import procesar_excel_clasificacion
            exito, msj_resultado = procesar_excel_clasificacion(
                archivo, lote_seleccionado,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido')
            )
            if not exito:
                _registrar_fallo(tabla_carga, contexto_carga, msj_resultado, lote_seleccionado,
                                 session.get('user_id'), session.get('user_nombre'))
            flash(traducir_error(msj_resultado), "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando clasificación: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"No se pudo cargar el archivo de clasificación. {traducir_error(str(e))}", "danger")

    else:
        flash(f"La carga para '{modulo_seleccionado}' aún no está programada.", "warning")

    return redirect(url_for('carga_datos.carga_datos_vista'), code=303)