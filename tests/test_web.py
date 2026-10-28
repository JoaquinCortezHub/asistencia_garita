from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest

from asistencia_facial import web
from asistencia_facial.models import Reconocimiento

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(tmp_path: Path):
    employees = tmp_path / "empleados"
    employees.mkdir()
    shutil.copy2(ROOT / "assets" / "pruebas" / "FotoA.jpg", employees / "Carl Sagan.jpg")
    return web.create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WEB_PASSWORD": "secret",
            "EMPLOYEES_DIR": employees,
            "ATTENDANCE_LOG": tmp_path / "registro.csv",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def authenticate(client) -> None:
    response = client.post("/login", data={"password": "secret"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def frame_upload() -> tuple[BytesIO, str]:
    success, encoded = cv2.imencode(".jpg", np.zeros((24, 24, 3), dtype=np.uint8))
    assert success
    return BytesIO(encoded.tobytes()), "capture.jpg"


def test_requires_authentication(client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_and_logout(client) -> None:
    rejected = client.post("/login", data={"password": "wrong"}, follow_redirects=True)
    assert rejected.status_code == 200
    assert "contraseña es incorrecta" in rejected.get_data(as_text=True)

    authenticate(client)
    logged_out = client.post("/logout")
    assert logged_out.status_code == 302
    assert logged_out.headers["Location"].endswith("/login")


def test_employee_gallery_and_image_are_protected(client) -> None:
    authenticate(client)

    gallery = client.get("/employees")
    image = client.get("/employees/images/Carl%20Sagan.jpg")

    assert gallery.status_code == 200
    assert "Carl Sagan" in gallery.get_data(as_text=True)
    assert image.status_code == 200
    assert image.content_type.startswith("image/")


def test_attendance_log_view_requires_authentication(client) -> None:
    response = client.get("/attendance")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_attendance_log_view_renders_and_filters_csv(client, app) -> None:
    app.config["ATTENDANCE_LOG"].write_text(
        "id_empleado,nombre,fecha,hora,tipo,distancia\n"
        "carl-sagan,Carl Sagan,2026-10-28,08:00:00,entrada,0.4000\n"
        "carl-sagan,Carl Sagan,2026-10-28,18:00:00,salida,0.4200\n"
        "otro-guardia,Otro Guardia,2026-10-27,09:00:00,entrada,0.3900\n",
        encoding="utf-8",
    )
    authenticate(client)

    response = client.get("/attendance")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Carl Sagan" in body
    assert "Otro Guardia" in body
    assert body.index("18:00:00") < body.index("08:00:00")

    filtered = client.get("/attendance?employee_id=carl-sagan&tipo=salida")
    filtered_body = filtered.get_data(as_text=True)

    assert filtered.status_code == 200
    assert "18:00:00" in filtered_body
    assert "08:00:00" not in filtered_body
    assert ">Otro Guardia</th>" not in filtered_body


def test_attendance_log_view_handles_missing_csv(client) -> None:
    authenticate(client)

    response = client.get("/attendance")

    assert response.status_code == 200
    assert "Todavía no hay marcaciones" in response.get_data(as_text=True)


def test_upload_validates_a_face_and_adds_employee(client, app) -> None:
    authenticate(client)
    source = ROOT / "assets" / "pruebas" / "FotoA.jpg"

    with source.open("rb") as image:
        response = client.post(
            "/employees/upload",
            data={"name": "Nuevo Guardia", "image": (image, "captura.jpg")},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert "Nuevo_Guardia.jpg" in {path.name for path in app.config["EMPLOYEES_DIR"].iterdir()}


def test_upload_rejects_invalid_image_without_creating_file(client, app) -> None:
    authenticate(client)

    response = client.post(
        "/employees/upload",
        data={"name": "Inválido", "image": (BytesIO(b"not-an-image"), "invalid.jpg")},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "No se pudo validar" in response.get_data(as_text=True)
    assert {path.name for path in app.config["EMPLOYEES_DIR"].iterdir()} == {"Carl Sagan.jpg"}


def test_delete_employee_preserves_csv(client, app) -> None:
    app.config["ATTENDANCE_LOG"].write_text(
        "id_empleado,nombre,fecha,hora,tipo,distancia\n"
        "carl-sagan,Carl Sagan,2026-10-28,08:00:00,entrada,0.4000\n",
        encoding="utf-8",
    )
    authenticate(client)

    response = client.post("/employees/carl-sagan/delete", follow_redirects=True)

    assert response.status_code == 200
    assert not (app.config["EMPLOYEES_DIR"] / "Carl Sagan.jpg").exists()
    assert "carl-sagan,Carl Sagan" in app.config["ATTENDANCE_LOG"].read_text(encoding="utf-8")


def test_recognition_registers_and_deduplicates_csv(client, app, monkeypatch) -> None:
    authenticate(client)
    recognized = Reconocimiento(True, "carl-sagan", "Carl Sagan", (1, 4, 5, 0), 0.31)
    monkeypatch.setattr(web, "reconocer_frame", lambda *_args, **_kwargs: [recognized])

    image, filename = frame_upload()
    first = client.post(
        "/api/attendance/recognize",
        data={"event_type": "entrada", "frame": (image, filename)},
        content_type="multipart/form-data",
    )
    image, filename = frame_upload()
    second = client.post(
        "/api/attendance/recognize",
        data={"event_type": "entrada", "frame": (image, filename)},
        content_type="multipart/form-data",
    )

    assert first.status_code == 200
    assert first.json["status"] == "registered"
    assert second.status_code == 200
    assert second.json["status"] == "duplicate"
    assert app.config["ATTENDANCE_LOG"].read_text(encoding="utf-8").count("carl-sagan") == 1


def test_recognition_does_not_write_for_multiple_faces(client, app, monkeypatch) -> None:
    authenticate(client)
    recognitions = [
        Reconocimiento(True, "one", "One", (1, 4, 5, 0), 0.31),
        Reconocimiento(True, "two", "Two", (2, 5, 6, 1), 0.32),
    ]
    monkeypatch.setattr(web, "reconocer_frame", lambda *_args, **_kwargs: recognitions)
    image, filename = frame_upload()

    response = client.post(
        "/api/attendance/recognize",
        data={"event_type": "entrada", "frame": (image, filename)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert response.json["status"] == "multiple_faces"
    assert not app.config["ATTENDANCE_LOG"].exists()
