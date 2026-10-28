from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import cv2
import face_recognition as fr
import numpy as np

from .models import (
    Empleado,
    Reconocimiento,
    ResultadoComparacion,
    RostroCargado,
    UbicacionRostro,
)

logger = logging.getLogger(__name__)
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}


def _validar_tolerancia(tolerancia: float) -> None:
    if not 0 < tolerancia <= 1:
        raise ValueError("La tolerancia debe ser mayor que 0 y menor o igual que 1.")


def _id_desde_nombre(nombre: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nombre)
    sin_acentos = normalizado.encode("ascii", "ignore").decode("ascii")
    identificador = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos).strip("-").lower()
    if not identificador:
        raise ValueError(f"No se pudo construir un id para el archivo {nombre!r}.")
    return identificador


def cargar_rostro_unico(ruta: str | Path, modelo: str = "hog") -> RostroCargado:
    """Carga una imagen y exige exactamente un rostro codificable."""

    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la imagen: {ruta}")

    imagen_rgb = fr.load_image_file(str(ruta))
    ubicaciones = fr.face_locations(imagen_rgb, model=modelo)
    if len(ubicaciones) != 1:
        raise ValueError(
            f"La imagen {ruta.name!r} debe contener exactamente un rostro; "
            f"se detectaron {len(ubicaciones)}."
        )

    codificaciones = fr.face_encodings(imagen_rgb, known_face_locations=ubicaciones)
    if len(codificaciones) != 1:
        raise ValueError(f"No se pudo codificar el rostro de {ruta.name!r}.")

    return RostroCargado(
        ruta=ruta,
        imagen_rgb=imagen_rgb,
        ubicacion=tuple(int(valor) for valor in ubicaciones[0]),  # type: ignore[arg-type]
        codificacion=codificaciones[0],
    )


def comparar_rostros(
    rostro_control: RostroCargado,
    rostro_prueba: RostroCargado,
    tolerancia: float = 0.6,
) -> ResultadoComparacion:
    """Compara dos rostros ya cargados y devuelve distancia y decisión."""

    _validar_tolerancia(tolerancia)
    coincidencias = fr.compare_faces(
        [rostro_control.codificacion],
        rostro_prueba.codificacion,
        tolerance=tolerancia,
    )
    distancia = float(
        fr.face_distance([rostro_control.codificacion], rostro_prueba.codificacion)[0]
    )
    return ResultadoComparacion(
        coincide=bool(coincidencias[0]),
        distancia=distancia,
        ubicacion_control=rostro_control.ubicacion,
        ubicacion_prueba=rostro_prueba.ubicacion,
    )


def cargar_empleados(
    directorio: str | Path,
    modelo: str = "hog",
) -> list[Empleado]:
    """Carga imágenes válidas del directorio y prepara sus codificaciones."""

    directorio = Path(directorio)
    if not directorio.is_dir():
        raise FileNotFoundError(f"No existe el directorio de empleados: {directorio}")

    empleados: list[Empleado] = []
    ids_vistos: set[str] = set()
    for ruta in sorted(directorio.iterdir(), key=lambda item: item.name.lower()):
        if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES_IMAGEN:
            continue

        try:
            id_empleado = _id_desde_nombre(ruta.stem)
        except ValueError as error:
            logger.warning("Se omite %s: %s", ruta.name, error)
            continue
        if id_empleado in ids_vistos:
            raise ValueError(f"El id de empleado {id_empleado!r} está repetido en la base.")

        try:
            rostro = cargar_rostro_unico(ruta, modelo=modelo)
            empleados.append(
                Empleado(
                    id_empleado=id_empleado,
                    nombre=ruta.stem,
                    ruta_imagen=ruta,
                    codificacion=rostro.codificacion,
                )
            )
            ids_vistos.add(id_empleado)
        except (OSError, RuntimeError, ValueError, IndexError) as error:
            logger.warning("Se omite %s: %s", ruta.name, error)

    if not empleados:
        raise ValueError(
            f"No hay imágenes de empleados válidas en {directorio}."
        )
    return empleados


def _escalar_ubicacion(ubicacion: tuple[int, int, int, int], escala: float) -> UbicacionRostro:
    return tuple(int(round(valor / escala)) for valor in ubicacion)  # type: ignore[return-value]


def reconocer_frame(
    frame_bgr: np.ndarray,
    empleados: list[Empleado],
    tolerancia: float = 0.6,
    modelo: str = "hog",
    escala: float = 0.25,
) -> list[Reconocimiento]:
    """Detecta y reconoce todos los rostros de un frame BGR de OpenCV."""

    _validar_tolerancia(tolerancia)
    if not empleados:
        raise ValueError("No hay empleados cargados para reconocer.")
    if frame_bgr is None or frame_bgr.size == 0:
        raise ValueError("Se recibió un frame vacío de la cámara.")
    if not 0 < escala <= 1:
        raise ValueError("La escala del frame debe estar entre 0 y 1.")

    frame_reducido = cv2.resize(
        frame_bgr,
        None,
        fx=escala,
        fy=escala,
        interpolation=cv2.INTER_AREA,
    )
    frame_rgb = cv2.cvtColor(frame_reducido, cv2.COLOR_BGR2RGB)
    ubicaciones = fr.face_locations(frame_rgb, model=modelo)
    codificaciones = fr.face_encodings(frame_rgb, known_face_locations=ubicaciones)
    codificaciones_conocidas = [empleado.codificacion for empleado in empleados]

    reconocimientos: list[Reconocimiento] = []
    for ubicacion, codificacion in zip(ubicaciones, codificaciones):
        distancias = fr.face_distance(codificaciones_conocidas, codificacion)
        indice = int(np.argmin(distancias))
        distancia = float(distancias[indice])
        coincidencias = fr.compare_faces(
            codificaciones_conocidas,
            codificacion,
            tolerance=tolerancia,
        )
        coincide = bool(coincidencias[indice])
        empleado = empleados[indice]
        reconocimientos.append(
            Reconocimiento(
                coincide=coincide,
                id_empleado=empleado.id_empleado if coincide else None,
                nombre=empleado.nombre if coincide else "Desconocido",
                ubicacion=_escalar_ubicacion(tuple(ubicacion), escala),
                distancia=distancia,
            )
        )
    return reconocimientos
