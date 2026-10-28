from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from .recognition import cargar_rostro_unico, comparar_rostros

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DEFAULT_CONTROL = RAIZ_PROYECTO / "assets" / "pruebas" / "FotoA.jpg"
DEFAULT_PRUEBA = RAIZ_PROYECTO / "assets" / "pruebas" / "FotoB.jpg"


def _argumentos() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compara dos imágenes y muestra la distancia facial."
    )
    parser.add_argument("--control", type=Path, default=DEFAULT_CONTROL)
    parser.add_argument("--prueba", type=Path, default=DEFAULT_PRUEBA)
    parser.add_argument("--tolerancia", type=float, default=0.6)
    parser.add_argument("--modelo", choices=("hog", "cnn"), default="hog")
    parser.add_argument(
        "--sin-ventanas",
        action="store_true",
        help="No abre ventanas; útil para servidores o pruebas sin escritorio.",
    )
    return parser


def _rectangulo(imagen, ubicacion, color) -> None:
    arriba, derecha, abajo, izquierda = ubicacion
    cv2.rectangle(imagen, (izquierda, arriba), (derecha, abajo), color, 2)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos().parse_args(argv)
    try:
        rostro_control = cargar_rostro_unico(args.control, modelo=args.modelo)
        rostro_prueba = cargar_rostro_unico(args.prueba, modelo=args.modelo)
        resultado = comparar_rostros(rostro_control, rostro_prueba, args.tolerancia)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    estado = "COINCIDE" if resultado.coincide else "NO COINCIDE"
    print(f"Resultado: {estado}")
    print(f"Distancia facial: {resultado.distancia:.4f}")
    print(f"Tolerancia: {args.tolerancia:.2f}")

    if args.sin_ventanas:
        return 0

    control_bgr = cv2.cvtColor(rostro_control.imagen_rgb.copy(), cv2.COLOR_RGB2BGR)
    prueba_bgr = cv2.cvtColor(rostro_prueba.imagen_rgb.copy(), cv2.COLOR_RGB2BGR)
    _rectangulo(control_bgr, rostro_control.ubicacion, (0, 255, 0))
    _rectangulo(prueba_bgr, rostro_prueba.ubicacion, (0, 255, 0))
    cv2.putText(
        prueba_bgr,
        f"{estado} | distancia {resultado.distancia:.2f}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 180, 0) if resultado.coincide else (0, 0, 220),
        2,
        cv2.LINE_AA,
    )
    try:
        cv2.imshow("Foto de control", control_bgr)
        cv2.imshow("Foto de prueba", prueba_bgr)
        cv2.waitKey(0)
    finally:
        cv2.destroyAllWindows()
    return 0

