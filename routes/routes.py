import os
import time
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps

from models.base import get_db_connection, obtener_hash_git
from models.auditoria.services import (
    obtener_historial, 
    contar_historial,
    obtener_historial_filtrado,
    contar_historial_filtrado,
    obtener_opciones_filtros,
    obtener_campos_por_tabla
)

# Registramos este archivo como un componente (Blueprint) principal de Flask
bp = Blueprint('main', __name__)

# MIDDLEWARES (CANDADOS DE SEGURIDAD PARA LAS RUTAS)

def login_requerido(f):
    # Candado que verifica si el usuario tiene una sesión en su navegador antes de cargar una pantalla
    @wraps(f)
    def decorated_function(*args, **kwargs): # Si no hay sesión activa, bloquea el acceso a la función
        if 'user_id' not in session: # Si no hay sesión activa, bloquea el acceso a la función
            # Si la petición es interna (API AJAX), devuelve un error estructurado JSON
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'msg': 'Sesión expirada o no autorizada. Inicie sesión nuevamente.'}), 401
            # Si es una carga de pantalla normal, redirige al usuario a la página de inicio
            flash("Debes iniciar sesión para acceder a esta página.", "warning")
            return redirect(url_for('main.login_page'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_requerido(f):
    # Candado de acceso exclusivo para las configuraciones críticas (Creación de usuarios y roles)
    @wraps(f)
    def decorated_function(*args, **kwargs): # Si el rol del usuario no es Superadmin, bloquea el acceso a la función
        if session.get('user_rol') != 'Superadmin': # Si el rol del usuario no es Superadmin, bloquea el acceso
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'msg': 'No tienes permisos para realizar esta acción.'}), 403 # Si es una petición API, devuelve un error JSON
            flash("Acceso denegado. Esta área es exclusiva para Superadministradores.", "error")
            return redirect(url_for('main.login_page')) # Si es una carga de pantalla normal, redirige al usuario a la vista principal de lotes
        return f(*args, **kwargs)
    return decorated_function

def editor_requerido(f):
    # Candado que bloquea cualquier intento de guardar, editar o borrar información si el rol es 'Lector'
    @wraps(f)
    def decorated_function(*args, **kwargs): # Si el rol del usuario es Lector, bloquea el acceso a la función
        if session.get('user_rol') == 'Lector': # Si el rol del usuario es Lector, bloquea el acceso a la función
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'msg': 'Modo Lectura: No tienes permisos para modificar datos.'}), 403
            flash("Acceso denegado. Solo tienes permisos de lectura.", "error") # Si es una carga de pantalla normal, redirige al usuario a la vista principal de lotes
            return redirect(request.referrer or url_for('lotes.vista_lotes'))
        return f(*args, **kwargs) # Si el rol es Editor o Superadmin, permite el acceso a la función
    return decorated_function

# ESCUDO ANTI FUERZA-BRUTA (MEMORIA RAM)
intentos_ip = {}

def limitar_intentos(f):
    # Bloquea la dirección IP de quien intente ingresar o solicitar datos erróneos más de 5 veces en 60 segundos
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip_cliente = request.remote_addr # Obtiene la dirección IP del cliente que realiza la petición
        tiempo_actual = time.time()
        ventana_tiempo = 60 # Tiempo de penalización configurado en segundos
        max_intentos = 5 # Margen de error tolerado

        # Inicia el conteo para IPs desconocidas
        if ip_cliente not in intentos_ip:
            intentos_ip[ip_cliente] = []

        # Purgado automático: borra del registro los intentos que ocurrieron hace más de 1 minuto
        intentos_ip[ip_cliente] = [t for t in intentos_ip[ip_cliente] if tiempo_actual - t < ventana_tiempo]

        # Bloquea la petición si el límite fue alcanzado y muestra advertencia
        if len(intentos_ip[ip_cliente]) >= max_intentos:
            flash("Demasiados intentos detectados. Por seguridad, espera 1 minuto antes de volver a intentar.", "error")
            return redirect(url_for('main.pantalla_principal'))

        # Almacena el timestamp de este intento válido y permite el paso
        intentos_ip[ip_cliente].append(tiempo_actual)
        return f(*args, **kwargs)
    return decorated_function

