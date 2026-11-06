"""Interpretación de fechas y horas en español coloquial para el motor de reglas.

Trabaja sobre texto **ya normalizado y alineado** (minúsculas, sin acentos, misma longitud que el
original; ver ``reglas._alinear``) para poder devolver las posiciones (``spans``) de lo que se
interpretó y así quitarlo del texto antes de buscar cantidades.

Qué entiende
------------
Caducidad (se reconoce por una palabra clave como "caduca", "vence", "consumir antes"):
  "caduca hoy", "caduca mañana", "vence el viernes", "caduca el 15 de noviembre", "caduca 15/11",
  "caduca en 2 días", "caduca en 3 horas", "caduca a las 11 pm".
Ventana de recolección:
  "entre las 6 y las 8 pm", "de 6 a 8 pm", "después de las 8 pm", "a partir de las 5",
  "antes de las 9", "hasta las 10", "a las 7", "20:30".

Limitaciones conocidas (documentadas a propósito): "de 6 a 8" sin "las", "pm" ni ":" no se toma
como horario (se confundiría con cantidades como "de 25 a 30 kg"); no entiende "esta noche" ni
fechas escritas con palabras ("el quince de noviembre").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .. import reloj
from ..conocimiento.catalogo import UNIDAD_CANONICA

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
}
NUMEROS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "quince": 15,
    "veinte": 20, "medio": 0.5, "media": 0.5,
}

_PALABRAS_CLAVE_CADUCIDAD = re.compile(
    r"caduc\w*|venc\w*|consumir antes|consumo preferente|fecha de caducidad|\bcad\b"
)
_DEL_DIA = re.compile(r"\b(?:del dia|de hoy|horneado hoy|hecho hoy|recien horneado)\b")

_NUM = r"(\d{1,2})(?::(\d{2}))?"
_SUF = (
    r"\s*(am|pm|hrs|hs|horas|h|(?:de|en) la (?:tarde|noche|manana|madrugada))?"
)
_RANGO = re.compile(
    rf"\b(?:entre|de|desde)\s+(?:las?\s+)?{_NUM}{_SUF}\s*(?:y|a|hasta)\s+(?:las?\s+)?{_NUM}{_SUF}\b"
)
_PUNTUAL = re.compile(
    rf"\b(despues de|a partir de|desde|antes de|hasta|para|como a|a)\s+las?\s+{_NUM}{_SUF}\b"
)
_HHMM = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm|hrs|hs|h)?\b")
_AMPM = re.compile(r"\b(\d{1,2})\s*(am|pm)\b")

_FECHA_NUM = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_DIA_MES = re.compile(rf"\b(\d{{1,2}}) de ({'|'.join(MESES)})(?: de (\d{{4}}))?\b")
_EN_N = re.compile(
    rf"\ben (\d+|{'|'.join(NUMEROS)}) (dias?|horas?|semanas?|minutos?)\b"
)
_RELATIVA = re.compile(r"\b(pasado manana|manana|hoy)\b")
_DIA_SEM = re.compile(rf"\b(?:el |este |para el )?({'|'.join(DIAS_SEMANA)})\b")
_UNIDADES = "|".join(sorted(map(re.escape, UNIDAD_CANONICA), key=len, reverse=True))
_SIGUE_UNIDAD = re.compile(rf"^\s*(?:{_UNIDADES})(?![a-z0-9])")


@dataclass
class Tiempos:
    caduca_en: datetime | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
    spans: list[tuple[int, int]] = field(default_factory=list)  # lo ya interpretado


def _normalizar_sufijo(sufijo: str | None) -> str:
    """'de la noche' -> 'pm', 'de la mañana' -> 'am'; 'h', 'hrs'... se dejan tal cual."""
    if not sufijo:
        return ""
    if "tarde" in sufijo or "noche" in sufijo:
        return "pm"
    if "manana" in sufijo or "madrugada" in sufijo:
        return "am"
    return sufijo


def _hora(h: str, m: str | None, sufijo: str | None, ahora: datetime) -> time | None:
    """Convierte hora y minuto con am/pm opcional. Sin sufijo se infiere pm para 1-7 h."""
    hora, minuto = int(h), int(m or 0)
    if hora > 24 or minuto > 59:
        return None
    sufijo = _normalizar_sufijo(sufijo)
    if sufijo == "pm" and hora < 12:
        hora += 12
    elif sufijo == "am" and hora == 12:
        hora = 0
    elif sufijo == "":
        if 1 <= hora <= 7:
            hora += 12
        elif 8 <= hora <= 11 and ahora.hour >= 12:
            hora += 12
    return time(hora % 24, minuto)


def _hay_palabra_clave_antes(t: str, pos: int, ventana: int = 30) -> bool:
    """¿Hay "caduca/vence..." justo antes de ``pos`` **en la misma frase** (sin coma ni punto en medio)?"""
    antes = re.split(r"[,.;]", t[max(0, pos - ventana):pos])[-1]
    return bool(_PALABRAS_CLAVE_CADUCIDAD.search(antes))


def _traslapa(spans: list[tuple[int, int]], ini: int, fin: int) -> bool:
    return any(ini < f and ini_ < fin for ini_, f in spans)


def _dia_base(t: str, pos: int, ahora: datetime) -> date:
    """Día al que se refiere una hora suelta: mañana si lo dicen justo antes, si no hoy."""
    contexto = t[max(0, pos - 25):pos]
    if "pasado manana" in contexto:
        return (ahora + timedelta(days=2)).date()
    if "manana" in contexto and not _PALABRAS_CLAVE_CADUCIDAD.search(contexto):
        return (ahora + timedelta(days=1)).date()
    return ahora.date()


def _fecha_con_year(dia: int, mes: int, year: int | None, ahora: datetime) -> date | None:
    try:
        if year is None:
            candidata = date(ahora.year, mes, dia)
            return candidata if candidata >= ahora.date() else date(ahora.year + 1, mes, dia)
        if year < 100:
            year += 2000
        return date(year, mes, dia)
    except ValueError:
        return None


def analizar_tiempos(t: str, ahora: datetime) -> Tiempos:
    """Extrae caducidad y ventana de recolección de ``t`` (texto normalizado y alineado)."""
    res = Tiempos()

    # -- 1) Fechas con palabra clave de caducidad -----------------------------------------------
    for m in _FECHA_NUM.finditer(t):
        if not _hay_palabra_clave_antes(t, m.start(), 35):
            continue
        d, mes, y = int(m.group(1)), int(m.group(2)), m.group(3)
        fecha = _fecha_con_year(d, mes, int(y) if y else None, ahora)
        if fecha:
            res.caduca_en = datetime.combine(fecha, time(23, 59))
            res.spans.append(m.span())
    for m in _DIA_MES.finditer(t):
        if not _hay_palabra_clave_antes(t, m.start(), 35):
            continue
        fecha = _fecha_con_year(int(m.group(1)), MESES[m.group(2)], int(m.group(3)) if m.group(3) else None, ahora)
        if fecha:
            res.caduca_en = datetime.combine(fecha, time(23, 59))
            res.spans.append(m.span())
    for m in _EN_N.finditer(t):
        if not _hay_palabra_clave_antes(t, m.start(), 35):
            continue
        n = float(NUMEROS.get(m.group(1), m.group(1)))
        unidad = m.group(2)
        if unidad.startswith("minuto"):
            res.caduca_en = ahora + timedelta(minutes=n)
        elif unidad.startswith("hora"):
            res.caduca_en = ahora + timedelta(hours=n)
        elif unidad.startswith("dia"):
            res.caduca_en = reloj.fin_del_dia(ahora + timedelta(days=n))
        else:
            res.caduca_en = reloj.fin_del_dia(ahora + timedelta(weeks=n))
        res.spans.append(m.span())
    for m in _RELATIVA.finditer(t):
        if not _hay_palabra_clave_antes(t, m.start(), 30) or _traslapa(res.spans, *m.span()):
            continue
        dias = {"hoy": 0, "manana": 1, "pasado manana": 2}[m.group(1)]
        res.caduca_en = reloj.fin_del_dia(ahora + timedelta(days=dias))
        res.spans.append(m.span())
    for m in _DIA_SEM.finditer(t):
        if not _hay_palabra_clave_antes(t, m.start(), 30) or _traslapa(res.spans, *m.span()):
            continue
        delta = (DIAS_SEMANA[m.group(1)] - ahora.weekday()) % 7 or 7
        res.caduca_en = reloj.fin_del_dia(ahora + timedelta(days=delta))
        res.spans.append(m.span())

    # -- 2) Rangos de horas: "entre las 6 y las 8 pm", "de 6 a 8 pm" -----------------------------
    for m in _RANGO.finditer(t):
        if _traslapa(res.spans, *m.span()):
            continue
        h1, m1, s1, h2, m2, s2 = m.groups()
        marcado = bool(re.search(r"\blas?\b|:", m.group(0))) or bool(s1 or s2)
        if not marcado or _SIGUE_UNIDAD.match(t[m.end():]):
            continue
        suf1 = s1 or s2  # "6 y 8 pm": el sufijo aplica a las dos horas
        suf2 = s2 or s1
        desde = _hora(h1, m1, suf1, ahora)
        hasta = _hora(h2, m2, suf2, ahora)
        if not desde or not hasta:
            continue
        dia = _dia_base(t, m.start(), ahora)
        res.desde = datetime.combine(dia, desde)
        res.hasta = datetime.combine(dia, hasta)
        res.spans.append(m.span())

    # -- 3) Horas sueltas: "después de las 8 pm", "a las 7", "20:30" ------------------------------
    candidatos: list[tuple[int, int, str, tuple]] = []
    for m in _PUNTUAL.finditer(t):
        candidatos.append((m.start(), m.end(), m.group(1), m.group(2, 3, 4)))
    for m in _HHMM.finditer(t):
        candidatos.append((m.start(), m.end(), "a", m.group(1, 2, 3)))
    for m in _AMPM.finditer(t):
        candidatos.append((m.start(), m.end(), "a", (m.group(1), None, m.group(2))))
    for ini, fin, prep, (h, mi, suf) in sorted(candidatos):
        if _traslapa(res.spans, ini, fin) or _SIGUE_UNIDAD.match(t[fin:]):
            continue
        hora = _hora(h, mi, suf, ahora)
        if hora is None:
            continue
        res.spans.append((ini, fin))
        if _hay_palabra_clave_antes(t, ini, 25):  # "caduca a las 11 pm"
            base = res.caduca_en.date() if res.caduca_en else ahora.date()
            res.caduca_en = datetime.combine(base, hora)
            continue
        momento = datetime.combine(_dia_base(t, ini, ahora), hora)
        if prep in ("despues de", "a partir de", "desde"):
            res.desde = momento
        elif prep in ("antes de", "hasta"):
            res.hasta = momento
        else:  # "a las 7", "para las 7", "20:30": llegan alrededor de esa hora
            res.desde = momento
            res.hasta = momento + timedelta(hours=1)

    # -- 4) "pan del día" / "de hoy": caduca hoy si nadie dijo otra cosa -------------------------
    if res.caduca_en is None and _DEL_DIA.search(t):
        res.caduca_en = reloj.fin_del_dia(ahora)

    return res
