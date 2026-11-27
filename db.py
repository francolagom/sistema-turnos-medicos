"""Acceso a SQLite y creación de la estructura inicial."""
import sqlite3
from pathlib import Path
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dni TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT
);
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    specialty TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    slot_minutes INTEGER NOT NULL CHECK (slot_minutes > 0),
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    UNIQUE (doctor_id, weekday, start_time, end_time)
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    appointment_date TEXT NOT NULL,
    appointment_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Programado' CHECK (status IN ('Programado', 'Cancelado')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id, appointment_date, appointment_time);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_doctor_slot
    ON appointments(doctor_id, appointment_date, appointment_time) WHERE status = 'Programado';
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_patient_slot
    ON appointments(patient_id, appointment_date, appointment_time) WHERE status = 'Programado';
"""


def get_db():
    """Devuelve una conexión por solicitud web."""
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Crea tablas y carga datos de demostración solo si la base está vacía."""
    db = get_db()
    db.executescript(SCHEMA)
    user_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if user_count == 0:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin1234")),
        )
        db.execute(
            "INSERT INTO doctors (first_name, last_name, specialty) VALUES (?, ?, ?)",
            ("Laura", "Pérez", "Clínica médica"),
        )
        doctor_id = db.execute("SELECT id FROM doctors WHERE first_name = ?", ("Laura",)).fetchone()["id"]
        db.execute(
            "INSERT INTO schedules (doctor_id, weekday, start_time, end_time, slot_minutes) VALUES (?, ?, ?, ?, ?)",
            (doctor_id, 0, "09:00", "12:00", 30),
        )
        db.execute(
            "INSERT INTO patients (dni, first_name, last_name, phone, email) VALUES (?, ?, ?, ?, ?)",
            ("30111222", "María", "Gómez", "1123456789", "maria@example.com"),
        )
    db.commit()
