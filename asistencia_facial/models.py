from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np

UbicacionRostro = tuple[int, int, int, int]


class TipoEvento(StrEnum):
    """Tipos de marcación que soporta el primer hito."""

    ENTRADA = "entrada"
    SALIDA = "salida"


@dataclass(frozen=True)
class RostroCargado:
    ruta: Path
    imagen_rgb: np.ndarray
    ubicacion: UbicacionRostro
    codificacion: np.ndarray


@dataclass(frozen=True)
class Empleado:
    id_empleado: str
    nombre: str
    ruta_imagen: Path
    codificacion: np.ndarray


@dataclass(frozen=True)
class ResultadoComparacion:
    coincide: bool
    distancia: float
    ubicacion_control: UbicacionRostro
    ubicacion_prueba: UbicacionRostro


@dataclass(frozen=True)
class Reconocimiento:
    coincide: bool
    id_empleado: str | None
    nombre: str
    ubicacion: UbicacionRostro
    distancia: float | None

