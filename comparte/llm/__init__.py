"""Motores de lenguaje del Agente Captador y su fábrica."""

from __future__ import annotations

from ..config import Ajustes, obtener_ajustes
from .base import Extraccion, Extractor, Imagen, ItemExtraido
from .reglas import ExtractorReglas

__all__ = ["Extraccion", "Extractor", "Imagen", "ItemExtraido", "ExtractorReglas", "crear_extractor"]


def crear_extractor(ajustes: Ajustes | None = None) -> Extractor:
    """Elige el motor según ``COMPARTE_LLM`` y la presencia de ``ANTHROPIC_API_KEY``.

    * ``reglas``: siempre el motor de reglas.
    * ``claude``: Claude con respaldo a reglas; falla si no hay clave.
    * ``auto`` (defecto): Claude con respaldo a reglas si hay clave; si no, reglas.
    """
    ajustes = ajustes or obtener_ajustes()
    modo = ajustes.modo_llm
    if modo not in ("auto", "reglas", "claude"):
        raise ValueError(f"COMPARTE_LLM inválido: {modo!r} (usa auto, reglas o claude)")
    if modo == "reglas":
        return ExtractorReglas()
    if not ajustes.api_key:
        if modo == "claude":
            raise RuntimeError("COMPARTE_LLM=claude requiere definir ANTHROPIC_API_KEY")
        return ExtractorReglas()

    from .claude import ExtractorClaude, ExtractorConRespaldo

    return ExtractorConRespaldo(ExtractorClaude(ajustes.api_key, ajustes.modelo_claude), ExtractorReglas())
