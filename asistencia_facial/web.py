from __future__ import annotations

import csv
import hmac
import re
import tempfile
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

import cv2
import numpy as np
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .attendance import CABECERA_CSV, registrar_evento
from .models import Empleado, Reconocimiento, TipoEvento
from .recognition import cargar_empleados, cargar_rostro_unico, reconocer_frame

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DEFAULT_EMPLEADOS = RAIZ_PROYECTO / "assets" / "empleados"
DEFAULT_REGISTRO = RAIZ_PROYECTO / "datos" / "registro.csv"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FRAME_BYTES = 5 * 1024 * 1024
EMPLOYEE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# This value is intentionally isolated for the requested local prototype.
WEB_PASSWORD = "contra123"
WEB_SECRET_KEY = "CAMBIAR_CLAVE_DE_SESION"

View = TypeVar("View", bound=Callable[..., Any])


def login_required(view: View) -> View:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


class EmployeeCatalog:
    """Filesystem-backed employee images with an in-memory encoding cache."""

    def __init__(self, directory: str | Path, model: str = "hog") -> None:
        self.directory = Path(directory).resolve()
        self.model = model
        self._employees: list[Empleado] | None = None

    def list(self) -> list[Empleado]:
        if self._employees is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._employees = cargar_empleados(self.directory, modelo=self.model)
        return list(self._employees)

    def invalidate(self) -> None:
        self._employees = None

    def add(self, name: str, image: FileStorage | None) -> Empleado:
        if image is None or not image.filename:
            raise ValueError("Seleccioná una imagen de empleado.")

        extension = Path(image.filename).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("La imagen debe ser JPG, JPEG, PNG o WEBP.")

        display_name = name.strip() or Path(image.filename).stem
        safe_stem = secure_filename(display_name).strip("._-")
        if not safe_stem:
            raise ValueError("El nombre del empleado no es válido.")

        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{safe_stem}{extension}"
        if target.exists():
            raise ValueError("Ya existe una imagen con ese nombre de empleado.")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.directory,
                prefix=".upload-",
                suffix=".upload",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                image.save(temporary)

            cargar_rostro_unico(temporary_path, modelo=self.model)
            temporary_path.replace(target)
            temporary_path = None
            self.invalidate()
            try:
                employees = self.list()
            except ValueError as error:
                target.unlink(missing_ok=True)
                self.invalidate()
                if "repetido" in str(error):
                    raise ValueError("El ID derivado del empleado ya existe.") from error
                raise
        except (OSError, RuntimeError, ValueError) as error:
            if target.exists() and self._employees is None:
                target.unlink(missing_ok=True)
                self.invalidate()
            if isinstance(error, ValueError):
                raise
            raise ValueError(f"No se pudo validar la imagen: {error}") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        added = next((employee for employee in employees if employee.ruta_imagen == target), None)
        if added is None:
            raise ValueError("La imagen no pudo incorporarse al padrón.")
        return added

    def remove(self, employee_id: str) -> Empleado:
        if not EMPLOYEE_ID_PATTERN.fullmatch(employee_id):
            raise ValueError("El ID de empleado no es válido.")

        employee = next(
            (item for item in self.list() if item.id_empleado == employee_id),
            None,
        )
        if employee is None:
            raise FileNotFoundError("No existe ese empleado.")

        employee_path = employee.ruta_imagen.resolve()
        if employee_path.parent != self.directory:
            raise ValueError("La imagen está fuera del directorio permitido.")
        employee_path.unlink()
        self.invalidate()
        return employee


def _decode_frame(raw: bytes) -> np.ndarray:
    if not raw:
        raise ValueError("La captura está vacía.")
    if len(raw) > MAX_FRAME_BYTES:
        raise ValueError("La captura supera el tamaño máximo permitido.")
    buffer = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None or frame.size == 0:
        raise ValueError("La captura no es una imagen válida.")
    return frame


def _employee_payload(recognition: Reconocimiento) -> dict[str, Any]:
    return {
        "id": recognition.id_empleado,
        "name": recognition.nombre,
        "distance": recognition.distancia,
    }


def _read_attendance_rows(path: str | Path) -> list[dict[str, str]]:
    """Read the existing attendance CSV without changing its source of truth."""

    attendance_path = Path(path)
    if not attendance_path.exists() or attendance_path.stat().st_size == 0:
        return []

    with attendance_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != CABECERA_CSV:
            raise ValueError("El CSV de asistencia no usa el esquema esperado.")
        return [
            {column: (row.get(column) or "") for column in CABECERA_CSV}
            for row in reader
            if row.get("id_empleado")
        ]


