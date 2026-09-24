from flask import Flask
from config import Config
import werkzeug.serving

# Importación de Blueprints
from routes.routes import bp
from routes.planta_alimentos.catalogo_a import planta_bp

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
    app.register_blueprint(bp)        # Blueprint principal (main)
    app.register_blueprint(planta_bp) # Blueprint modular de planta de alimentos

    return app

# Instancia global (usada por run.py y servidores WSGI)
app = create_app()

if __name__ == '__main__':
    # Ejecutamos con el manejador silencioso
    app.run(host='0.0.0.0', port=5000, debug=True, request_handler=ManejadorSilencioso)