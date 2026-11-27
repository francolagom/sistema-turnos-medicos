"""Punto de entrada para ejecutar la aplicación localmente."""
from app import app

if __name__ == "__main__":
    # Servidor de desarrollo: no exponer directamente a Internet.
    app.run(host="127.0.0.1", port=5000, debug=False)
