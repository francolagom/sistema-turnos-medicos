"""Configuración de la aplicación."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # La clave local permite ejecutar el prototipo. Debe reemplazarse mediante
    # la variable SECRET_KEY antes de cualquier despliegue fuera de desarrollo.
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-local-solo-para-desarrollo")
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "turnos.db"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}
