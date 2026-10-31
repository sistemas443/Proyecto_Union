from flask import Flask
from config import Config
import werkzeug.serving

# Importación de Blueprints
from routes.routes import bp
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.primera_semana.vistas import primera_semana_bp
from routes.semanal_levante.vistas import semanal_levante_bp
from routes.semanal.vistas import semanal_bp
from routes.diario.vistas import diario_bp
from routes.clasificacion.vistas import clasificacion_bp
from routes.lotes.vistas import lotes_bp
from routes.catalogos.api import catalogos_bp
from routes.consolidados.vistas import consolidados_bp
from routes.carga_datos.vistas import carga_datos_bp
from routes.talento_humano.vistas import talento_humano_bp  # NUEVO: Talento Humano

# --- INICIO DEL FILTRO INFALIBLE PARA OCULTAR GET ---
class ManejadorSilencioso(werkzeug.serving.WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        if 'GET' in self.requestline:
            return  # Oculta peticiones GET en la consola
        super().log_request(code, size)
# --- FIN DEL FILTRO ---

def registrar_errores_globales(app):
    """
    Guarda en el historial de auditoría cualquier excepción no atrapada por las rutas.
    Se registra con tabla 'sistema' y con la ruta que se estaba atendiendo como contexto.
    """
    from flask import request, session
    from werkzeug.exceptions import HTTPException
    from models.auditoria.services import registrar_error

    @app.errorhandler(Exception)
    def error_no_controlado(error):
        es_error_cliente = isinstance(error, HTTPException) and error.code < 500

        # Los errores del cliente (404, 401, etc.) no son fallos del sistema, no se registran
        if not es_error_cliente:
            try:
                registrar_error(
                    tabla='sistema',
                    contexto=f'{request.method} {request.path}'[:100],
                    mensaje=f'{type(error).__name__}: {error}',
                    usuario_id=session.get('user_id'),
                    usuario_nombre=session.get('user_nombre', 'Sistema'),
                )
            except Exception as e:
                print(f"[ERROR REGISTRANDO EXCEPCIÓN GLOBAL]: {e}")

        # Las excepciones HTTP (404, 401, etc.) se responden tal cual
        if isinstance(error, HTTPException):
            return error

        app.logger.exception('Excepción no controlada')
        return 'Error interno del servidor. El fallo quedó registrado en el historial.', 500


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- FILTROS PERSONALIZADOS JINJA2 ---
    def tiempo_transcurrido(fecha_ingreso):
        """Calcula años, meses y días desde fecha_ingreso hasta hoy"""
        if not fecha_ingreso:
            return "—"
        from datetime import date
        hoy = date.today()
        # Si fecha_ingreso es string, convertir a date
        if isinstance(fecha_ingreso, str):
            try:
                fecha_ingreso = date.fromisoformat(fecha_ingreso)
            except ValueError:
                return "—"
        elif not hasattr(fecha_ingreso, 'year'):
            return "—"

        años = hoy.year - fecha_ingreso.year
        meses = hoy.month - fecha_ingreso.month
        dias = hoy.day - fecha_ingreso.day

        if dias < 0:
            meses -= 1
            # Días del mes anterior
            import calendar
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            año_mes_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            dias += calendar.monthrange(año_mes_anterior, mes_anterior)[1]

        if meses < 0:
            años -= 1
            meses += 12

        partes = []
        if años > 0:
            partes.append(f"{años}a")
        if meses > 0:
            partes.append(f"{meses}m")
        if dias > 0 or not partes:
            partes.append(f"{dias}d")

        return " ".join(partes)

    app.jinja_env.filters['tiempo_transcurrido'] = tiempo_transcurrido
    # ---------------------------------------

    app.config.from_object(Config)

    # Registro de TODOS los Blueprints del proyecto
    app.register_blueprint(bp)                    # Blueprint principal (main)
    app.register_blueprint(planta_bp)              # Blueprint modular de planta de alimentos
    app.register_blueprint(primera_semana_bp)      # Blueprint modular de primera semana
    app.register_blueprint(semanal_levante_bp)     # Blueprint modular de semanal levante
    app.register_blueprint(semanal_bp)             # Blueprint modular de semanal producción (+ gráficos)
    app.register_blueprint(diario_bp)              # Blueprint modular de diario
    app.register_blueprint(clasificacion_bp)       # Blueprint modular de clasificación
    app.register_blueprint(lotes_bp)               # Blueprint modular de lotes (+ cabecera)
    app.register_blueprint(catalogos_bp)           # Blueprint de catálogos con foto (Superadmin)
    app.register_blueprint(consolidados_bp)         # Blueprint de consolidados L+P
    app.register_blueprint(carga_datos_bp)         # Blueprint modular de carga masiva de datos
    app.register_blueprint(talento_humano_bp)      # NUEVO: Talento Humano

    # --- REGISTRO DE ERRORES NO ESPERADOS EN EL HISTORIAL DE AUDITORÍA ---
    registrar_errores_globales(app)
    # ------------------------------------

    return app

# Instancia global (usada por run.py y servidores WSGI)
app = create_app()

if __name__ == '__main__':
    # Ejecutamos con el manejador silencioso
    app.run(host='0.0.0.0', port=5000, debug=True, request_handler=ManejadorSilencioso)