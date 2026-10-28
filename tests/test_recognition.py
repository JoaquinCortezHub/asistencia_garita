from pathlib import Path

import numpy as np
import pytest

from asistencia_facial import recognition
from asistencia_facial.models import Empleado, RostroCargado


ROOT = Path(__file__).resolve().parents[1]
EMPLOYEES = ROOT / "assets" / "empleados"
PRUEBAS = ROOT / "assets" / "pruebas"


def test_material_real_tiene_un_rostro_por_imagen() -> None:
    empleados = recognition.cargar_empleados(EMPLOYEES)
    assert len(empleados) == 7
    assert {empleado.nombre for empleado in empleados} == {
        "Carl Sagan",
        "Cosmo Kramer",
        "Elaine Benes",
        "George Constanza",
        "Jerry Seinfeld",
        "Michio Kaku",
        "Neil deGrasse Tyson",
    }


def test_fotos_de_prueba_coinciden_y_no_coinciden() -> None:
    control = recognition.cargar_rostro_unico(PRUEBAS / "FotoA.jpg")
    misma_persona = recognition.cargar_rostro_unico(PRUEBAS / "FotoB.jpg")
    otra_persona = recognition.cargar_rostro_unico(PRUEBAS / "FotoC.jpg")

    positiva = recognition.comparar_rostros(control, misma_persona)
    negativa = recognition.comparar_rostros(control, otra_persona)

    assert positiva.coincide
    assert positiva.distancia < 0.6
    assert positiva.distancia == pytest.approx(0.4099, abs=0.02)
    assert not negativa.coincide
    assert negativa.distancia > 0.6
    assert negativa.distancia == pytest.approx(0.8086, abs=0.02)


def test_imagen_sin_rostro_es_rechazada(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    imagen = tmp_path / "sin-rostro.jpg"
    imagen.write_bytes(b"contenido de prueba")
    monkeypatch.setattr(recognition.fr, "load_image_file", lambda _: np.zeros((10, 10, 3), dtype=np.uint8))
    monkeypatch.setattr(recognition.fr, "face_locations", lambda *_args, **_kwargs: [])

    with pytest.raises(ValueError, match="exactamente un rostro"):
        recognition.cargar_rostro_unico(imagen)


def test_directorio_vacio_es_rechazado(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="imágenes.*válidas"):
        recognition.cargar_empleados(tmp_path)


def test_reconocer_frame_selecciona_la_menor_distancia(monkeypatch: pytest.MonkeyPatch) -> None:
    empleados = [
        Empleado("uno", "Uno", Path("uno.jpg"), np.zeros(128)),
        Empleado("dos", "Dos", Path("dos.jpg"), np.ones(128)),
    ]
    objetivo = np.full(128, 0.5)
    monkeypatch.setattr(recognition.fr, "face_locations", lambda *_args, **_kwargs: [(1, 4, 5, 0)])
    monkeypatch.setattr(recognition.fr, "face_encodings", lambda *_args, **_kwargs: [objetivo])
    monkeypatch.setattr(recognition.fr, "face_distance", lambda conocidos, _objetivo: np.array([0.8, 0.3]))
    monkeypatch.setattr(recognition.fr, "compare_faces", lambda *_args, **_kwargs: [False, True])

    reconocimientos = recognition.reconocer_frame(np.zeros((40, 40, 3), dtype=np.uint8), empleados)

    assert len(reconocimientos) == 1
    assert reconocimientos[0].coincide
    assert reconocimientos[0].id_empleado == "dos"
    assert reconocimientos[0].distancia == pytest.approx(0.3)
    assert reconocimientos[0].ubicacion == (4, 16, 20, 0)

