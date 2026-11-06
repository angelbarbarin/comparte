"""Punto de entrada web: fábrica de la aplicación FastAPI (API en ``/api`` + interfaz en ``/``)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, select

from . import __version__, reloj
from .api.rutas import Contexto, construir_router
from .config import RAIZ, Ajustes, obtener_ajustes
from .datos_demo import sembrar_actores, sembrar_historial
from .db import crear_fabrica, crear_motor, crear_tablas
from .llm import Extractor, crear_extractor
from .modelos import Donante

log = logging.getLogger("comparte")


def crear_app(
    ajustes: Ajustes | None = None,
    motor: Engine | None = None,
    extractor: Extractor | None = None,
    datos_demo: bool = True,
    con_historial: bool = True,
    servir_web: bool = True,
) -> FastAPI:
    """Crea la aplicación.

    * ``datos_demo``: si la base está vacía, carga el piloto simulado (donantes, receptores, voluntarios).
    * ``con_historial``: además del piloto, carga el historial simulado de rescates.
    * Las pruebas pasan ``motor`` en memoria y ``extractor`` propio para no tocar disco ni red.
    """
    ajustes = ajustes or obtener_ajustes()
    motor = motor or crear_motor(ajustes.db_url)
    crear_tablas(motor)
    fabrica = crear_fabrica(motor)
    extractor = extractor or crear_extractor(ajustes)

    if ajustes.hora_demo:
        reloj.fijar_hora_hoy(ajustes.hora_demo)
        log.info("Reloj de demo fijado a las %s", ajustes.hora_demo)
    if datos_demo:
        with fabrica() as db:
            if db.scalar(select(Donante.id).limit(1)) is None:
                sembrar_actores(db)
                if con_historial:
                    sembrar_historial(db)

    app = FastAPI(
        title="ComParte API", version=__version__,
        description="Plataforma agéntica de rescate de alimentos (ODS 2). Agentes: Captador, Coordinador, "
                    "Logístico e Impacto, coordinados por un orquestador. MVP sin autenticación.",
    )
    app.include_router(construir_router(Contexto(ajustes=ajustes, motor=motor, fabrica=fabrica, extractor=extractor)))

    @app.exception_handler(LookupError)
    async def _no_encontrado(_: Request, exc: LookupError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _conflicto(_: Request, exc: ValueError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    if servir_web:
        # Fotos subidas por los donantes y la interfaz estática (debe montarse al final: captura "/").
        subidas = ajustes.carpeta_datos / "uploads"
        subidas.mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=subidas), name="uploads")
        app.mount("/", StaticFiles(directory=RAIZ / "web", html=True), name="web")
    return app
