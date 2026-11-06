"""Catálogo de alimentos y de unidades de medida.

El catálogo hace tres cosas:

1. Reconocer alimentos en texto libre (sinónimos, plurales, sin acentos).
2. Dar a cada alimento su **categoría de necesidad** (para emparejar con los receptores), su
   **forma de almacenamiento**, su **nivel de riesgo** y su vida útil por defecto.
3. Convertir cantidades dichas de forma coloquial ("3 cajas", "2 docenas") a kilogramos.

Los valores son estimaciones del equipo, pensadas para una demostración; ver
``docs/ALCANCE_MVP.md``. Nada de esto es una certificación sanitaria.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Categorías de necesidad (las que declaran los receptores en su perfil).
CATEGORIAS: dict[str, str] = {
    "pan": "Pan y tortilla",
    "fruta": "Fruta",
    "verdura": "Verdura",
    "abarrotes": "Abarrotes y bebidas",
    "lacteos": "Lácteos",
    "proteina": "Proteína (carne, huevo, pescado)",
    "preparado": "Comida preparada",
    "otro": "Otros",
}

AMBIENTE = "ambiente"
REFRIGERADO = "refrigerado"
PREPARADO = "preparado"


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos ni signos raros, con espacios simples. Conserva dígitos y , . : / -"""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9,.:/\- ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass(frozen=True)
class Alimento:
    clave: str
    nombre: str
    categoria: str
    almacenamiento: str  # ambiente | refrigerado | preparado
    riesgo: str  # bajo | medio | alto
    vida_util_horas: float  # cuando el donante no da fecha de caducidad
    kg_por_pieza: float
    sinonimos: tuple[str, ...]


def _a(clave, nombre, categoria, almacenamiento, riesgo, horas, kg_pieza, *sinonimos) -> Alimento:
    return Alimento(clave, nombre, categoria, almacenamiento, riesgo, horas, kg_pieza, sinonimos)


_ALIMENTOS: list[Alimento] = [
    _a("pan", "pan", "pan", AMBIENTE, "bajo", 24, 0.07,
       "pan dulce", "pan del dia", "pan de caja", "pan blanco", "pan integral", "pan", "bolillo",
       "telera", "concha", "cuernito", "dona", "polvoron", "baguette", "birote", "panque"),
    _a("tortilla", "tortilla", "pan", AMBIENTE, "bajo", 24, 0.03, "tortilla", "tostada"),
    _a("fruta", "fruta", "fruta", AMBIENTE, "bajo", 48, 0.2,
       "fruta", "manzana", "platano", "banana", "naranja", "mandarina", "mango", "papaya", "sandia",
       "melon", "uva", "limon", "fresa", "pera", "durazno", "pina", "guayaba", "aguacate", "coco",
       "kiwi", "toronja", "ciruela", "cereza", "jicama"),
    _a("verdura", "verdura", "verdura", AMBIENTE, "bajo", 72, 0.2,
       "verdura", "hortaliza", "jitomate", "tomate verde", "tomate", "cebolla", "papa", "zanahoria",
       "lechuga", "calabacita", "calabaza", "chayote", "nopal", "chile", "espinaca", "brocoli",
       "coliflor", "col", "cilantro", "perejil", "pepino", "elote", "ejote", "apio", "betabel",
       "rabano", "acelga", "ajo"),
    _a("abarrotes", "abarrotes", "abarrotes", AMBIENTE, "bajo", 90 * 24, 0.5,
       "abarrotes", "papas fritas", "arroz", "frijol", "lenteja", "garbanzo", "pasta", "espagueti",
       "fideo", "aceite", "azucar", "harina", "avena", "cereal", "galleta", "enlatado", "lata",
       "atun", "sardina", "salsa", "cafe", "chocolate", "mermelada", "miel", "cacahuate", "botana"),
    _a("bebidas", "bebidas", "abarrotes", AMBIENTE, "bajo", 90 * 24, 1.0,
       "bebida", "jugo", "agua embotellada", "agua", "refresco"),
    _a("lacteos", "lácteos", "lacteos", REFRIGERADO, "alto", 72, 0.25,
       "lacteo", "leche", "yogurt", "yogur", "queso", "crema", "mantequilla", "requeson", "jocoque"),
    _a("huevo", "huevo", "proteina", REFRIGERADO, "medio", 168, 0.06, "huevo", "blanquillo"),
    _a("pollo", "pollo", "proteina", REFRIGERADO, "alto", 24, 1.5, "pollo", "pechuga", "muslo"),
    _a("cerdo", "cerdo", "proteina", REFRIGERADO, "alto", 24, 1.0,
       "carne de cerdo", "cerdo", "puerco", "chuleta"),
    _a("res", "res", "proteina", REFRIGERADO, "alto", 24, 1.0,
       "carne de res", "res", "bistec", "arrachera", "carne molida"),
    _a("carne", "carne", "proteina", REFRIGERADO, "alto", 24, 1.0, "carne"),
    _a("pescado", "pescado", "proteina", REFRIGERADO, "alto", 24, 0.5,
       "pescado", "mojarra", "tilapia", "camaron", "marisco"),
    _a("embutidos", "embutidos", "proteina", REFRIGERADO, "alto", 72, 0.3,
       "embutido", "salchicha", "jamon", "chorizo", "tocino", "salami", "mortadela"),
    _a("preparado", "comida preparada", "preparado", PREPARADO, "alto", 4, 0.4,
       "comida preparada", "arroz con pollo", "platillo", "guisado", "tamal", "pozole", "sopa",
       "ensalada", "pizza", "sandwich", "hamburguesa", "taco", "caldo", "menudo", "birria",
       "enchilada", "torta", "lonche", "porcion", "comida"),
    _a("no_aceptado", "producto no aceptado", "otro", AMBIENTE, "alto", 0, 0.0,
       "cerveza", "vino", "tequila", "mezcal", "licor", "whisky", "alcohol", "medicina",
       "medicamento", "pastilla", "cigarro", "tabaco", "vape"),
]

