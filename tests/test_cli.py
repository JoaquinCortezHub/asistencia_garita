from pathlib import Path

import numpy as np

from asistencia_facial import asistencia_cli
from asistencia_facial.models import Empleado


def test_asistencia_informa_camara_no_disponible(monkeypatch, tmp_path: Path) -> None:
    empleado = Empleado("empleado", "Empleado", Path("empleado.jpg"), np.zeros(128))
    monkeypatch.setattr(asistencia_cli, "cargar_empleados", lambda *_args, **_kwargs: [empleado])

    class CamaraCerrada:
        def isOpened(self):
            return False

        def release(self):
            return None

    monkeypatch.setattr(asistencia_cli.cv2, "VideoCapture", lambda _indice: CamaraCerrada())

    assert asistencia_cli.main(
        ["--camara", "99", "--sin-ventanas", "--registro", str(tmp_path / "registro.csv")]
    ) == 3

