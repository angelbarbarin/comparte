"""Acceso a la base de datos (SQLAlchemy 2.0).

Por defecto usa SQLite en ``data/comparte.db``. El modelo no depende de SQLite: para pasar a
PostgreSQL basta con cambiar ``COMPARTE_DB_URL`` (p. ej. ``postgresql+psycopg://...``).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import obtener_ajustes


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos (ver ``modelos.py``)."""


def crear_motor(url: str | None = None) -> Engine:
    """Crea el motor de base de datos. Para SQLite en memoria comparte una sola conexión."""
    ajustes = obtener_ajustes()
    url = url or ajustes.db_url
    argumentos: dict = {}
    if url.startswith("sqlite"):
        argumentos["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            argumentos["poolclass"] = StaticPool
        else:
            ajustes.carpeta_datos.mkdir(parents=True, exist_ok=True)
    return create_engine(url, **argumentos)


def crear_fabrica(motor: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=motor, expire_on_commit=False)


def crear_tablas(motor: Engine) -> None:
    from . import modelos  # noqa: F401  (registra los modelos en Base.metadata)

    Base.metadata.create_all(motor)


def reiniciar_tablas(motor: Engine) -> None:
    """Borra y vuelve a crear todas las tablas (solo para la demo)."""
    from . import modelos  # noqa: F401

    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)


def sesion_por_peticion(fabrica: sessionmaker[Session]):
    """Genera la dependencia de FastAPI que entrega una sesión por petición."""

    def _dependencia() -> Iterator[Session]:
        sesion = fabrica()
        try:
            yield sesion
        finally:
            sesion.close()

    return _dependencia
