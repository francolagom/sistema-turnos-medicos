"""Pruebas básicas de las funciones centrales del sistema."""
import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app
from db import get_db


class TurnosMedicosTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = os.path.join(self.temp_dir.name, "test.db")
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE": database,
        })
        self.client = self.app.test_client()
        response = self.client.post("/login", data={
            "username": "admin", "password": "admin1234"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _next_monday(self):
        days = (0 - date.today().weekday()) % 7
        if days == 0:
            days = 7
        return (date.today() + timedelta(days=days)).isoformat()

    def test_dashboard_requires_login(self):
        self.client.post("/logout")
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_invalid_login_is_rejected(self):
        self.client.post("/logout")
        response = self.client.post("/login", data={
            "username": "admin", "password": "incorrecta"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Usuario o contraseña incorrectos".encode("utf-8"), response.data)

    def test_overlapping_schedule_is_rejected(self):
        # El alta inicial crea agenda para el lunes de 09:00 a 12:00.
        response = self.client.post("/schedules", data={
            "doctor_id": "1", "weekday": "0", "start_time": "10:00",
            "end_time": "13:00", "slot_minutes": "30",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("superpone".encode("utf-8"), response.data)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) FROM schedules WHERE doctor_id=1 AND weekday=0"
            ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_patient_can_be_registered(self):
        response = self.client.post("/patients", data={
            "dni": "40123456", "first_name": "Juan", "last_name": "López",
            "phone": "1122334455", "email": "juan@example.com",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            patient = get_db().execute("SELECT * FROM patients WHERE dni='40123456'").fetchone()
            self.assertIsNotNone(patient)

    def test_schedule_with_active_appointment_cannot_be_deleted(self):
        day = self._next_monday()
        self.client.post("/appointments/new", data={
            "patient_id": "1", "doctor_id": "1", "appointment_date": day,
            "appointment_time": "09:00",
        }, follow_redirects=True)
        response = self.client.post("/schedules/1/delete", follow_redirects=True)
        self.assertIn("hay turnos programados".encode("utf-8"), response.data)
        with self.app.app_context():
            schedule = get_db().execute("SELECT id FROM schedules WHERE id=1").fetchone()
            self.assertIsNotNone(schedule)

    def test_booking_conflict_is_rejected_and_cancellation_releases_slot(self):
        day = self._next_monday()
        payload = {
            "patient_id": "1", "doctor_id": "1", "appointment_date": day,
            "appointment_time": "09:00",
        }
        first = self.client.post("/appointments/new", data=payload, follow_redirects=True)
        self.assertEqual(first.status_code, 200)
        with self.app.app_context():
            appointment = get_db().execute(
                "SELECT * FROM appointments WHERE appointment_date=? AND appointment_time='09:00'",
                (day,),
            ).fetchone()
            self.assertIsNotNone(appointment)
            appointment_id = appointment["id"]
        self.client.post("/appointments/new", data=payload, follow_redirects=True)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) FROM appointments WHERE appointment_date=? AND appointment_time='09:00' AND status='Programado'",
                (day,),
            ).fetchone()[0]
            self.assertEqual(count, 1)
        self.client.post(f"/appointments/{appointment_id}/cancel", follow_redirects=True)
        replacement = self.client.post("/appointments/new", data=payload, follow_redirects=True)
        self.assertEqual(replacement.status_code, 200)
        with self.app.app_context():
            active_count = get_db().execute(
                "SELECT COUNT(*) FROM appointments WHERE appointment_date=? AND appointment_time='09:00' AND status='Programado'",
                (day,),
            ).fetchone()[0]
            self.assertEqual(active_count, 1)


if __name__ == "__main__":
    unittest.main()
