from flask import Flask
from config import Config
from routes import bp
import werkzeug.serving

# --- INICIO DEL FILTRO INFALIBLE PARA OCULTAR GET ---
# Creamos una clase que hereda del manejador original de peticiones de Flask
class ManejadorSilencioso(werkzeug.serving.WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        # self.requestline contiene el texto de la petición, por ejemplo: "GET / HTTP/1.1"
        if 'GET' in self.requestline:
            return  # Si detecta que es un GET, simplemente "muere" aquí y no imprime nada
        
        # Si es un POST u otro método, llama a la función original para que lo imprima
        super().log_request(code, size)
# --- FIN DEL FILTRO ---

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Registro del Blueprint con todas las rutas
    app.register_blueprint(bp)

    return app

# Instancia global (usada por run.py y por servidores WSGI como Gunicorn)
app = create_app()

if __name__ == '__main__':
    # Encendemos el motor en el puerto 5000 y le decimos explícitamente 
    # que use nuestro ManejadorSilencioso (request_handler)
    app.run(host='0.0.0.0', port=5000, debug=True, request_handler=ManejadorSilencioso)