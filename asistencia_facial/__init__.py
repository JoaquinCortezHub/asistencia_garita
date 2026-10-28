"""Núcleo reutilizable del sistema de asistencias facial."""

from .attendance import CABECERA_CSV, registrar_evento
from .models import (
    Empleado,
    Reconocimiento,
    ResultadoComparacion,
    RostroCargado,
    TipoEvento,
)
from .recognition import (
    cargar_empleados,
    cargar_rostro_unico,
    comparar_rostros,
    reconocer_frame,
)

__all__ = [
    "CABECERA_CSV",
    "Empleado",
    "Reconocimiento",
    "ResultadoComparacion",
    "RostroCargado",
    "TipoEvento",
    "cargar_empleados",
    "cargar_rostro_unico",
    "comparar_rostros",
    "reconocer_frame",
    "registrar_evento",
]

