"""Utilidades comunes a todos los agentes: bitácora de decisiones y avisos al donante.

Cada decisión relevante de un agente se registra con ``registrar_evento``. Esa bitácora cumple dos
funciones: es el **registro de auditoría de decisiones de agentes** que exige la sección 7 del
documento de visión, y es lo que la interfaz muestra como línea de tiempo para que se vea qué agente
hizo qué (y qué hizo el orquestador entre ellos).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .. import reloj
from ..modelos import Conversacion, Donacion, EventoAgente, Mensaje


def a_iso(momento: datetime | None) -> str | None:
    return momento.isoformat(timespec="minutes") if momento else None


def de_iso(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def fmt_momento(momento: datetime, ahora: datetime) -> str:
    """'hoy 20:00', 'mañana 08:30' o 'jue 12 nov 14:00' (para mensajes breves en pantallas pequeñas)."""
    dias = (momento.date() - ahora.date()).days
    if dias == 0:
        prefijo = "hoy"
    elif dias == 1:
        prefijo = "mañana"
    else:
        prefijo = f"{DIAS_CORTOS[momento.weekday()]} {momento.day} {MESES_CORTOS[momento.month - 1]}"
    return f"{prefijo} {momento:%H:%M}"


def fmt_kg(kg: float) -> str:
    """'25 kg', '2.5 kg' o '0.4 kg' sin ceros sobrantes."""
    return f"{kg:.1f}".rstrip("0").rstrip(".") + " kg"


def registrar_evento(
    db: Session,
    agente: str,
    accion: str,
    resumen: str,
    *,
    donacion_id: int | None = None,
    conversacion_id: int | None = None,
    detalle: dict | None = None,
) -> EventoAgente:
    """Agrega una entrada a la bitácora de auditoría (no hace commit)."""
    evento = EventoAgente(
        donacion_id=donacion_id,
        conversacion_id=conversacion_id,
        agente=agente,
        accion=accion,
        resumen=resumen,
        detalle=detalle or {},
        creado_en=reloj.ahora(),
    )
    db.add(evento)
    return evento


def decir(db: Session, conversacion: Conversacion, rol: str, texto: str, imagen: str | None = None) -> Mensaje:
    """Agrega un mensaje al chat del donante. ``rol`` es "donante" o el nombre de un agente."""
    mensaje = Mensaje(
        conversacion_id=conversacion.id, rol=rol, texto=texto, imagen=imagen, creado_en=reloj.ahora()
    )
    db.add(mensaje)
    db.flush()
    # Se recarga la colección en el siguiente acceso. (Agregar a conversacion.mensajes a mano duplica
    # el mensaje cuando la colección aún no estaba cargada.)
    db.expire(conversacion, ["mensajes"])
    return mensaje


def notificar_donante(db: Session, donacion: Donacion, agente: str, texto: str) -> None:
    """Avisa al donante por su chat. Si la donación no vino de una conversación, no hace nada."""
    if donacion.conversacion_id is None:
        return
    conversacion = db.get(Conversacion, donacion.conversacion_id)
    if conversacion is not None:
        decir(db, conversacion, agente, texto)
