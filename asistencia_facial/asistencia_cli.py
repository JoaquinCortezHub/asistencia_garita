from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import cv2

from .attendance import registrar_evento
from .models import TipoEvento
from .recognition import cargar_empleados, reconocer_frame

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DEFAULT_EMPLEADOS = RAIZ_PROYECTO / "assets" / "empleados"
DEFAULT_REGISTRO = RAIZ_PROYECTO / "datos" / "registro.csv"


def _argumentos() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconoce empleados por webcam y registra su asistencia."
    )
    parser.add_argument("--tipo", choices=[evento.value for evento in TipoEvento], default="entrada")
    parser.add_argument("--camara", type=int, default=0)
    parser.add_argument("--empleados", type=Path, default=DEFAULT_EMPLEADOS)
    parser.add_argument("--registro", type=Path, default=DEFAULT_REGISTRO)
    parser.add_argument("--tolerancia", type=float, default=0.6)
    parser.add_argument("--modelo", choices=("hog", "cnn"), default="hog")
    parser.add_argument("--escala", type=float, default=0.25)
    parser.add_argument(
        "--sin-ventanas",
        action="store_true",
        help="Procesa frames sin mostrar la ventana; se detiene con Ctrl+C.",
    )
    return parser


def _dibujar_reconocimiento(frame, reconocimiento, estado: str = "") -> None:
    arriba, derecha, abajo, izquierda = reconocimiento.ubicacion
    color = (0, 190, 0) if reconocimiento.coincide else (0, 0, 220)
    cv2.rectangle(frame, (izquierda, arriba), (derecha, abajo), color, 2)
    distancia = (
        f" | {reconocimiento.distancia:.2f}"
        if reconocimiento.distancia is not None
        else ""
    )
    texto = f"{reconocimiento.nombre}{distancia}"
    if estado:
        texto += f" | {estado}"
    cv2.rectangle(
        frame,
        (izquierda, max(0, abajo - 32)),
        (derecha, abajo),
        color,
        cv2.FILLED,
    )
    cv2.putText(
        frame,
        texto,
        (izquierda + 6, max(20, abajo - 9)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def main(argv: list[str] | None = None) -> int:
    args = _argumentos().parse_args(argv)
    tipo = TipoEvento(args.tipo)
    try:
        empleados = cargar_empleados(args.empleados, modelo=args.modelo)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"Error al cargar empleados: {error}", file=sys.stderr)
        return 2

    captura = cv2.VideoCapture(args.camara)
    if not captura.isOpened():
        print(f"No se pudo abrir la cámara {args.camara}.", file=sys.stderr)
        captura.release()
        return 3

    claves_procesadas: set[tuple[str, str, str]] = set()
    try:
        while True:
            exito, frame = captura.read()
            if not exito or frame is None:
                print("No se pudo leer un frame de la cámara.", file=sys.stderr)
                return 3

            try:
                reconocimientos = reconocer_frame(
                    frame,
                    empleados,
                    tolerancia=args.tolerancia,
                    modelo=args.modelo,
                    escala=args.escala,
                )
            except (RuntimeError, ValueError) as error:
                print(f"Error procesando la cámara: {error}", file=sys.stderr)
                return 4

            fecha_actual = datetime.now().astimezone().date().isoformat()
            for reconocimiento in reconocimientos:
                estado = ""
                if reconocimiento.coincide and reconocimiento.id_empleado:
                    clave = (reconocimiento.id_empleado, fecha_actual, tipo.value)
                    if clave not in claves_procesadas:
                        try:
                            agregado = registrar_evento(
                                args.registro,
                                reconocimiento.id_empleado,
                                reconocimiento.nombre,
                                tipo,
                                reconocimiento.distancia or 0.0,
                            )
                        except (OSError, ValueError) as error:
                            print(f"Error al registrar asistencia: {error}", file=sys.stderr)
                            return 5
                        claves_procesadas.add(clave)
                        estado = "registrado" if agregado else "ya registrado"
                    else:
                        estado = "ya registrado"
                _dibujar_reconocimiento(frame, reconocimiento, estado)

            if not args.sin_ventanas:
                cv2.imshow("Asistencia facial (Q/Esc para salir)", frame)
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), 27):
                    break
    except KeyboardInterrupt:
        print("\nCaptura finalizada por el usuario.")
    finally:
        captura.release()
        cv2.destroyAllWindows()
    return 0

