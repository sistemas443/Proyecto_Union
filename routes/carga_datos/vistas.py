from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from routes.routes import login_requerido
from models.lotes.services import get_lotes_distintos

carga_datos_bp = Blueprint('carga_datos', __name__)


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

    return render_template('generales/carga_datos.html', lotes=get_lotes_distintos())


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
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando diario: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"Error procesando el archivo diario: {e}", "danger")

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
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando semanal producción: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"Error procesando el archivo semanal: {e}", "danger")

    elif modulo_seleccionado == 'primera_semana':
        tabla_carga, contexto_carga = 'primera_semana', 'Carga Excel de primera semana'
        try:
            from models.primera_semana.services import procesar_excel_primera_semana
            exito, msj_resultado = procesar_excel_primera_semana(
                archivo, lote_seleccionado,
                usuario_id=session.get('user_id'),
                usuario_nombre=session.get('user_nombre', 'Desconocido')
            )
            if not exito:
                _registrar_fallo(tabla_carga, contexto_carga, msj_resultado, lote_seleccionado,
                                 session.get('user_id'), session.get('user_nombre'))
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando primera semana: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"Error procesando el archivo de primera semana: {e}", "danger")

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
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando semanal levante: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"Error procesando el archivo de levante: {e}", "danger")

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
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando clasificación: {e}")
            _registrar_fallo(tabla_carga, contexto_carga, f"{type(e).__name__}: {e}", lote_seleccionado,
                             session.get('user_id'), session.get('user_nombre'))
            flash(f"Error procesando el archivo de clasificación: {e}", "danger")

    else:
        flash(f"La carga para '{modulo_seleccionado}' aún no está programada.", "warning")

    return redirect(url_for('carga_datos.carga_datos_vista'), code=303)