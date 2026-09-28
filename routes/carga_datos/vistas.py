from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from routes.routes import login_requerido
from models.lotes.services import get_lotes_distintos

carga_datos_bp = Blueprint('carga_datos', __name__)


@carga_datos_bp.route('/carga-datos', methods=['GET'])
@login_requerido
def carga_datos_vista():
    if session.get('user_rol') != 'Superadmin':
        return "Acceso denegado. Solo Superadmin.", 403

    return render_template('carga_datos.html', lotes=get_lotes_distintos())


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
        try:
            from models.diario.services import procesar_excel_diario
            exito, msj_resultado = procesar_excel_diario(archivo, lote_seleccionado)
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando diario: {e}")
            flash(f"Error procesando el archivo diario: {e}", "danger")

    elif modulo_seleccionado == 'semanal_prod':
        try:
            from models.semanal.services import procesar_excel_semanal_produccion
            exito, msj_resultado = procesar_excel_semanal_produccion(archivo, lote_seleccionado)
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando semanal producción: {e}")
            flash(f"Error procesando el archivo semanal: {e}", "danger")

    elif modulo_seleccionado == 'primera_semana':
        try:
            from models.primera_semana.services import procesar_excel_primera_semana
            exito, msj_resultado = procesar_excel_primera_semana(archivo, lote_seleccionado)
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando primera semana: {e}")
            flash(f"Error procesando el archivo de primera semana: {e}", "danger")

    elif modulo_seleccionado == 'semanal_levante':
        try:
            from models.semanal_levante.services import procesar_excel_semanal_levante
            exito, msj_resultado = procesar_excel_semanal_levante(archivo, lote_seleccionado)
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando semanal levante: {e}")
            flash(f"Error procesando el archivo de levante: {e}", "danger")

    elif modulo_seleccionado == 'clasificacion':
        try:
            from models.clasificacion.services import procesar_excel_clasificacion
            exito, msj_resultado = procesar_excel_clasificacion(archivo, lote_seleccionado)
            flash(msj_resultado, "success" if exito else "danger")
        except Exception as e:
            print(f"Error procesando clasificación: {e}")
            flash(f"Error procesando el archivo de clasificación: {e}", "danger")

    else:
        flash(f"La carga para '{modulo_seleccionado}' aún no está programada.", "warning")

    return redirect(url_for('carga_datos.carga_datos_vista'), code=303)