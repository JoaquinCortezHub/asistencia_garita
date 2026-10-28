from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from asistencia_facial.attendance import CABECERA_CSV, registrar_evento
from asistencia_facial.models import TipoEvento


MENDOZA = ZoneInfo("America/Argentina/Mendoza")


def test_crea_csv_y_rechaza_duplicado_por_tipo_y_dia(tmp_path: Path) -> None:
    registro = tmp_path / "datos" / "registro.csv"
    momento = datetime(2026, 10, 18, 8, 30, 12, tzinfo=MENDOZA)

    assert registrar_evento(registro, "michio-kaku", "Michio Kaku", "entrada", 0.41, momento)
    assert not registrar_evento(registro, "michio-kaku", "Michio Kaku", "entrada", 0.42, momento)
    assert registrar_evento(registro, "michio-kaku", "Michio Kaku", TipoEvento.SALIDA, 0.43, momento)

    filas = registro.read_text(encoding="utf-8").splitlines()
    assert filas[0] == ",".join(CABECERA_CSV)
    assert "michio-kaku,Michio Kaku,2026-10-18,08:30:12,entrada,0.4100" in filas
    assert "michio-kaku,Michio Kaku,2026-10-18,08:30:12,salida,0.4300" in filas
    assert len(filas) == 3


def test_permite_misma_marcacion_en_otra_fecha(tmp_path: Path) -> None:
    registro = tmp_path / "registro.csv"
    assert registrar_evento(
        registro,
        "empleado",
        "Empleado",
        "entrada",
        0.2,
        datetime(2026, 10, 18, 8, 0, tzinfo=MENDOZA),
    )
    assert registrar_evento(
        registro,
        "empleado",
        "Empleado",
        "entrada",
        0.2,
        datetime(2026, 10, 19, 8, 0, tzinfo=MENDOZA),
    )


def test_rechaza_csv_del_material_original(tmp_path: Path) -> None:
    registro = tmp_path / "registro.csv"
    registro.write_text("nombre, hora\nMichio Kaku, 22:06:05\n", encoding="utf-8")

    with pytest.raises(ValueError, match="esquema esperado"):
        registrar_evento(registro, "empleado", "Empleado", "entrada", 0.2)


def test_valida_tipo_y_distancia(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="entrada.*salida"):
        registrar_evento(tmp_path / "registro.csv", "id", "Nombre", "pausa", 0.2)
    with pytest.raises(ValueError, match="negativa"):
        registrar_evento(tmp_path / "registro.csv", "id", "Nombre", "entrada", -0.1)

