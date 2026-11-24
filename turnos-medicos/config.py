"""Configuración de la aplicación."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-local-solo-para-desarrollo")
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "turnos.db"))
