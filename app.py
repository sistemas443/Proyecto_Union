from flask import Flask
from config import Config
from routes import bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Registro del Blueprint con todas las rutas
    app.register_blueprint(bp)

    return app

# Instancia global (usada por run.py y por servidores WSGI como Gunicorn)
app = create_app()

# --- AGREGA ESTO AL FINAL ---
if __name__ == '__main__':
    # Encendemos el motor en el puerto 5000 y lo exponemos para Google Cloud (0.0.0.0)
    app.run(host='0.0.0.0', port=5000, debug=True)