"""Línea de comandos: ``python -m comparte <comando>``.

    python -m comparte servir            # arranca la aplicación (API + interfaz) en http://127.0.0.1:8000
    python -m comparte reiniciar         # borra la base y recarga el piloto simulado
    python -m comparte servir --hora-demo 16:00 --reiniciar   # lo típico antes de grabar el video
"""

from __future__ import annotations

import argparse
import logging
import os

import uvicorn

from .config import obtener_ajustes
from .datos_demo import reiniciar_demo
from .db import crear_fabrica, crear_motor


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m comparte", description="ComParte: rescate de alimentos con agentes")
    sub = parser.add_subparsers(dest="comando")

    servir = sub.add_parser("servir", help="Arranca la API y la interfaz web")
    servir.add_argument("--host", default="127.0.0.1")
    servir.add_argument("--puerto", type=int, default=8000)
    servir.add_argument("--hora-demo", metavar="HH:MM", help="Fija la hora de la aplicación (útil para grabar a cualquier hora)")
    servir.add_argument("--reiniciar", action="store_true", help="Borra y recarga los datos de prueba antes de arrancar")
    servir.add_argument("--sin-historial", action="store_true", help="Con --reiniciar: no carga los rescates históricos simulados")

    reinicio = sub.add_parser("reiniciar", help="Borra la base y recarga el piloto simulado")
    reinicio.add_argument("--sin-historial", action="store_true", help="No carga los rescates históricos simulados")
    reinicio.add_argument("--hora-demo", metavar="HH:MM")

    args = parser.parse_args(argv)
    comando = args.comando or "servir"
    if args.comando is None:
        args = parser.parse_args(["servir"])

    if getattr(args, "hora_demo", None):
        os.environ["COMPARTE_HORA_DEMO"] = args.hora_demo  # lo lee obtener_ajustes()
    ajustes = obtener_ajustes()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if comando == "reiniciar" or getattr(args, "reiniciar", False):
        motor = crear_motor(ajustes.db_url)
        conteos = reiniciar_demo(motor, crear_fabrica(motor), ajustes.hora_demo,
                                 con_historial=not getattr(args, "sin_historial", False))
        print("Datos de demostración cargados:", conteos)
        motor.dispose()
        if comando == "reiniciar":
            return

    from .main import crear_app

    app = crear_app(ajustes)
    print(f"ComParte en http://{args.host}:{args.puerto}  (documentación de la API en /docs)")
    uvicorn.run(app, host=args.host, port=args.puerto, log_level="info")


if __name__ == "__main__":
    main()