CATALOGO: dict[str, Alimento] = {a.clave: a for a in _ALIMENTOS}

# Alimento que no se reconoce en el catálogo: pasa a revisión humana.
DESCONOCIDO = Alimento("desconocido", "alimento no reconocido", "otro", AMBIENTE, "medio", 24, 0.5, ())


# Índice sinónimo -> alimento, y un único regex con los sinónimos largos primero.
_INDICE: dict[str, Alimento] = {}
for _al in _ALIMENTOS:
    for _s in _al.sinonimos:
        _INDICE.setdefault(_s, _al)

_PATRON = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(re.escape(s) for s in sorted(_INDICE, key=len, reverse=True))
    + r")(?:es|s)?(?![a-z0-9])"
)


@dataclass(frozen=True)
class Coincidencia:
    alimento: Alimento
    texto: str  # tal como lo escribió el usuario (normalizado)
    inicio: int
    fin: int


def buscar_alimentos(texto_normalizado: str) -> list[Coincidencia]:
    """Alimentos del catálogo mencionados en el texto (ya normalizado), en orden de aparición."""
    return [
        Coincidencia(_INDICE[m.group(1)], m.group(0), m.start(), m.end())
        for m in _PATRON.finditer(texto_normalizado)
    ]


# ------------------------------------------------------------------------------------ unidades
_SINONIMOS_UNIDAD: dict[str, tuple[str, ...]] = {
    "kg": ("kg", "kgs", "kilo", "kilos", "kilogramo", "kilogramos", "k"),
    "g": ("g", "gr", "grs", "gramo", "gramos"),
    "ton": ("tonelada", "toneladas", "ton"),
    "l": ("l", "lt", "lts", "litro", "litros"),
    "pieza": ("pieza", "piezas", "pza", "pzas", "pz", "unidad", "unidades"),
    "docena": ("docena", "docenas"),
    "caja": ("caja", "cajas"),
    "bolsa": ("bolsa", "bolsas"),
    "charola": ("charola", "charolas", "bandeja", "bandejas"),
    "lata": ("lata", "latas"),
    "costal": ("costal", "costales", "saco", "sacos"),
    "paquete": ("paquete", "paquetes"),
    "botella": ("botella", "botellas"),
    "porcion": ("porcion", "porciones", "racion", "raciones"),
}
UNIDAD_CANONICA: dict[str, str] = {s: u for u, ss in _SINONIMOS_UNIDAD.items() for s in ss}

# kg que se asumen por unidad genérica cuando no se conoce el peso real.
KG_POR_UNIDAD_GENERICA: dict[str, float] = {
    "caja": 10.0, "bolsa": 1.0, "charola": 3.0, "lata": 0.4, "costal": 25.0,
    "paquete": 0.5, "botella": 1.0, "porcion": 0.4,
}


def unidad_canonica(texto: str) -> str | None:
    """'kilos' -> 'kg'. None si no es una unidad conocida."""
    return UNIDAD_CANONICA.get(normalizar(texto))


def a_kg(cantidad: float, unidad: str, alimento: Alimento) -> tuple[float, bool]:
    """Convierte ``cantidad`` de ``unidad`` (canónica) a kg. Devuelve ``(kg, es_estimado)``.

    ``es_estimado`` es True cuando se usó un peso supuesto (piezas, cajas, etc.); el Captador lo
    muestra al donante para que lo corrija si no es correcto.
    """
    if unidad == "kg":
        return cantidad, False
    if unidad == "g":
        return cantidad / 1000.0, False
    if unidad == "ton":
        return cantidad * 1000.0, False
    if unidad == "l":
        return cantidad, False  # densidad ~1
    if unidad == "pieza":
        return cantidad * alimento.kg_por_pieza, True
    if unidad == "docena":
        return cantidad * 12 * alimento.kg_por_pieza, True
    return cantidad * KG_POR_UNIDAD_GENERICA.get(unidad, 1.0), True
