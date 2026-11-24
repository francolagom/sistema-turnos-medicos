"""Sistema web de gestión de turnos médicos. Proyecto académico."""
from datetime import date, datetime, time, timedelta
from functools import wraps
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from config import Config
from db import close_db, get_db, init_db

WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.context_processor
    def inject_globals():
        return {"weekdays": WEEKDAYS}

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Iniciá sesión para continuar.", "warning")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def clean_required(*names):
        """Obtiene campos obligatorios y evita guardar cadenas vacías."""
        values = {name: request.form.get(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError("Completá todos los campos obligatorios.")
        return values

    def parse_date(value):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("La fecha ingresada no es válida.")

    def get_available_slots(doctor_id, day, exclude_appointment_id=None):
        """Genera horarios en base a la agenda y descarta los ya ocupados."""
        db = get_db()
        weekday = day.weekday()
        schedules = db.execute(
            "SELECT * FROM schedules WHERE doctor_id = ? AND weekday = ? ORDER BY start_time",
            (doctor_id, weekday),
        ).fetchall()
        occupied_sql = (
            "SELECT appointment_time FROM appointments "
            "WHERE doctor_id = ? AND appointment_date = ? AND status = 'Programado'"
        )
        occupied_params = [doctor_id, day.isoformat()]
        if exclude_appointment_id is not None:
            occupied_sql += " AND id != ?"
            occupied_params.append(exclude_appointment_id)
        occupied = {
            row["appointment_time"] for row in db.execute(occupied_sql, occupied_params).fetchall()
        }
        slots = []
        for schedule in schedules:
            start = datetime.strptime(schedule["start_time"], "%H:%M")
            end = datetime.strptime(schedule["end_time"], "%H:%M")
            step = timedelta(minutes=schedule["slot_minutes"])
            current = start
            while current + step <= end:
                label = current.strftime("%H:%M")
                if label not in occupied:
                    slots.append(label)
                current += step
        return slots

    @app.route("/")
    def index():
        if "user_id" not in session:
            return redirect(url_for("login"))
        return redirect(url_for("dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
            ).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                flash("Bienvenido/a al sistema.", "success")
                return redirect(url_for("dashboard"))
            flash("Usuario o contraseña incorrectos.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("La sesión se cerró correctamente.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db = get_db()
        stats = {
            "patients": db.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            "doctors": db.execute("SELECT COUNT(*) FROM doctors").fetchone()[0],
            "appointments": db.execute("SELECT COUNT(*) FROM appointments WHERE status = 'Programado'").fetchone()[0],
        }
        today = date.today().isoformat()
        today_appointments = db.execute(
            "SELECT a.*, p.first_name || ' ' || p.last_name AS patient_name, "
            "d.first_name || ' ' || d.last_name AS doctor_name "
            "FROM appointments a JOIN patients p ON p.id=a.patient_id "
            "JOIN doctors d ON d.id=a.doctor_id "
            "WHERE a.appointment_date=? AND a.status='Programado' ORDER BY a.appointment_time",
            (today,),
        ).fetchall()
        return render_template("dashboard.html", stats=stats, today_appointments=today_appointments)

    @app.route("/patients", methods=["GET", "POST"])
    @login_required
    def patients():
        db = get_db()
        if request.method == "POST":
            try:
                data = clean_required("dni", "first_name", "last_name", "phone")
                data["email"] = request.form.get("email", "").strip() or None
                db.execute(
                    "INSERT INTO patients (dni, first_name, last_name, phone, email) VALUES (?, ?, ?, ?, ?)",
                    (data["dni"], data["first_name"], data["last_name"], data["phone"], data["email"]),
                )
                db.commit()
                flash("Paciente registrado correctamente.", "success")
                return redirect(url_for("patients"))
            except ValueError as error:
                flash(str(error), "danger")
            except sqlite3.IntegrityError:
                flash("Ya existe un paciente registrado con ese DNI.", "danger")
        rows = db.execute("SELECT * FROM patients ORDER BY last_name, first_name").fetchall()
        return render_template("patients.html", patients=rows)

    @app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_patient(patient_id):
        db = get_db()
        patient = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
        if not patient:
            flash("No se encontró el paciente.", "danger")
            return redirect(url_for("patients"))
        if request.method == "POST":
            try:
                data = clean_required("dni", "first_name", "last_name", "phone")
                email = request.form.get("email", "").strip() or None
                db.execute(
                    "UPDATE patients SET dni=?, first_name=?, last_name=?, phone=?, email=? WHERE id=?",
                    (data["dni"], data["first_name"], data["last_name"], data["phone"], email, patient_id),
                )
                db.commit()
                flash("Datos del paciente actualizados.", "success")
                return redirect(url_for("patients"))
            except ValueError as error:
                flash(str(error), "danger")
            except sqlite3.IntegrityError:
                flash("Ese DNI ya está asociado a otro paciente.", "danger")
        return render_template("patient_edit.html", patient=patient)

    @app.route("/patients/<int:patient_id>/delete", methods=["POST"])
    @login_required
    def delete_patient(patient_id):
        db = get_db()
        linked = db.execute("SELECT COUNT(*) FROM appointments WHERE patient_id=?", (patient_id,)).fetchone()[0]
        if linked:
            flash("No se puede eliminar: el paciente tiene turnos asociados. Podés conservar su registro.", "warning")
        else:
            db.execute("DELETE FROM patients WHERE id=?", (patient_id,))
            db.commit()
            flash("Paciente eliminado.", "success")
        return redirect(url_for("patients"))

    @app.route("/doctors", methods=["GET", "POST"])
    @login_required
    def doctors():
        db = get_db()
        if request.method == "POST":
            try:
                data = clean_required("first_name", "last_name", "specialty")
                db.execute(
                    "INSERT INTO doctors (first_name, last_name, specialty) VALUES (?, ?, ?)",
                    (data["first_name"], data["last_name"], data["specialty"]),
                )
                db.commit()
                flash("Médico registrado correctamente.", "success")
                return redirect(url_for("doctors"))
            except ValueError as error:
                flash(str(error), "danger")
        rows = db.execute("SELECT * FROM doctors ORDER BY last_name, first_name").fetchall()
        return render_template("doctors.html", doctors=rows)

    @app.route("/doctors/<int:doctor_id>/delete", methods=["POST"])
    @login_required
    def delete_doctor(doctor_id):
        db = get_db()
        linked = db.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id=?", (doctor_id,)).fetchone()[0]
        if linked:
            flash("No se puede eliminar: el médico tiene turnos asociados.", "warning")
        else:
            db.execute("DELETE FROM doctors WHERE id=?", (doctor_id,))
            db.commit()
            flash("Médico eliminado.", "success")
        return redirect(url_for("doctors"))

    @app.route("/schedules", methods=["GET", "POST"])
    @login_required
    def schedules():
        db = get_db()
        if request.method == "POST":
            try:
                data = clean_required("doctor_id", "weekday", "start_time", "end_time", "slot_minutes")
                doctor_id = int(data["doctor_id"])
                weekday = int(data["weekday"])
                start = datetime.strptime(data["start_time"], "%H:%M")
                end = datetime.strptime(data["end_time"], "%H:%M")
                slot_minutes = int(data["slot_minutes"])
                if not db.execute("SELECT id FROM doctors WHERE id=?", (doctor_id,)).fetchone():
                    raise ValueError("Seleccioná un médico válido.")
                if not 0 <= weekday <= 6 or end <= start or slot_minutes <= 0:
                    raise ValueError("Revisá el día, el rango horario y la duración del turno.")
                if (end - start).seconds // 60 < slot_minutes:
                    raise ValueError("El horario de atención debe ser igual o mayor a la duración del turno.")
                db.execute(
                    "INSERT INTO schedules (doctor_id, weekday, start_time, end_time, slot_minutes) VALUES (?, ?, ?, ?, ?)",
                    (doctor_id, weekday, data["start_time"], data["end_time"], slot_minutes),
                )
                db.commit()
                flash("Horario agregado correctamente.", "success")
                return redirect(url_for("schedules"))
            except ValueError as error:
                flash(str(error), "danger")
            except sqlite3.IntegrityError:
                flash("Ese horario ya está cargado para el médico seleccionado.", "danger")
        doctors_list = db.execute("SELECT * FROM doctors ORDER BY last_name").fetchall()
        rows = db.execute(
            "SELECT s.*, d.first_name, d.last_name FROM schedules s JOIN doctors d ON d.id=s.doctor_id "
            "ORDER BY d.last_name, s.weekday, s.start_time"
        ).fetchall()
        return render_template("schedules.html", doctors=doctors_list, schedules=rows)

    @app.route("/schedules/<int:schedule_id>/delete", methods=["POST"])
    @login_required
    def delete_schedule(schedule_id):
        db = get_db()
        db.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        db.commit()
        flash("Horario eliminado.", "success")
        return redirect(url_for("schedules"))

    @app.route("/appointments")
    @login_required
    def appointments():
        db = get_db()
        search = request.args.get("q", "").strip()
        query = (
            "SELECT a.*, p.first_name || ' ' || p.last_name AS patient_name, p.dni, "
            "d.first_name || ' ' || d.last_name AS doctor_name, d.specialty "
            "FROM appointments a JOIN patients p ON p.id=a.patient_id "
            "JOIN doctors d ON d.id=a.doctor_id"
        )
        params = []
        if search:
            query += " WHERE p.first_name LIKE ? OR p.last_name LIKE ? OR d.last_name LIKE ? OR a.appointment_date LIKE ?"
            params = [f"%{search}%"] * 4
        query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
        rows = db.execute(query, params).fetchall()
        return render_template("appointments.html", appointments=rows, search=search)

    @app.route("/appointments/new", methods=["GET", "POST"])
    @login_required
    def new_appointment():
        db = get_db()
        doctors_list = db.execute("SELECT * FROM doctors ORDER BY last_name").fetchall()
        patients_list = db.execute("SELECT * FROM patients ORDER BY last_name").fetchall()
        doctor_id = request.values.get("doctor_id", type=int)
        date_value = request.values.get("appointment_date", "")
        slots = []
        if doctor_id and date_value:
            try:
                selected_date = parse_date(date_value)
                if selected_date >= date.today():
                    slots = get_available_slots(doctor_id, selected_date)
            except ValueError:
                slots = []
        if request.method == "POST":
            try:
                data = clean_required("patient_id", "doctor_id", "appointment_date", "appointment_time")
                patient_id, selected_doctor = int(data["patient_id"]), int(data["doctor_id"])
                selected_date = parse_date(data["appointment_date"])
                if selected_date < date.today():
                    raise ValueError("No se pueden asignar turnos en fechas pasadas.")
                if not db.execute("SELECT id FROM patients WHERE id=?", (patient_id,)).fetchone():
                    raise ValueError("Seleccioná un paciente válido.")
                if not db.execute("SELECT id FROM doctors WHERE id=?", (selected_doctor,)).fetchone():
                    raise ValueError("Seleccioná un médico válido.")
                available = get_available_slots(selected_doctor, selected_date)
                if data["appointment_time"] not in available:
                    raise ValueError("El horario elegido ya no está disponible o no pertenece a la agenda del médico.")
                patient_busy = db.execute(
                    "SELECT id FROM appointments WHERE patient_id=? AND appointment_date=? AND appointment_time=? AND status='Programado'",
                    (patient_id, selected_date.isoformat(), data["appointment_time"]),
                ).fetchone()
                if patient_busy:
                    raise ValueError("El paciente ya tiene un turno en ese horario.")
                db.execute(
                    "INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
                    (patient_id, selected_doctor, selected_date.isoformat(), data["appointment_time"]),
                )
                db.commit()
                flash("Turno asignado correctamente.", "success")
                return redirect(url_for("appointments"))
            except (ValueError, TypeError) as error:
                flash(str(error) or "Revisá los datos ingresados.", "danger")
            except sqlite3.IntegrityError:
                flash("No se pudo guardar el turno. Revisá los datos.", "danger")
            doctor_id = request.form.get("doctor_id", type=int)
            date_value = request.form.get("appointment_date", "")
            if doctor_id and date_value:
                try:
                    slots = get_available_slots(doctor_id, parse_date(date_value))
                except ValueError:
                    slots = []
        return render_template(
            "appointment_new.html", doctors=doctors_list, patients=patients_list,
            selected_doctor=doctor_id, selected_date=date_value, slots=slots, today=date.today().isoformat(),
        )


    @app.route("/appointments/<int:appointment_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_appointment(appointment_id):
        db = get_db()
        appointment = db.execute(
            "SELECT * FROM appointments WHERE id=? AND status='Programado'", (appointment_id,)
        ).fetchone()
        if not appointment:
            flash("No se encontró un turno programado para modificar.", "warning")
            return redirect(url_for("appointments"))
        doctors_list = db.execute("SELECT * FROM doctors ORDER BY last_name").fetchall()
        patients_list = db.execute("SELECT * FROM patients ORDER BY last_name").fetchall()
        doctor_id = request.values.get("doctor_id", type=int) or appointment["doctor_id"]
        date_value = request.values.get("appointment_date") or appointment["appointment_date"]
        try:
            slots = get_available_slots(doctor_id, parse_date(date_value), appointment_id)
        except ValueError:
            slots = []
        if request.method == "POST":
            try:
                data = clean_required("patient_id", "doctor_id", "appointment_date", "appointment_time")
                patient_id = int(data["patient_id"])
                selected_doctor = int(data["doctor_id"])
                selected_date = parse_date(data["appointment_date"])
                if selected_date < date.today():
                    raise ValueError("No se pueden asignar turnos en fechas pasadas.")
                if not db.execute("SELECT id FROM patients WHERE id=?", (patient_id,)).fetchone():
                    raise ValueError("Seleccioná un paciente válido.")
                if not db.execute("SELECT id FROM doctors WHERE id=?", (selected_doctor,)).fetchone():
                    raise ValueError("Seleccioná un médico válido.")
                available = get_available_slots(selected_doctor, selected_date, appointment_id)
                if data["appointment_time"] not in available:
                    raise ValueError("El horario elegido ya no está disponible o no pertenece a la agenda del médico.")
                patient_busy = db.execute(
                    "SELECT id FROM appointments WHERE patient_id=? AND appointment_date=? "
                    "AND appointment_time=? AND status='Programado' AND id != ?",
                    (patient_id, selected_date.isoformat(), data["appointment_time"], appointment_id),
                ).fetchone()
                if patient_busy:
                    raise ValueError("El paciente ya tiene otro turno en ese horario.")
                db.execute(
                    "UPDATE appointments SET patient_id=?, doctor_id=?, appointment_date=?, appointment_time=? WHERE id=?",
                    (patient_id, selected_doctor, selected_date.isoformat(), data["appointment_time"], appointment_id),
                )
                db.commit()
                flash("Turno modificado correctamente.", "success")
                return redirect(url_for("appointments"))
            except (ValueError, TypeError) as error:
                flash(str(error) or "Revisá los datos ingresados.", "danger")
            except sqlite3.IntegrityError:
                flash("Ese paciente o médico ya tiene un turno en el horario elegido.", "danger")
            doctor_id = request.form.get("doctor_id", type=int) or appointment["doctor_id"]
            date_value = request.form.get("appointment_date") or appointment["appointment_date"]
            try:
                slots = get_available_slots(doctor_id, parse_date(date_value), appointment_id)
            except ValueError:
                slots = []
        return render_template(
            "appointment_edit.html", appointment=appointment, doctors=doctors_list,
            patients=patients_list, selected_doctor=doctor_id, selected_date=date_value,
            slots=slots, today=date.today().isoformat(),
        )

    @app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
    @login_required
    def cancel_appointment(appointment_id):
        db = get_db()
        db.execute(
            "UPDATE appointments SET status='Cancelado' WHERE id=? AND status='Programado'",
            (appointment_id,),
        )
        db.commit()
        flash("El turno fue cancelado. El horario vuelve a quedar disponible.", "success")
        return redirect(url_for("appointments"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
