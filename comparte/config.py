"""Configuración de ComParte.

Todo se lee de variables de entorno (opcionalmente desde un archivo ``.env`` en la raíz del
repositorio; ver ``.env.example``). Los valores por defecto permiten arrancar sin configurar nada:
base SQLite local y motor de lenguaje por reglas (sin costo y sin internet).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


@dataclass(frozen=True)
class Ajustes:
    """Valores de configuración ya interpretados."""

    db_url: str
    carpeta_datos: Path
    modo_llm: str  # "auto" | "reglas" | "claude"
    modelo_claude: str
    api_key: str | None
    vigencia_oferta_min: int  # tiempo que tiene un receptor para responder una oferta
    vigencia_recoleccion_min: int  # tiempo que tiene un voluntario para responder
    hora_demo: str | None  # "HH:MM": fija la hora de la demo (el reloj sigue corriendo desde ahí)
    velocidad_kmh: float  # velocidad media urbana usada para estimar tiempos de viaje
    factor_circuito: float  # distancia por calles = línea recta x factor


def _entero(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


def _decimal(nombre: str, defecto: float) -> float:
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


def obtener_ajustes() -> Ajustes:
    """Lee la configuración actual del entorno (se evalúa en cada llamada, útil en pruebas)."""
    carpeta = Path(os.getenv("COMPARTE_DATOS", RAIZ / "data"))
    return Ajustes(
        db_url=os.getenv("COMPARTE_DB_URL", f"sqlite:///{(carpeta / 'comparte.db').as_posix()}"),
        carpeta_datos=carpeta,
        modo_llm=os.getenv("COMPARTE_LLM", "auto").strip().lower(),
        modelo_claude=os.getenv("COMPARTE_MODELO", "claude-opus-5-5"),
        api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        vigencia_oferta_min=_entero("COMPARTE_VIGENCIA_OFERTA_MIN", 15),
        vigencia_recoleccion_min=_entero("COMPARTE_VIGENCIA_RECOLECCION_MIN", 10),
        hora_demo=os.getenv("COMPARTE_HORA_DEMO") or None,
        velocidad_kmh=_decimal("COMPARTE_VELOCIDAD_KMH", 25.0),
        factor_circuito=_decimal("COMPARTE_FACTOR_CIRCUITO", 1.3),
    )
