from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from models.base import get_db_connection  
from models.cabecera.services import get_cabecera_info, update_cabecera_unificada
from models.diario.services import get_diario_all, update_registro_diario_field

# Importamos ÚNICAMENTE lo de Producción desde la carpeta semanal
from models.semanal.services import get_semanal_all, update_semanal_field as update_produccion_field

# Importamos lo de Primera Semana desde su nueva carpeta independiente
from models.primera_semana.services import get_primera_semana_by_lote, update_primera_semana_field

# Importamos lo de Levante de la nueva carpeta 'semanal_levante'
from models.semanal_levante.services import get_semanal_levante_all, update_semanal_field as update_levante_field

from models.clasificacion.services import get_clasificacion_all, update_clasificacion_field
from models.lotes.services import get_lotes_distintos, get_todos_los_lotes, guardar_nuevo_lote, actualizar_lote, borrar_lote, get_opciones_dinamicas

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/api/cabecera/actualizar', methods=['POST'])
def actualizar_cabecera():
    data = request.get_json(silent=True) or {}
    lote, columna, valor = data.get('lote'), data.get('columna'), data.get('valor')
    if not lote or not columna: return jsonify({'status': 'error', 'msg': 'Faltan datos'}), 400
    success, msg = update_cabecera_unificada(lote, columna, valor)
    return jsonify({'status': 'ok'}) if success else jsonify({'status': 'error', 'msg': msg}), 500

@bp.route('/diario', methods=['GET', 'POST'])
def diario():
    lote_seleccionado = request.form.get('lote', '') if request.method == 'POST' else ''
    filas = []
    cabecera = None
    
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        cabecera = get_cabecera_info(lote_seleccionado)
        if cabecera:
            from models.diario.services import generar_estructura_diario
            generar_estructura_diario(lote_seleccionado, cabecera.get('id'), cabecera.get('fecha_recepcion'))
        filas = get_diario_all(lote_seleccionado)
        
    return render_template('diario.html', 
                           filas=filas, 
                           lotes=get_lotes_distintos(), 
                           lote_seleccionado=lote_seleccionado, 
                           cabecera=cabecera)
    
@bp.route('/primera-semana', methods=['GET', 'POST'])
def primera_semana():
    lote_seleccionado = request.form.get('lote', '') if request.method == 'POST' else ''
    filas = []
    cabecera = None
    
    if lote_seleccionado and lote_seleccionado != 'VACIO':
        cabecera = get_cabecera_info(lote_seleccionado)
        filas = get_primera_semana_by_lote(lote_seleccionado)
        
        print(f"\n[CONTROL WEB] Lote: {lote_seleccionado} | ID: {cabecera.get('id') if cabecera else 'None'}")
        print(f"[CONTROL WEB] Cantidad de filas devueltas por el servicio semanal: {len(filas)}")
        
    return render_template('primera_semana.html', 
                           filas=filas, 
                           lotes=get_lotes_distintos(), 
                           lote_seleccionado=lote_seleccionado, 
                           cabecera=cabecera)
    
@bp.route('/api/primera-semana/actualizar', methods=['POST'])
def actualizar_primera_semana():
    data = request.get_json(silent=True) or {}
    id_reg = data.get('id')
    columna = data.get('columna', '').strip()
    valor = data.get('valor', '')

    if not id_reg or not columna: 
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400

    try:
        # Ya la tienes importada arriba, así que solo llamamos a la función
        success, campos_actualizados, msg = update_primera_semana_field(int(id_reg), columna, valor)
        
        if success:
            return jsonify({'status': 'ok', 'updated_data': campos_actualizados})
        else:
            return jsonify({'status': 'error', 'msg': msg}), 400
    except Exception as e: 
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    
@bp.route('/api/diario/actualizar', methods=['POST'])
def actualizar_diario():
    data = request.get_json(silent=True) or {}
    id_reg = data.get('id')
    columna = data.get('columna', '').strip()
    valor = data.get('valor', '')
    
    if not id_reg or not columna: 
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
        
    try:
        # Ejecutamos el guardado en el servicio del Diario
        resultado = update_registro_diario_field(int(id_reg), columna, valor)
        
        # Validamos cómo responde el servicio (si devuelve 2 o 3 valores)
        if isinstance(resultado, tuple) and len(resultado) == 3:
            success, campos_on_time, msg = resultado
        elif isinstance(resultado, tuple) and len(resultado) == 2:
            success, campos_on_time = resultado
            msg = "El dato fue rechazado por la base de datos."
        else:
            success = resultado
            campos_on_time = {}
            msg = "Error desconocido al procesar el guardado."
            
        if success:
            return jsonify({'status': 'ok', 'updated_data': campos_on_time})
        else:
            # Aquí está la magia: ¡Ahora sí enviamos el mensaje de error!
            return jsonify({'status': 'error', 'msg': msg}), 400
            
    except Exception as e: 
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@bp.route('/semanal', methods=['GET', 'POST'])
def semanal():
    lote_seleccionado = request.form.get('lote', '') if request.method == 'POST' else ''
    return render_template('semanal.html', filas=get_semanal_all(lote_seleccionado), lotes=get_lotes_distintos(), lote_seleccionado=lote_seleccionado, cabecera=get_cabecera_info(lote_seleccionado))