# RUTAS DE AUTENTICACIÓN (LOGIN, RECUPERACIÓN Y LOGOUT)
@bp.route('/login', methods=['POST'])
@limitar_intentos
def login():
    # Sanitiza el nombre de usuario de inmediato: remueve espacios periféricos, espacios internos y lo pasa a minúsculas
    username = request.form.get('username', '').strip().replace(" ", "").lower()
    # La contraseña viaja intacta, respetando estrictamente su formato original (mayúsculas y caracteres)
    password = request.form.get('password')

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Extrae los credenciales de la base de datos junto con el rol e imagen del usuario
        cur.execute("""
            SELECT u.id, u.nombre_completo, u.password_hash, u.activo, r.nombre, u.foto_perfil
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.username = %s
        """, (username,))
        usuario = cur.fetchone()

        # Valida que el usuario exista y que el texto plano de la clave coincida con el hash encriptado
        if usuario and check_password_hash(usuario[2], password):
            # Rechaza el acceso si un Superadmin desactivó (Soft Delete) esta cuenta
            if not usuario[3]:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "error")
                return redirect(url_for('main.pantalla_principal'))
            else:
                # Inyecta las variables esenciales de autorización y diseño en las cookies encriptadas de la sesión
                session['user_id'] = usuario[0] # ID único del usuario en la base de datos
                session['user_nombre'] = usuario[1] # Nombre completo del usuario (para mostrar en la interfaz)
                session['user_rol'] = usuario[4] # Nombre del rol (Superadmin, Editor, Lector)
                session['user_foto'] = usuario[5] or ''  # Nombre del archivo de la foto de perfil (si existe) o cadena vacía

                # Mensaje de bienvenida con imagen incrustada
                img_url = url_for('static', filename='img/Saludo.gif')
                flash(f'<img src="{img_url}" style="vertical-align: middle; height: 55px; width: auto;"> ¡Bienvenido, {usuario[1]}!', 'success')

                return redirect(url_for('main.pantalla_principal'))
        else:
            # Respuesta unificada y ambigua para prevenir que descubran si el error fue el correo o la clave
            flash("Usuario o contraseña incorrectos.", "error")

    except Exception as e:
        # Fuga de datos prevenida: El error SQL se imprime en el servidor y al usuario se le da un texto limpio
        print(f"[ERROR DE AUTENTICACIÓN]: {e}")
        flash("Se produjo un error de conexión con el sistema.", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('main.login_page'))