def _attendance_employee_options(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    options: dict[str, dict[str, str]] = {}
    for row in rows:
        employee_id = row["id_empleado"]
        if employee_id and employee_id not in options:
            options[employee_id] = {
                "id": employee_id,
                "name": row["nombre"] or employee_id,
            }
    return sorted(options.values(), key=lambda option: option["name"].casefold())


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(RAIZ_PROYECTO / "templates"),
        static_folder=str(RAIZ_PROYECTO / "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=WEB_SECRET_KEY,
        WEB_PASSWORD=WEB_PASSWORD,
        EMPLOYEES_DIR=DEFAULT_EMPLEADOS,
        ATTENDANCE_LOG=DEFAULT_REGISTRO,
        FACE_MODEL="hog",
        FACE_TOLERANCE=0.6,
        FRAME_SCALE=0.25,
        MAX_CONTENT_LENGTH=MAX_FRAME_BYTES,
    )
    if config:
        app.config.update(config)

    catalog = EmployeeCatalog(app.config["EMPLOYEES_DIR"], model=app.config["FACE_MODEL"])
    app.extensions["employee_catalog"] = catalog

    @app.get("/login")
    @app.post("/login")
    def login() -> Any:
        if session.get("authenticated"):
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            password = request.form.get("password", "")
            expected = str(app.config["WEB_PASSWORD"])
            if hmac.compare_digest(password, expected):
                session.clear()
                session["authenticated"] = True
                return redirect(url_for("dashboard"))
            flash("La contraseña es incorrecta.", "error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout() -> Any:
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard() -> Any:
        try:
            employees_count = len(catalog.list())
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            employees_count = 0
        return render_template(
            "dashboard.html",
            event_types=list(TipoEvento),
            employees_count=employees_count,
        )

    @app.get("/employees")
    @login_required
    def employees() -> Any:
        try:
            employee_list = catalog.list()
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            employee_list = []
            flash(f"No se pudo cargar el padrón: {error}", "error")
        return render_template("employees.html", employees=employee_list)

    @app.get("/attendance")
    @login_required
    def attendance_logs() -> Any:
        try:
            all_rows = _read_attendance_rows(app.config["ATTENDANCE_LOG"])
            csv_error = None
        except OSError:
            all_rows = []
            csv_error = "No se pudo leer el CSV de asistencia."
        except ValueError:
            all_rows = []
            csv_error = "El CSV de asistencia no usa el esquema esperado."

        if csv_error:
            flash(csv_error, "error")

        selected_employee = request.args.get("employee_id", "").strip()
        selected_type = request.args.get("tipo", "").strip()
        if selected_type not in {event_type.value for event_type in TipoEvento}:
            selected_type = ""

        rows = all_rows
        if selected_employee:
            rows = [row for row in rows if row["id_empleado"] == selected_employee]
        if selected_type:
            rows = [row for row in rows if row["tipo"] == selected_type]
        rows.sort(key=lambda row: (row["fecha"], row["hora"]), reverse=True)

        return render_template(
            "attendance.html",
            logs=rows,
            employees=_attendance_employee_options(all_rows),
            event_types=list(TipoEvento),
            selected_employee=selected_employee,
            selected_type=selected_type,
        )

    @app.post("/employees/upload")
    @login_required
    def upload_employee() -> Any:
        try:
            employee = catalog.add(request.form.get("name", ""), request.files.get("image"))
        except (OSError, RuntimeError, ValueError) as error:
            flash(str(error), "error")
        else:
            flash(f"Empleado {employee.nombre} cargado correctamente.", "success")
        return redirect(url_for("employees"))

    @app.post("/employees/<employee_id>/delete")
    @login_required
    def delete_employee(employee_id: str) -> Any:
        try:
            employee = catalog.remove(employee_id)
        except (FileNotFoundError, OSError, ValueError) as error:
            flash(str(error), "error")
        else:
            flash(
                f"Se eliminó la imagen de {employee.nombre}. Los logs históricos se conservaron.",
                "success",
            )
        return redirect(url_for("employees"))

    @app.get("/employees/images/<path:filename>")
    @login_required
    def employee_image(filename: str) -> Any:
        if Path(filename).name != filename:
            abort(404)
        try:
            allowed = {employee.ruta_imagen.name for employee in catalog.list()}
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            abort(404)
        if filename not in allowed:
            abort(404)
        return send_from_directory(str(catalog.directory), filename)

    @app.post("/api/attendance/recognize")
    @login_required
    def recognize_attendance() -> Any:
        event_type = request.form.get("event_type", "")
        try:
            tipo = TipoEvento(event_type)
            frame_file = request.files.get("frame")
            if frame_file is None:
                raise ValueError("No se recibió una captura de la cámara.")
            frame = _decode_frame(frame_file.read())
            recognitions = reconocer_frame(
                frame,
                catalog.list(),
                tolerancia=float(app.config["FACE_TOLERANCE"]),
                modelo=str(app.config["FACE_MODEL"]),
                escala=float(app.config["FRAME_SCALE"]),
            )
        except (OSError, RuntimeError, ValueError, cv2.error) as error:
            return jsonify(status="error", message=str(error)), 422

        if not recognitions:
            return jsonify(status="no_face", message="No se detectó ningún rostro."), 422
        if len(recognitions) != 1:
            return jsonify(
                status="multiple_faces",
                message="La captura debe contener un único rostro.",
            ), 422

        recognition = recognitions[0]
        if not recognition.coincide or not recognition.id_empleado:
            return jsonify(status="unknown", message="El rostro no pertenece al padrón."), 422

        try:
            added = registrar_evento(
                app.config["ATTENDANCE_LOG"],
                recognition.id_empleado,
                recognition.nombre,
                tipo,
                recognition.distancia or 0.0,
            )
        except (OSError, ValueError) as error:
            return jsonify(status="error", message=str(error)), 422

        status = "registered" if added else "duplicate"
        message = "Marcación registrada." if added else "Esta marcación ya estaba registrada hoy."
        return jsonify(
            status=status,
            message=message,
            employee=_employee_payload(recognition),
            event_type=tipo.value,
        )

    return app


def main() -> None:
    create_app().run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
