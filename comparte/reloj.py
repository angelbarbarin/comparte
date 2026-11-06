"""Reloj único del sistema.

Todo el código pide la hora aquí (``reloj.ahora()``) en lugar de usar ``datetime.now()``. Eso permite:

* **Pruebas deterministas**: ``congelar(datetime(...))`` detiene el tiempo.
* **Demo reproducible**: ``fijar_hora_hoy("17:30")`` hace que la aplicación crea que son las 17:30
  (y el tiempo siga corriendo desde ahí). Así el video no depende de la hora real de grabación
  (por ejemplo, de noche todos los receptores estarían cerrados).
* **Simular el paso del tiempo**: ``avanzar(15)`` para demostrar vencimientos de ofertas.

Las fechas del sistema son *naive* (sin zona) y siempre en hora local del AMG
(``America/Mexico_City``). El proyecto solo opera en esa zona.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Mexico_City")

_congelado: datetime | None = None
_desfase: timedelta = timedelta(0)


def _real() -> datetime:
    return datetime.now(ZONA).replace(tzinfo=None)


def ahora() -> datetime:
    """Hora actual del sistema en el AMG (con el desfase de demo si lo hay)."""
    if _congelado is not None:
        return _congelado
    return _real() + _desfase


def congelar(momento: datetime) -> None:
    """Detiene el reloj en ``momento`` (uso en pruebas)."""
    global _congelado
    _congelado = momento


def avanzar(minutos: float) -> datetime:
    """Adelanta el reloj ``minutos``. Devuelve la nueva hora."""
    global _congelado, _desfase
    delta = timedelta(minutes=minutos)
    if _congelado is not None:
        _congelado = _congelado + delta
    else:
        _desfase = _desfase + delta
    return ahora()


def fijar_hora_hoy(hhmm: str) -> datetime:
    """Hace que ahora sean las ``hhmm`` (formato ``"17:30"``) de hoy; el tiempo sigue corriendo."""
    global _congelado, _desfase
    hora, minuto = (int(x) for x in hhmm.split(":"))
    real = _real()
    objetivo = real.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    _congelado = None
    _desfase = objetivo - real
    return ahora()


def restablecer() -> None:
    """Vuelve a la hora real."""
    global _congelado, _desfase
    _congelado = None
    _desfase = timedelta(0)


def hay_desfase() -> bool:
    return _congelado is not None or _desfase != timedelta(0)


def fin_del_dia(momento: datetime) -> datetime:
    """23:59 del mismo día que ``momento`` (convención para "caduca hoy")."""
    return datetime.combine(momento.date(), time(23, 59))


def a_hora(hhmm: str, dia: datetime) -> datetime:
    """Combina un ``"HH:MM"`` con la fecha de ``dia``."""
    hora, minuto = (int(x) for x in hhmm.split(":"))
    return datetime.combine(dia.date(), time(hora, minuto))
