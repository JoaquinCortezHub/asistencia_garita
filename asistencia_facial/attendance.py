from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import TipoEvento

CABECERA_CSV = [
    "id_empleado",
    "nombre",
    "fecha",
    "hora",
    "tipo",
    "distancia",
]


def _leer_claves_existentes(ruta: Path) -> set[tuple[str, str, str]]:
    if not ruta.exists() or ruta.stat().st_size == 0:
        return set()

    with ruta.open("r", newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames != CABECERA_CSV:
            raise ValueError(
                f"El archivo {ruta} no usa el esquema esperado: "
                f"{','.join(CABECERA_CSV)}."
            )
        return {
            (fila["id_empleado"], fila["fecha"], fila["tipo"])
            for fila in lector
            if fila.get("id_empleado")
        }


def registrar_evento(
    ruta_registro: str | Path,
    id_empleado: str,
    nombre: str,
    tipo: TipoEvento | str,
    distancia: float,
    momento: datetime | None = None,
) -> bool:
    """Agrega una marcación si no existe el mismo tipo para ese día.

    Devuelve True cuando se agregó una fila y False cuando era duplicada.
    """

    try:
        tipo_evento = tipo if isinstance(tipo, TipoEvento) else TipoEvento(tipo)
    except ValueError as error:
        raise ValueError("El tipo de evento debe ser 'entrada' o 'salida'.") from error

    if not id_empleado.strip() or not nombre.strip():
        raise ValueError("El empleado debe tener id y nombre.")
    if distancia < 0:
        raise ValueError("La distancia facial no puede ser negativa.")

    ruta = Path(ruta_registro)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    momento_local = momento or datetime.now().astimezone()
    if momento_local.tzinfo is None:
        momento_local = momento_local.astimezone()
    fecha = momento_local.date().isoformat()
    hora = momento_local.strftime("%H:%M:%S")
    clave = (id_empleado, fecha, tipo_evento.value)

    claves_existentes = _leer_claves_existentes(ruta)
    if clave in claves_existentes:
        return False

    necesita_cabecera = not ruta.exists() or ruta.stat().st_size == 0
    with ruta.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CABECERA_CSV)
        if necesita_cabecera:
            escritor.writeheader()
        escritor.writerow(
            {
                "id_empleado": id_empleado,
                "nombre": nombre,
                "fecha": fecha,
                "hora": hora,
                "tipo": tipo_evento.value,
                "distancia": f"{distancia:.4f}",
            }
        )
    return True