@bp.route('/solicitar-recuperacion', methods=['POST'])
@limitar_intentos
def solicitar_recuperacion():
    # Sanitización de variables provenientes de la petición POST del modal
    username = request.form.get('username_recuperar', '').strip().replace(" ", "").lower()

    if not username: # Si el campo de usuario está vacío, no se procesa la solicitud y se devuelve un mensaje de advertencia
        flash("Por favor ingresa un nombre de usuario.", "warning")
        return redirect(url_for('main.login_page'))

    conn = get_db_connection() # Creamos la conexión a la base de datos para verificar si el usuario existe y enviar la notificación al administrador
    cur = conn.cursor()

    try:
        # Traemos el nombre y también el estado (activo/inactivo)
        cur.execute("SELECT nombre_completo, activo FROM usuarios WHERE username = %s", (username,))
        usuario = cur.fetchone()

        if usuario:
            nombre_real = usuario[0]
            esta_activo = usuario[1]

            # Si el usuario está desactivado, lanzamos una alerta de error directa y cortamos el proceso
            if not esta_activo:
                flash("Tu cuenta se encuentra desactivada. Contacta directamente al administrador.", "error")
                return redirect(request.referrer or url_for('main.login_page'))

            # Constantes de configuración del servidor de correo emisor corporativo
            correo_remitente = "sistemas@avicolasanmartin.com" #correo que envía la notificación al administrador
            password_remitente = "veusvqztzlfcyatw"  #Clave de aplicación generada en Google Workspace para SMTP (no es la contraseña de la cuenta)
            correo_administrador = "sistemas@avicolasanmartin.com" #correo que se encarga de recuperar las cuentas

            # Configuración del servidor SMTP
            smtp_server = 'smtp.gmail.com' #Servidor SMTP de Google Workspace
            smtp_port = 587 #Puerto de conexión seguro para TLS

            # Estructura de cabeceras y cuerpo plano del correo electrónico
            asunto = f"ALERTA: Solicitud de restablecimiento - {nombre_real}"
            cuerpo = f"""
            El usuario ha solicitado un restablecimiento de contraseña.

            Datos de la solicitud:
            - Nombre Completo: {nombre_real}
            - Usuario (Login): {username}

            Por favor, ingresa al Panel de Usuarios de Avícola San Martín para asignarle una nueva contraseña.
            """

            msg = MIMEMultipart()
            msg['From'] = correo_remitente
            msg['To'] = correo_administrador
            msg['Subject'] = asunto
            msg.attach(MIMEText(cuerpo, 'plain'))

            # Transmisión segura con protocolo TLS hacia Google Workspace
            try:
                server = smtplib.SMTP(smtp_server, smtp_port) # Inicia la conexión con el servidor SMTP
                server.starttls() # Activa el modo de cifrado TLS para proteger la transmisión de datos
                server.login(correo_remitente, password_remitente) # Inicia sesión en el servidor SMTP con las credenciales del remitente
                server.send_message(msg)# Envía el correo electrónico al administrador con la solicitud de recuperación
                server.quit()# Cierra la conexión con el servidor SMTP después de enviar el correo
                flash("Solicitud enviada exitosamente. El administrador ha sido notificado.", "success")
            except Exception as e: # Captura cualquier error durante el envío del correo y lo imprime en la consola del servidor para depuración
                print("Error enviando correo:", e)
                flash("Error de conexión al enviar el correo. Por favor contacta al administrador.", "error")
        else:
            # Ahora decimos explícitamente si falló
            flash("El usuario ingresado no existe en el sistema.", "error")
            return redirect(url_for('main.login_page'))

    except Exception as e:
        print(f"[ERROR RECUPERACION]: {e}")
        flash("Se produjo un error de conexión con el sistema.", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(request.referrer or url_for('main.login_page'))

@bp.route('/solicitar-pin', methods=['POST'])
@limitar_intentos
def solicitar_pin():
    username = request.form.get('username_pin', '').strip().replace(" ", "").lower()

    if not username:
        flash("Por favor ingresa tu usuario.", "warning")
        return redirect(url_for('main.login_page'))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Buscamos al usuario, verificando que tenga correo y esté activo
        cur.execute("SELECT nombre_completo, correo, activo FROM usuarios WHERE username = %s", (username,))
        usuario = cur.fetchone()

        if usuario:
            nombre_real = usuario[0]
            correo_usuario = usuario[1]
            esta_activo = usuario[2]

            if not esta_activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "error")
                return redirect(url_for('main.login_page'))

            if not correo_usuario:
                flash("No tienes un correo registrado. Usa la opción de contactar al administrador.", "error")
                return redirect(url_for('main.login_page'))

            # Generamos un PIN secreto de 6 dígitos
            pin_secreto = str(random.randint(100000, 999999))

            # Guardamos el PIN y el usuario temporalmente en la sesión del navegador
            session['reset_user'] = username
            session['reset_pin'] = pin_secreto
            session['reset_time'] = time.time()

            # --- ENVÍO DEL CORREO AL USUARIO ---
            correo_remitente = "sistemas@avicolasanmartin.com"
            password_remitente = "veusvqztzlfcyatw"

            smtp_server = 'smtp.gmail.com'
            smtp_port = 587

            asunto = "Tu Código de Recuperación - Avícola San Martín"
            cuerpo = f"""
            Hola {nombre_real},

            Has solicitado restablecer tu contraseña. Tu código de seguridad (PIN) es:

            {pin_secreto}

            ⚠️ Este código tiene una validez de 15 minutos. Si el tiempo expira, deberás solicitar uno nuevo.

            Si no fuiste tú quien solicitó este cambio, por favor ignora este mensaje y avisa a soporte.
            """

            msg = MIMEMultipart()
            msg['From'] = correo_remitente
            msg['To'] = correo_usuario
            msg['Subject'] = asunto
            msg.attach(MIMEText(cuerpo, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(correo_remitente, password_remitente)
            server.send_message(msg)
            server.quit()

            flash("Te hemos enviado un código de 6 dígitos a tu correo.", "success")
            # Lo enviaremos a una nueva pantalla para que escriba el PIN
            return redirect(url_for('main.verificar_pin_page'))

        else:
            flash("El usuario ingresado no existe en el sistema.", "error")
            return redirect(url_for('main.login_page'))

    except Exception as e:
        print(f"[ERROR PIN]: {e}")
        flash("Error del servidor al intentar enviar el correo.", "error")
        return redirect(url_for('main.login_page'))
    finally:
        cur.close()
        conn.close()

# RUTA PARA MOSTRAR LA PANTALLA DONDE SE ESCRIBE EL PIN
@bp.route('/verificar-pin')
def verificar_pin_page():
    if 'reset_pin' not in session or 'reset_user' not in session:
        flash("Tu sesión de recuperación expiró. Vuelve a intentarlo.", "warning")
        return redirect(url_for('main.login_page'))

    # Calculamos el tiempo restante en segundos
    tiempo_creacion = session.get('reset_time', 0)
    tiempo_transcurrido = time.time() - tiempo_creacion
    tiempo_restante = int(900 - tiempo_transcurrido) # 900 seg = 15 min

    # Si el tiempo ya se acabó, destruimos todo automáticamente
    if tiempo_restante <= 0:
        return redirect(url_for('main.cancelar_recuperacion'))

    # Le pasamos el tiempo restante al HTML
    return render_template('auth/verificar_pin.html', tiempo_restante=tiempo_restante)

# 2. VALIDAR ÚNICAMENTE EL PIN (PASO 1)
@bp.route('/validar-pin', methods=['POST'])
@limitar_intentos
def validar_pin():
    if 'reset_pin' not in session or 'reset_user' not in session:
        flash("Tu sesión de recuperación expiró.", "warning")
        return redirect(url_for('main.login_page'))

    pin_ingresado = request.form.get('pin', '').strip()

    # Control de tiempo de expiración del PIN (15 minutos)
    tiempo_creacion = session.get('reset_time', 0)
    if time.time() - tiempo_creacion > 900: # 15 minutos en segundos
        session.pop('reset_pin', None) # Limpiamos el PIN de la sesión
        session.pop('reset_user', None)
        session.pop('reset_time', None)
        flash("El código ha expirado por seguridad (Límite de 15 minutos). Solicita uno nuevo.", "error")
        return redirect(url_for('main.login_page'))

    # Control de intentos fallidos del PIN en la sesión
    intentos = session.get('pin_intentos', 0)

    if pin_ingresado != session['reset_pin']:
        intentos += 1
        session['pin_intentos'] = intentos

        # Límite de seguridad: Máximo 3 intentos erróneos
        if intentos >= 3:
            session.pop('reset_pin', None)
            session.pop('reset_user', None)
            session.pop('pin_intentos', None)
            flash("Has superado el límite de 3 intentos fallidos. Solicita un nuevo código.", "error")
            return redirect(url_for('main.login_page'))

        intentos_restantes = 3 - intentos
        flash(f"Código incorrecto. Te quedan {intentos_restantes} intento(s).", "error")
        return redirect(url_for('main.verificar_pin_page'))

    # Si el PIN es correcto, marcamos la sesión como "Verificada"
    session['pin_verificado'] = True
    session.pop('pin_intentos', None)
    flash("¡Código verificado con éxito! Ingresa tu nueva contraseña.", "success")
    return redirect(url_for('main.verificar_pin_page'))

# 3. GUARDAR LA NUEVA CONTRASEÑA (PASO 2)
@bp.route('/cambiar-clave-pin', methods=['POST'])
@limitar_intentos
def cambiar_clave_pin():
    # Validamos que el PIN haya sido verificado exitosamente en el paso anterior
    if not session.get('pin_verificado') or 'reset_user' not in session:
        flash("Proceso no autorizado o expirado.", "error")
        return redirect(url_for('main.login_page'))

    nueva_clave = request.form.get('nueva_clave')
    confirmar_clave = request.form.get('confirmar_clave')

    # Validaciones de seguridad para la nueva contraseña
    if len(nueva_clave) < 8:
        flash("La contraseña debe tener al menos 8 caracteres por seguridad.", "warning")
        return redirect(url_for('main.verificar_pin_page'))

    if nueva_clave != confirmar_clave:
        flash("Las contraseñas no coinciden. Inténtalo de nuevo.", "error")
        return redirect(url_for('main.verificar_pin_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        hash_pass = generate_password_hash(nueva_clave)
        username = session['reset_user']

        cur.execute("UPDATE usuarios SET password_hash = %s WHERE username = %s", (hash_pass, username))
        conn.commit()

        # Limpiamos todos los rastros temporales de la sesión
        session.pop('reset_pin', None)
        session.pop('reset_user', None)
        session.pop('pin_verificado', None)

        flash("¡Tu contraseña ha sido actualizada con éxito! Ya puedes ingresar.", "success")
        return redirect(url_for('main.login_page'))

    except Exception as e:
        conn.rollback()
        print(f"[ERROR ACTUALIZANDO CLAVE]: {e}")
        flash("Error interno al cambiar la clave.", "error")
        return redirect(url_for('main.verificar_pin_page'))
    finally:
        cur.close()
        conn.close()

# RUTA PARA CANCELAR EL PROCESO DE RECUPERACIÓN DE CONTRASEÑA
@bp.route('/cancelar-recuperacion')
def cancelar_recuperacion():
    # Destruye toda la evidencia del PIN en memoria
    session.pop('reset_pin', None)
    session.pop('reset_user', None)
    session.pop('reset_time', None)
    session.pop('pin_intentos', None)
    session.pop('pin_verificado', None)
    return redirect(url_for('main.login_page'))

# ADMINISTRACIÓN DEL ACCESO AL SISTEMA (USUARIOS Y ROLES)

@bp.route('/usuarios')
@login_requerido
@superadmin_requerido
def gestion_usuarios():
    # Renderiza la vista del CRUD de empleados combinando los datos de la tabla usuarios y de la tabla roles
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT u.id, u.nombre_completo, u.username, u.activo, r.nombre as rol_nombre, r.id as rol_id, u.foto_perfil, u.correo
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            ORDER BY u.id ASC
        """)
        usuarios = cur.fetchall()

        cur.execute("SELECT id, nombre FROM roles ORDER BY id ASC")
        roles = cur.fetchall()
    except Exception as e:
        print(f"[ERROR CARGANDO USUARIOS]: {e}")
        flash("Error interno al cargar la lista de usuarios.", "error")
        usuarios, roles = [], []
    finally:
        cur.close()
        conn.close()

    return render_template('auth/usuarios.html', usuarios=usuarios, roles=roles)

@bp.route('/usuarios/guardar', methods=['POST'])
@login_requerido
@superadmin_requerido
def guardar_usuario():
    # Punto final para la creación de perfiles nuevos o actualización de perfiles existentes
    id_usuario = request.form.get('id')
    nombre_completo = request.form.get('nombre_completo')
    username = request.form.get('username', '').strip().replace(" ", "").lower()
    password = request.form.get('password')
    rol_id = request.form.get('rol_id')
    file_foto = request.files.get('foto_perfil')
    correo = request.form.get('correo', '').strip()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        foto_nombre = None

        # Recupera el nombre de la foto que ya tenía asignada el usuario para no perderla si solo cambia el nombre
        if id_usuario:
            cur.execute("SELECT foto_perfil FROM usuarios WHERE id = %s", (id_usuario,))
            res_foto = cur.fetchone()
            foto_nombre = res_foto[0] if res_foto else None # Si no hay foto previa, se mantiene como None

        if file_foto and file_foto.filename != '': # Si el administrador subió un archivo de imagen, se procesa y guarda en la carpeta correspondiente

            # Chequeo de peso límite moviendo el cursor de lectura al final de los bytes del archivo
            file_foto.seek(0, os.SEEK_END)
            peso_archivo = file_foto.tell()
            file_foto.seek(0, 0) # Retorna a posición cero para que Pillow pueda procesar la imagen

            # 5 MB transformados a escala byte
            if peso_archivo > 5 * 1024 * 1024:
                flash("La imagen es demasiado pesada. El tamaño máximo permitido es de 5 MB.", "error")
                return redirect(url_for('main.gestion_usuarios'))

            # Direccionamiento relativo a la carpeta 'static'
            folder_path = os.path.join(current_app.root_path, 'static', 'uploads', 'usuarios')
            os.makedirs(folder_path, exist_ok=True)

            # NUEVO: ELIMINACIÓN DE LA FOTO ANTERIOR (AHORRO DE ESPACIO)
            if foto_nombre:
                ruta_foto_vieja = os.path.join(folder_path, foto_nombre)
                # Verificamos si el archivo viejo realmente existe en el disco duro
                if os.path.exists(ruta_foto_vieja):
                    try:
                        os.remove(ruta_foto_vieja) # Lo eliminamos físicamente
                    except Exception as e:
                        print(f"[ADVERTENCIA] No se pudo borrar la foto vieja: {e}")

            # Construye un nombre unívoco asegurando la limpieza de caracteres prohibidos en el sistema operativo
            nombre_seguro = secure_filename(file_foto.filename)
            filename = f"user_{username}_{nombre_seguro.split('.')[0]}.jpg"
            filepath = os.path.join(folder_path, filename)

            # Redimensionado geométrico obligatorio: Fija aspecto de 300x300, parcha fondos transparentes de PNG y comprime al 85%
            img = Image.open(file_foto)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img_cuadrada = ImageOps.fit(img, (300, 300), Image.Resampling.LANCZOS)
            img_cuadrada.save(filepath, format='JPEG', optimize=True, quality=85)

            foto_nombre = filename

        # Lógica dividida: Actualizar vs Insertar (Update / Insert)
        if id_usuario:
            if password:
                hash_pass = generate_password_hash(password)
                cur.execute("""
                    UPDATE usuarios SET nombre_completo = %s, username = %s, rol_id = %s, password_hash = %s, foto_perfil = %s, correo = %s
                    WHERE id = %s
                """, (nombre_completo, username, rol_id, hash_pass, foto_nombre, correo, id_usuario))
            else:
                cur.execute("""
                    UPDATE usuarios SET nombre_completo = %s, username = %s, rol_id = %s, foto_perfil = %s, correo = %s
                    WHERE id = %s
                """, (nombre_completo, username, rol_id, foto_nombre, correo, id_usuario))

            if int(id_usuario) == int(session.get('user_id')):
                session['user_nombre'] = nombre_completo
                session['user_foto'] = foto_nombre or ''
                session.modified = True

            flash("Usuario actualizado con éxito", "success")

        else:
            if not password:
                flash("La contraseña es obligatoria para un usuario nuevo", "error")
                return redirect(url_for('main.gestion_usuarios'))

            hash_pass = generate_password_hash(password)
            cur.execute("""
                INSERT INTO usuarios (nombre_completo, username, password_hash, rol_id, foto_perfil, correo)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre_completo, username, hash_pass, rol_id, foto_nombre, correo))
            flash("Usuario creado con éxito", "success")

        conn.commit()
    except Exception as e:
        conn.rollback()
        # Constraint catcher: Si en la DB salta un error de duplicado (username único), se advierte formalmente
        if "unique constraint" in str(e).lower(): # Detecta si el error es por violación de restricción única (username duplicado)
            flash("Ese nombre de usuario ya está registrado, elige otro.", "error")
        else:
            print(f"[ERROR GUARDANDO USUARIO]: {e}")
            flash("Error interno del servidor al guardar. Verifique los datos o contacte a soporte.", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('main.gestion_usuarios'))

@bp.route('/api/usuarios/toggle/<int:id>', methods=['POST'])
@login_requerido
@superadmin_requerido
def toggle_estado_usuario(id):
    # Deshabilita de forma lógica a un usuario, cambiando su bool 'activo', prohibiéndole el paso al login de inmediato
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Validación de candado: Bloquea intentos de suicidio de sesión
        if int(id) == int(session.get('user_id')):
            return jsonify({'status': 'error', 'msg': 'No puedes desactivar tu propia cuenta.'}), 400

        cur.execute("UPDATE usuarios SET activo = NOT activo WHERE id = %s RETURNING activo", (id,)) # Cambia el estado de activo a inactivo o viceversa y devuelve el nuevo estado
        nuevo_estado = cur.fetchone()[0]
        conn.commit()
        return jsonify({'status': 'ok', 'activo': nuevo_estado})
    except Exception as e:
        conn.rollback()
        print(f"[ERROR TOGGLE USUARIO]: {e}")
        return jsonify({'status': 'error', 'msg': 'Falla interna al procesar el cambio.'}), 500
    finally:
        cur.close()
        conn.close()

@bp.route('/api/roles/crear', methods=['POST'])
@login_requerido
@superadmin_requerido
def crear_rol():
    # End-point asíncrono para añadir registros dinámicos a la tabla Roles desde modales secundarios
    data = request.get_json(silent=True) or {} # Obtiene los datos JSON enviados desde el cliente, si no hay datos, se asigna un diccionario vacío
    nombre_rol = data.get('nombre', '').strip()
    descripcion_rol = data.get('descripcion', '').strip()

    if not nombre_rol: # Si el nombre del rol está vacío, devuelve un error JSON con código 400 (Bad Request)
        return jsonify({'status': 'error', 'msg': 'El nombre del rol no puede estar vacío.'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO roles (nombre, descripcion) VALUES (%s, %s) RETURNING id",
                    (nombre_rol, descripcion_rol))
        nuevo_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({'status': 'ok', 'id': nuevo_id, 'nombre': nombre_rol}) # Devuelve un JSON con el estado de éxito y los datos del nuevo rol creado
    except Exception as e:
        conn.rollback()
        # Filtro de repetición
        if "unique constraint" in str(e).lower():
            return jsonify({'status': 'error', 'msg': f"El rol '{nombre_rol}' ya existe en el sistema."}), 400
        print(f"[ERROR CREANDO ROL]: {e}")
        return jsonify({'status': 'error', 'msg': 'Falla interna al almacenar el rol.'}), 500
    finally:
        cur.close()
        conn.close()

# GESTORES Y VISUALIZADORES DE LAS TABLAS DEL NEGOCIO

@bp.route('/')
def login_page():
    # Si el usuario ya está logueado, lo mandamos a la pantalla principal
    if 'user_id' in session:
        return redirect(url_for('main.pantalla_principal'))
    # Si no está logueado, le mostramos la pantalla de login limpia
    return render_template('generales/login.html')


@bp.route('/pantalla-principal')
@login_requerido
def pantalla_principal():
    # Pantalla de bienvenida con el GIF centrado (solo esto se ve)
    return render_template('generales/pantalla_principal.html')


@bp.route('/inicio')
@login_requerido
def index():
    # Panel Privado (Dashboard) - Ahora se accede desde la pestaña "Reportes"
    version = f"v{current_app.config['APP_VERSION']} ({obtener_hash_git()})"
    return render_template('generales/index.html', version=version)


@bp.route('/ver-historial')
@superadmin_requerido
def ver_historial():
    """Muestra el historial de cambios con paginación y filtros."""
    opciones = obtener_opciones_filtros()
    
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = 100
    offset = (pagina - 1) * por_pagina
    
    cambios = obtener_historial(limite=por_pagina, offset=offset)
    total = contar_historial()
    total_paginas = (total + por_pagina - 1) // por_pagina
    
    return render_template(
        'generales/ver_historial.html', 
        cambios=cambios,
        opciones=opciones,
        pagina=pagina,
        total_paginas=total_paginas,
        total=total
    )


@bp.route('/api/auditoria/filtrar')
@superadmin_requerido
def api_auditoria_filtrar():
    """API para filtrar el historial de cambios."""
    filtros = {
        'usuario': request.args.get('usuario', ''),
        'tabla': request.args.get('tabla', ''),
        'accion': request.args.get('accion', ''),
        'campo': request.args.get('campo', ''),
        'fecha_desde': request.args.get('fecha_desde', ''),
        'fecha_hasta': request.args.get('fecha_hasta', ''),
        'lote': request.args.get('lote', ''),
    }
    # Limpiar filtros vacíos
    filtros = {k: v for k, v in filtros.items() if v}
    
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = request.args.get('por_pagina', 100, type=int)
    offset = (pagina - 1) * por_pagina
    
    cambios = obtener_historial_filtrado(filtros=filtros, limite=por_pagina, offset=offset)
    total = contar_historial_filtrado(filtros=filtros)
    total_paginas = (total + por_pagina - 1) // por_pagina
    
    return jsonify({
        'status': 'ok',
        'cambios': cambios,
        'pagina': pagina,
        'total_paginas': total_paginas,
        'total': total
    })


@bp.route('/api/auditoria/opciones')
@superadmin_requerido
def api_auditoria_opciones():
    """API para obtener las opciones de los dropdowns de filtros."""
    opciones = obtener_opciones_filtros()
    return jsonify({
        'status': 'ok',
        **opciones
    })


@bp.route('/api/auditoria/campos')
@superadmin_requerido
def api_auditoria_campos():
    """API para obtener los campos de una tabla específica."""
    tabla = request.args.get('tabla', '')
    if not tabla:
        return jsonify({'status': 'ok', 'campos': []})
    campos = obtener_campos_por_tabla(tabla)
    return jsonify({'status': 'ok', 'campos': campos})


@bp.route('/logout')
def logout():
    # Destrucción forzada de todas las variables temporales del navegador
    session.clear()

    # Mensaje de despedida con imagen incrustada
    img_url = url_for('static', filename='img/Despedida.gif')
    flash(f'<img src="{img_url}" style="vertical-align: middle; height: 55px; width: auto;"> Has cerrado sesión exitosamente.', 'success')

    # Creamos una respuesta de redirección y le inyectamos un script para limpiar el localStorage
    response = redirect(url_for('main.login_page'))
    response.set_cookie('clear_sidebar', 'true', max_age=5)  # Cookie temporal
    return response

# --- SISTEMA DE SUPLANTACIÓN DE SEGURIDAD (LOGIN AS) ---
@bp.route('/api/usuarios/suplantar/<int:id>', methods=['POST'])
@login_requerido
@superadmin_requerido
def suplantar_usuario(id):
    if int(id) == int(session.get('user_id')):
        return jsonify({'status': 'error', 'msg': 'No puedes suplantarte a ti mismo.'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, nombre_completo, activo FROM usuarios WHERE id = %s", (id,))
        usuario = cur.fetchone()

        if not usuario: return jsonify({'status': 'error', 'msg': 'Usuario no encontrado.'}), 404
        if not usuario[2]: return jsonify({'status': 'error', 'msg': 'No puedes suplantar a un usuario inactivo.'}), 400

        # Guardamos la identidad real del Superadmin en variables temporales
        session['admin_id_real'] = session['user_id']
        session['admin_nombre_real'] = session['user_nombre']
        session['admin_rol_real'] = session['user_rol']

        # Aplicamos la máscara (Forzando el rol a 'Lector' por máxima seguridad)
        session['user_id'] = usuario[0]
        session['user_nombre'] = usuario[1]
        session['user_rol'] = 'Lector'
        session['is_impersonating'] = True

        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[ERROR SUPLANTACIÓN]: {e}")
        return jsonify({'status': 'error', 'msg': 'Error interno del servidor.'}), 500
    finally:
        cur.close()
        conn.close()

@bp.route('/revertir-suplantacion')
@login_requerido
def revertir_suplantacion():
    # Devuelve al usuario a su estado original de Superadmin
    if session.get('is_impersonating'):
        session['user_id'] = session.pop('admin_id_real')
        session['user_nombre'] = session.pop('admin_nombre_real')
        session['user_rol'] = session.pop('admin_rol_real')
        session.pop('is_impersonating')
        flash("Has vuelto a tu cuenta de Superadministrador.", "success")
    return redirect(url_for('main.gestion_usuarios'))

# HERRAMIENTAS DE PREPARACIÓN DEL ENTORNO DB

@bp.route('/instalar-seguridad')
def instalar_seguridad():
    # Disparador inicial o "Setup Script": Se usa al recién montar el servidor para generar la estructura básica
    from werkzeug.security import generate_password_hash
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Construye de manera segura el armazón de control de privilegios (Roles)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(50) UNIQUE NOT NULL,
                descripcion TEXT
            )
        """)

        # Construye la tabla principal del personal limitando los accesos a datos foráneos de la tabla roles
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nombre_completo VARCHAR(100) NOT NULL,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                rol_id INTEGER REFERENCES roles(id),
                activo BOOLEAN DEFAULT TRUE,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Asegura la existencia del rol de acceso ilimitado
        cur.execute("SELECT id FROM roles WHERE nombre = 'Superadmin'")
        if not cur.fetchone():
            cur.execute("INSERT INTO roles (nombre, descripcion) VALUES ('Superadmin', 'Control total del sistema')")

        # Otorga el primer acceso vital a la organización
        cur.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if not cur.fetchone():
            hash_pass = generate_password_hash('admin123')
            cur.execute("""
                INSERT INTO usuarios (nombre_completo, username, password_hash, rol_id)
                VALUES ('Super Administrador', 'admin', %s, (SELECT id FROM roles WHERE nombre = 'Superadmin'))
            """, (hash_pass,))

        conn.commit()
        return "<h1>¡SEGURIDAD INSTALADA CON ÉXITO!</h1><p>Las tablas de roles y usuarios ya existen.</p>"
    except Exception as e:
        conn.rollback()
        return f"<h1>Hubo un problema:</h1><p>{str(e)}</p>"
    finally:
        cur.close()
        conn.close()

@bp.route('/agregar-columna-foto')
def agregar_columna_foto():
    # Parche inyector: Alteración al DDL original para soportar avatares si la tabla usuarios ya existía antes
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil VARCHAR(255);")
        conn.commit()
        return "<h1>¡ÉXITO!</h1><p>La columna 'foto_perfil' fue agregada correctamente a la tabla usuarios.</p>"
    except Exception as e:
        conn.rollback()
        return f"<h1>Nota/Error:</h1><p>{str(e)}</p>"
    finally:
        cur.close()
        conn.close()
        
# ==============================================================================
# RUTAS DE PRUEBA (SOLO SUPERADMIN) - Test de mensajes flash con imágenes
# ==============================================================================

@bp.route('/test-flash-saludo')
@login_requerido
@superadmin_requerido
def test_flash_saludo():
    img_url = url_for('static', filename='img/Saludo.gif')
    flash(f'<img src="{img_url}" style="vertical-align: middle; height: 55px; width: auto;"> ¡Bienvenido, {session.get("user_nombre", "Usuario")}!', 'success')
    return redirect(url_for('main.pantalla_principal'))


@bp.route('/test-flash-despedida')
@login_requerido
@superadmin_requerido
def test_flash_despedida():
    img_url = url_for('static', filename='img/Despedida.gif')
    flash(f'<img src="{img_url}" style="vertical-align: middle; height: 55px; width: auto;"> Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('main.pantalla_principal'))


@bp.route('/test-flash-sin-imagen')
@login_requerido
@superadmin_requerido
def test_flash_sin_imagen():
    flash("Este es un mensaje de prueba SIN imagen. Debería aparecer como toast pequeño arriba a la derecha.", 'success')
    return redirect(url_for('main.pantalla_principal'))