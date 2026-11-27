# Sistema de Gestión de Turnos Médicos

## Funcionalidades incluidas

- Inicio y cierre de sesión del personal administrativo.
- Panel con resumen de pacientes, profesionales y turnos programados.
- Registro, consulta, modificación y eliminación condicionada de pacientes.
- Registro y consulta de médicos.
- Configuración de días, franjas horarias y duración de turnos por médico.
- Consulta de disponibilidad y asignación de turnos.
- Búsqueda de turnos por paciente, médico o fecha.
- Modificación y cancelación de turnos.
- Validación para impedir que un médico o paciente tenga dos turnos activos en el mismo día y horario.
- Base de datos SQLite.

## Requisitos

- Python 3.10 o superior.
- pip.
- Un navegador web actualizado.

## Instalación y ejecución local

1. Descargar o clonar el repositorio.
2. Abrir una terminal en la carpeta del proyecto.
3. Crear un entorno virtual:

   ```bash
   python -m venv .venv
   ```

4. Activar el entorno virtual:

   **Windows (PowerShell):**
   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   **macOS / Linux:**
   ```bash
   source .venv/bin/activate
   ```

5. Instalar las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

6. Ejecutar la aplicación:

   ```bash
   python run.py
   ```

7. Abrir en el navegador la dirección que aparece en la terminal (por defecto `http://127.0.0.1:5000`).

La base de datos se crea automáticamente en `instance/turnos.db` y se carga información de demostración en la primera ejecución.

## Usuario de demostración

- **Usuario:** `admin`
- **Contraseña:** `admin1234`

## Estructura del proyecto

```text
turnos-medicos/
├── app.py                  # Rutas, validaciones y lógica de la aplicación
├── config.py               # Configuración
├── db.py                   # Esquema SQLite y datos iniciales
├── run.py                  # Punto de entrada
├── requirements.txt        # Dependencias
├── templates/              # Vistas HTML con Jinja
├── static/styles.css       # Estilos y diseño adaptable
├── instance/               # Base de datos local (no se sube a Git)
├── docs/                   # Diagramas y seguimiento del avance
└── tests/                  # Pruebas automatizadas básicas
```
