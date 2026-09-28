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
from routes.carga_datos.vistas import carga_datos_bp

# --- INICIO DEL FILTRO INFALIBLE PARA OCULTAR GET ---
class ManejadorSilencioso(werkzeug.serving.WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        if 'GET' in self.requestline:
            return  # Oculta peticiones GET en la consola
        super().log_request(code, size)
# --- FIN DEL FILTRO ---

def create_app():
    app = Flask(__name__)
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
    app.register_blueprint(carga_datos_bp)         # Blueprint modular de carga masiva de datos

    return app

# Instancia global (usada por run.py y servidores WSGI)
app = create_app()

if __name__ == '__main__':
    # Ejecutamos con el manejador silencioso
    app.run(host='0.0.0.0', port=5000, debug=True, request_handler=ManejadorSilencioso)