@bp.route('/semanal-levante', methods=['GET', 'POST'])
def semanal_levante():
    lote_seleccionado = request.form.get('lote', '') if request.method == 'POST' else ''
    return render_template('sem_lev.html', filas=get_semanal_levante_all(lote_seleccionado), lotes=get_lotes_distintos(), lote_seleccionado=lote_seleccionado, cabecera=get_cabecera_info(lote_seleccionado))

@bp.route('/api/semanal/actualizar', methods=['POST'])
def actualizar_semanal():
    data = request.get_json(silent=True) or {}
    id_reg, columna, valor = data.get('id'), data.get('columna', '').strip(), data.get('valor', '')
    pantalla = data.get('pantalla', 'produccion') 
    
    if not id_reg or not columna: 
        return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
        
    try:
        if pantalla == 'levante':
            ok, campos_actualizados, msg = update_levante_field(int(id_reg), columna, valor)
        else:
            ok, campos_actualizados, msg = update_produccion_field(int(id_reg), columna, valor)

        if ok:
            return jsonify({'status': 'ok', 'updated_data': campos_actualizados})
        else:
            return jsonify({'status': 'error', 'msg': f"Error en Base de Datos: {msg}"}), 400
    except Exception as e: 
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@bp.route('/clasificacion-produccion', methods=['GET', 'POST'])
def clas_prod():
    lote_seleccionado = request.form.get('lote', '') if request.method == 'POST' else ''
    return render_template('clas_prod.html', filas=get_clasificacion_all(lote_seleccionado), lotes=get_lotes_distintos(), lote_seleccionado=lote_seleccionado, cabecera=get_cabecera_info(lote_seleccionado))

@bp.route('/api/clasificacion/actualizar', methods=['POST'])
def actualizar_clasificacion():
    data = request.get_json(silent=True) or {}
    id_reg, columna, valor = data.get('id'), data.get('columna', '').strip(), data.get('valor', '')
    if not id_reg or not columna: return jsonify({'status': 'error', 'msg': 'Parámetros incompletos'}), 400
    try:
        ok = update_clasificacion_field(int(id_reg), columna, valor)
        return jsonify({'status': 'ok'}) if ok else jsonify({'status': 'error', 'msg': 'Error BD'}), 400
    except Exception as e: return jsonify({'status': 'error', 'msg': str(e)}), 500

@bp.route('/lotes')
def vista_lotes():
    return render_template('lotes.html', lotes=get_todos_los_lotes(), opciones=get_opciones_dinamicas())

@bp.route('/guardar-lote', methods=['POST'])
def guardar_lote():
    datos = request.form.to_dict()
    id_lote = request.form.get('id')
    
    # Ejecutamos el guardado o actualización
    success, msg = actualizar_lote(id_lote, datos) if id_lote else guardar_nuevo_lote(datos)
    
    if not success: 
        # Disparamos la alerta de SweetAlert2 con la categoría 'error'
        flash(msg, "error")
        # Recargamos la misma pantalla para no sacar al usuario
        return redirect(url_for('main.vista_lotes'))
    
    # Si todo sale perfecto, disparamos una alerta de éxito
    flash(msg, "success")
    return redirect(url_for('main.vista_lotes'))

@bp.route('/api/borrar-lote/<int:id>', methods=['POST'])
def api_borrar_lote(id):
    return jsonify({'status': 'ok'}) if borrar_lote(id) else jsonify({'status': 'error', 'msg': 'No se pudo borrar'}), 500

@bp.route('/arreglar-decimales')
def arreglar_decimales():
    from models.base import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Convertimos las columnas a formato NUMERIC con 1 decimal
        cur.execute("ALTER TABLE primera_semana ALTER COLUMN unif_10_menos TYPE NUMERIC(10,1);")
        cur.execute("ALTER TABLE primera_semana ALTER COLUMN unif_10_mas TYPE NUMERIC(10,1);")
        conn.commit()
        return "<h1>¡ÉXITO!</h1><p>Las columnas de 10% menos y 10% más ahora aceptan decimales en la base de datos.</p>"
    except Exception as e:
        conn.rollback()
        return f"<h1>Hubo un problema o ya estaban arregladas:</h1><p>{str(e)}</p>"
    finally:
        cur.close()
        conn.close()

@bp.route('/agregar-peso-real')
def agregar_peso_real():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE bd_vargas ADD COLUMN peso_real NUMERIC(10,2);")
        conn.commit()
        return "<h1>¡ÉXITO!</h1><p>La columna 'peso_real' fue agregada correctamente a bd_vargas.</p>"
    except Exception as e:
        conn.rollback()
        return f"<h1>Hubo un problema:</h1><p>{str(e)}</p>"
    finally:
        cur.close()
        conn.close()