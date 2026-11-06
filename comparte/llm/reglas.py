"""Motor de lenguaje por reglas (modo por defecto, sin costo y sin internet).

Interpreta mensajes de donación en español coloquial con expresiones regulares y el catálogo de
alimentos. Es **determinista** (misma entrada, misma salida), lo que lo hace ideal para pruebas y
para grabar la demostración, pero entiende un subconjunto del idioma: frases como
"Tengo 25 kg de pan dulce del día y 3 cajas de fruta madura, pueden pasar después de las 8 pm".
Para lenguaje más libre y fotos existe ``ExtractorClaude``.

Cómo funciona (en este orden):
1. Se alinea el texto: minúsculas y sin acentos pero **con la misma longitud**, para poder volver al
   texto original con las mismas posiciones y mostrar los nombres como los escribió el usuario.
2. Se extraen fechas y horas (``fechas_es``) y se quitan del texto.
3. Se extraen condiciones del alimento (refrigerado, mal estado, etc.).
4. Se detectan cantidades ("25 kg", "3 cajas", "media docena") y alimentos del catálogo y se
   emparejan por cercanía ("25 kg de pan" -> pan = 25 kg).
5. Se decide la intención (donar, confirmar, negar, cancelar).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from ..conocimiento.catalogo import UNIDAD_CANONICA, Coincidencia, buscar_alimentos
from .base import Extraccion, Imagen, ItemExtraido
from .fechas_es import NUMEROS, analizar_tiempos

_PALABRAS_NUM = "|".join(NUMEROS)
_UNIDADES = "|".join(sorted(map(re.escape, UNIDAD_CANONICA), key=len, reverse=True))
_NUMERO = rf"\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:[.,]\d+)?|{_PALABRAS_NUM}"

# Un número justo antes de un alimento, sin unidad: "40 bolillos" => 40 piezas. Con "de" ("3 cajas de
# jitomate y 2 de cebolla") se hereda la unidad de la cantidad anterior.
_NUMERO_SUELTO = re.compile(rf"(?<![a-z0-9.,])({_NUMERO})\s+(de\s+)?$")

_KILO_Y_MEDIO = re.compile(r"(?<![a-z0-9])(?:(\d+|un|uno|una)\s+)?kilos?\s+y\s+medio(?![a-z0-9])")
_CANTIDAD = re.compile(rf"(?<![a-z0-9.,])({_NUMERO})\s*({_UNIDADES})(?![a-z0-9])")

# Palabras que no pueden ser el nombre de un alimento desconocido ("20 kg que tengo desde ayer").
_NO_ES_ALIMENTO = {
    "que", "para", "y", "con", "en", "a", "del", "al", "por", "pero", "ya", "hoy", "manana", "desde",
    "hasta", "caduca", "vence", "entre", "pueden", "puede", "tengo", "tenemos", "es", "son", "de",
    "la", "el", "los", "las", "un", "una", "como", "mas", "sin", "se", "si", "no", "mi", "nuestro",
}

_CONDICIONES = [
    ("mal_estado", r"echad[oa]s? a perder|podrid|moho|descompuest|mal estado|agri[oa]s?\b|rancio"),
    ("cadena_rota", r"descongelad|se descongel|no (?:estuvo|estuvieron|esta|estan|se mantuvo|se mantuvieron)"
                    r" (?:en )?(?:refrigerad|refri|frio|congelad)|sin refriger|sin refri\b|"
                    r"fuera del refri|se corto la cadena|cadena (?:de frio )?rota|se rompio la cadena"),
    ("refrigerado", r"refrigerad|refrigeracion|refri\b|cadena de frio|en frio"),
    ("congelado", r"(?<!des)congelad"),
    ("empacado", r"empacad|empaquetad|sellad|cerrad|sin abrir|en su empaque|etiquetad"),
    ("abierto", r"(?:empaque|paquete|caja|bolsa|lata|envase|botella)s? abiert[oa]s?|"
                r"ya (?:esta|estan) abiert[oa]s?|sin empaque|sin envolver|ya se abrio"),
    ("caliente", r"caliente|recien hech|recien horneado"),
]

_CONFIRMA = re.compile(
    r"^(?:si|sip|sii|claro|correcto|confirmo|confirmado|dale|ok|okay|va|listo|exacto|perfecto|"
    r"adelante|procede|afirmativo|asi es|de acuerdo|esta bien|todo bien|todo correcto|muy bien|"
    r"por supuesto|sale)\b"
)
_NIEGA = re.compile(r"^(?:no|nel|nop|nope|negativo|incorrecto|mal|corrige|corregir|cambiar|cambia)\b")
_CANCELA = re.compile(
    r"\b(?:cancela\w*|olvidalo|olvida|dejalo|mejor no|ya no (?:quiero|voy|vamos)|"
    r"no quiero donar|no voy a donar)\b"
)


def _alinear(texto: str) -> str:
    """Minúsculas y sin acentos con la **misma longitud** que ``texto`` (1 carácter -> 1 carácter)."""
    salida = []
    for c in texto:
        base = next((x for x in unicodedata.normalize("NFD", c) if unicodedata.category(x) != "Mn"), " ")
        base = base.lower()
        salida.append(base if re.fullmatch(r"[a-z0-9,.:/\- ]", base) else " ")
    return "".join(salida)


def _blanquear(t: str, spans: list[tuple[int, int]]) -> str:
    """Reemplaza por espacios los tramos ya interpretados (conserva posiciones)."""
    chars = list(t)
    for ini, fin in spans:
        for i in range(ini, min(fin, len(chars))):
            chars[i] = " "
    return "".join(chars)


def _numero(texto: str) -> float:
    if texto in NUMEROS:
        return float(NUMEROS[texto])
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", texto):  # 1,500 o 1,500.5 (miles con coma)
        return float(texto.replace(",", ""))
    return float(texto.replace(",", "."))


def _condiciones(t: str) -> list[str]:
    encontradas = [nombre for nombre, patron in _CONDICIONES if re.search(patron, t)]
    if "cadena_rota" in encontradas:  # "se descongeló" anula "refrigerado"/"congelado"
        encontradas = [c for c in encontradas if c not in ("refrigerado", "congelado")]
    return encontradas


def _fusionar_adyacentes(coincidencias: list, t: str) -> list:
    """Une alimentos del mismo tipo separados solo por "de/del/en": "pechuga de pollo", "atún en lata"."""
    fusionadas: list = []
    for c in coincidencias:
        if fusionadas:
            a = fusionadas[-1]
            if a.alimento.clave == c.alimento.clave and t[a.fin:c.inicio].strip() in ("", "de", "del", "en"):
                fusionadas[-1] = Coincidencia(a.alimento, t[a.inicio:c.fin], a.inicio, c.fin)
                continue
        fusionadas.append(c)
    return fusionadas


def _items(orig: str, t: str) -> tuple[list[ItemExtraido], list[tuple[int, int]]]:
    """Cantidades y alimentos de ``t`` emparejados por cercanía. Devuelve también los tramos usados."""
    eventos: list[tuple[int, str, object]] = []  # (posición, tipo, datos)
    ocupados: list[tuple[int, int]] = []

    for m in _KILO_Y_MEDIO.finditer(t):
        base = float(NUMEROS.get(m.group(1), m.group(1))) if m.group(1) else 1.0  # "kilo y medio" = 1.5
        eventos.append((m.start(), "Q", (m.start(), m.end(), base + 0.5, "kg")))
        ocupados.append(m.span())
    for m in _CANTIDAD.finditer(t):
        if any(m.start() < f and i < m.end() for i, f in ocupados):
            continue
        eventos.append((m.start(), "Q", (m.start(), m.end(), _numero(m.group(1)), UNIDAD_CANONICA[m.group(2)])))
        ocupados.append(m.span())

    # Los alimentos se buscan con las cantidades en blanco ("latas" es unidad, no alimento).
    t_sin_cantidades = _blanquear(t, ocupados)
    for c in _fusionar_adyacentes(buscar_alimentos(t_sin_cantidades), t_sin_cantidades):
        eventos.append((c.inicio, "F", c))
        # "40 bolillos": un número pegado al alimento y sin unidad se cuenta como piezas;
        # "2 de cebolla" hereda la unidad de la cantidad anterior ("3 cajas de jitomate y 2 de cebolla").
        m = _NUMERO_SUELTO.search(t_sin_cantidades[:c.inicio])
        if m:
            unidad = "pieza"
            if m.group(2):
                previas = [e for e in eventos if e[1] == "Q" and e[0] < m.start(1)]
                if previas:
                    unidad = max(previas, key=lambda e: e[0])[2][3]
            eventos.append((m.start(1), "Q", (m.start(1), m.end(1), _numero(m.group(1)), unidad)))
            ocupados.append((m.start(1), m.end(1)))
            t_sin_cantidades = _blanquear(t_sin_cantidades, [(m.start(1), m.end(1))])
    eventos.sort(key=lambda e: e[0])

    items: list[ItemExtraido] = []
    claves: list[str] = []  # tipo de alimento de cada item (paralelo a ``items``)
    fin_ultimo = -2  # índice del último evento que formó parte del último item
    usados: set[int] = set()
    spans: list[tuple[int, int]] = []
    for i, (_, tipo, datos) in enumerate(eventos):
        if i in usados:
            continue
        if tipo == "F":
            c = datos
            nombre = orig[c.inicio:c.fin].lower()
            spans.append((c.inicio, c.fin))
            # "15 kg de verdura (zanahoria, calabaza)": un alimento sin cantidad del mismo tipo que el
            # anterior (con cantidad) y pegado a él es un detalle, no otro producto.
            if (items and items[-1].cantidad is not None and claves[-1] == c.alimento.clave
                    and c.alimento.clave != "desconocido" and i == fin_ultimo + 1):
                items[-1].nombre = f"{items[-1].nombre}, {nombre}"
            else:
                items.append(ItemExtraido(nombre=nombre))
                claves.append(c.alimento.clave)
            fin_ultimo = i
            continue

        ini, fin, cantidad, unidad = datos
        spans.append((ini, fin))
        siguiente = eventos[i + 1] if i + 1 < len(eventos) else None
        if siguiente and siguiente[1] == "F":
            c = siguiente[2]
            hueco = t[fin:c.inicio]
            if len(hueco.strip()) <= 30 and not re.search(r"[\d,.;]", hueco):
                items.append(ItemExtraido(orig[c.inicio:c.fin].lower(), cantidad, unidad))
                claves.append(c.alimento.clave)
                usados.add(i + 1)
                fin_ultimo = i + 1
                spans.append((c.inicio, c.fin))
                continue
        anterior = items[-1] if items else None
        if anterior and anterior.cantidad is None and eventos[i - 1][1] == "F":
            anterior.cantidad, anterior.unidad = cantidad, unidad  # "pan dulce, 25 kg"
            fin_ultimo = i
            continue
        m = re.match(r"\s*de\s+([a-z]+(?: [a-z]+){0,2})", t[fin:])
        if m:  # alimento fuera del catálogo: "2 charolas de gelatina"
            palabras = []
            for palabra in m.group(1).split():
                if palabra in _NO_ES_ALIMENTO or palabra.isdigit():
                    break
                palabras.append(palabra)
            if palabras:
                nombre = " ".join(palabras)
                inicio_nombre = fin + m.start(1)
                items.append(ItemExtraido(orig[inicio_nombre:inicio_nombre + len(nombre)].lower(), cantidad, unidad))
                claves.append("")
                spans.append((inicio_nombre, inicio_nombre + len(nombre)))
                continue
        items.append(ItemExtraido(None, cantidad, unidad))  # cantidad suelta ("20 kg")
        claves.append("")
    return items, spans


class ExtractorReglas:
    """Implementa ``Extractor`` con reglas (ver el docstring del módulo)."""

    nombre = "reglas"

    def extraer(
        self, texto: str, borrador: dict, ahora: datetime, imagen: Imagen | None = None
    ) -> Extraccion:
        orig = re.sub(r"\s+", " ", texto.strip())
        t = _alinear(orig)

        tiempos = analizar_tiempos(t, ahora)
        t_limpio = _blanquear(t, tiempos.spans)
        items, _ = _items(orig, t_limpio)
        condiciones = _condiciones(t)

        hay_datos = bool(items or tiempos.caduca_en or tiempos.desde or tiempos.hasta)
        sin_puntuacion = t.strip(" ,.;:!-")
        if _CANCELA.search(t):
            intencion = "cancelar"
        elif hay_datos:
            intencion = "donar"
        elif _CONFIRMA.match(sin_puntuacion):
            intencion = "confirmar"
        elif _NIEGA.match(sin_puntuacion):
            intencion = "negar"
        elif condiciones:
            intencion = "donar"
        else:
            intencion = "otro"

        return Extraccion(
            intencion=intencion,
            items=items,
            caduca_en=tiempos.caduca_en,
            recoleccion_desde=tiempos.desde,
            recoleccion_hasta=tiempos.hasta,
            condiciones=condiciones,
        )
