"""Agente Captador (CP-01 Registro conversacional y CP-02 Evaluación de inocuidad).

Conversa con el donante, entiende su mensaje (texto y opcionalmente foto), estructura la donación y
aplica las reglas de inocuidad. **Reparto de responsabilidades**:

* El *motor de lenguaje* (``comparte/llm``) solo interpreta el mensaje.
* El *Captador* (este módulo) decide qué hacer: qué preguntar, qué suponer, cuándo pedir confirmación,
  cuándo bloquear. Por eso el comportamiento es el mismo con el motor de reglas o con Claude.

Principio de diseño: **preguntar lo mínimo**. El único dato obligatorio es "qué alimento y cuánto";
la caducidad y la ventana de recolección se estiman cuando no se dan y se muestran en el resumen para
que el donante las corrija. Así donar toma dos mensajes (describir y "sí"), cumpliendo el criterio de
éxito del documento de visión: *donar en menos de un minuto*.

Etapas del borrador: ``recopilando`` -> (preguntas pendientes: cantidad, cadena de frío) ->
``confirmando`` -> se registra la ``Donacion`` y el borrador se reinicia.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from .. import reloj
from ..config import obtener_ajustes
from ..conocimiento import inocuidad
from ..conocimiento.catalogo import CATALOGO, DESCONOCIDO, Alimento, a_kg, buscar_alimentos, normalizar
from ..llm.base import Extraccion, Extractor, Imagen
from ..modelos import Agente, Conversacion, Donacion, Donante, EstadoDonacion
from .base import a_iso, de_iso, decir, fmt_kg, fmt_momento, registrar_evento

_UNIDAD_TXT = {
    "kg": ("kg", "kg"), "g": ("g", "g"), "ton": ("tonelada", "toneladas"), "l": ("L", "L"),
    "pieza": ("pieza", "piezas"), "docena": ("docena", "docenas"), "caja": ("caja", "cajas"),
    "bolsa": ("bolsa", "bolsas"), "charola": ("charola", "charolas"), "lata": ("lata", "latas"),
    "costal": ("costal", "costales"), "paquete": ("paquete", "paquetes"),
    "botella": ("botella", "botellas"), "porcion": ("porción", "porciones"),
}
_EXT_IMAGEN = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


@dataclass
class ResultadoCaptador:
    donacion: Donacion | None = None  # la donación que se acaba de registrar (si la hubo)
    bloqueada: bool = False  # inocuidad impidió registrar


def resolver_alimento(nombre: str) -> Alimento:
    """Alimento del catálogo que corresponde a ``nombre``; ``DESCONOCIDO`` si no se reconoce."""
    encontrados = buscar_alimentos(normalizar(nombre))
    return encontrados[0].alimento if encontrados else DESCONOCIDO


def _item(nombre: str, alimento: Alimento, cantidad: float | None, unidad: str | None) -> dict:
    item = {
        "nombre": nombre, "clave": alimento.clave, "categoria": alimento.categoria,
        "almacenamiento": alimento.almacenamiento, "riesgo": alimento.riesgo,
        "cantidad": None, "unidad": None, "kg": None, "estimado": False,
    }
    if cantidad is not None:
        _poner_cantidad(item, cantidad, unidad)
    return item


def _poner_cantidad(item: dict, cantidad: float, unidad: str | None) -> None:
    alimento = CATALOGO.get(item["clave"], DESCONOCIDO)
    kg, estimado = a_kg(cantidad, unidad or "kg", alimento)
    item.update(cantidad=cantidad, unidad=unidad or "kg", kg=round(kg, 2),
                estimado=estimado or unidad is None)


def _texto_cantidad(item: dict) -> str:
    singular, plural = _UNIDAD_TXT.get(item["unidad"], (item["unidad"], item["unidad"]))
    cantidad = item["cantidad"]
    return f"{cantidad:g} {singular if cantidad == 1 else plural}"


class AgenteCaptador:
    nombre = Agente.CAPTADOR

    def __init__(self, db: Session, extractor: Extractor, carpeta_datos: Path | None = None):
        self.db = db
        self.extractor = extractor
        self.carpeta_datos = carpeta_datos or obtener_ajustes().carpeta_datos

    # ------------------------------------------------------------------ API pública
    def iniciar_conversacion(self, donante: Donante, canal: str = "web") -> Conversacion:
        conv = Conversacion(donante_id=donante.id, canal=canal, borrador={}, creada_en=reloj.ahora())
        self.db.add(conv)
        self.db.flush()
        nombre = (donante.contacto or "").split(" ")[0] or "hola"
        decir(
            self.db, conv, self.nombre,
            f"¡Hola, {nombre}! Soy el Agente Captador de ComParte. Cuéntame qué excedente tienes: qué "
            "alimento, cuánto y, si puedes, hasta cuándo dura y a qué hora pueden pasar por él. "
            "También puedes mandar una foto.",
        )
        return conv

    def procesar_mensaje(
        self, conv: Conversacion, texto: str, imagen: Imagen | None = None
    ) -> ResultadoCaptador:
        ahora = reloj.ahora()
        b = self._borrador(conv, ahora)
        ruta_foto = self._guardar_foto(conv, imagen, ahora) if imagen else None
        decir(self.db, conv, "donante", texto, imagen=ruta_foto)

        ext = self.extractor.extraer(texto, b, ahora, imagen)
        if ruta_foto:
            b["foto"] = ruta_foto

        if ext.intencion == "cancelar":
            conv.borrador = {}
            decir(self.db, conv, self.nombre,
                  "Listo, cancelé este registro. Cuando tengas otro excedente, cuéntame.")
            return ResultadoCaptador()

        hay_datos = bool(ext.items or ext.caduca_en or ext.recoleccion_desde or ext.recoleccion_hasta)
        if b["etapa"] == "confirmando" and not hay_datos:
            if ext.intencion == "confirmar":
                b["condiciones"] = sorted(set(b["condiciones"]) | set(ext.condiciones))
                return self._registrar(conv, b, ahora)
            if ext.intencion == "negar":
                b["etapa"] = "recopilando"
                conv.borrador = b
                decir(self.db, conv, self.nombre,
                      "Entendido. ¿Qué quieres corregir? Dime el dato correcto, por ejemplo "
                      "«son 30 kg», «caduca mañana» o «pueden pasar a las 7 pm».")
                return ResultadoCaptador()

        if b["pendiente"] == "cadena_frio":
            if ext.intencion == "confirmar":
                b["condiciones"] = sorted(set(b["condiciones"]) | {inocuidad.COND_FRIO_OK})
                b["pendiente"] = None
            elif ext.intencion == "negar":
                b["condiciones"] = sorted(set(b["condiciones"]) | {inocuidad.COND_CADENA_ROTA})
                b["pendiente"] = None

        avisos = self._fusionar(b, ext)
        b["etapa"] = "recopilando"
        return self._avanzar(conv, b, ahora, avisos)

    # ------------------------------------------------------------------ borrador
    def _borrador(self, conv: Conversacion, ahora: datetime) -> dict:
        b = copy.deepcopy(conv.borrador or {})
        b.setdefault("items", [])
        b.setdefault("condiciones", [])
        b.setdefault("etapa", "recopilando")
        b.setdefault("pendiente", None)
        b.setdefault("caduca_en", None)
        b.setdefault("caducidad_estimada", False)
        b.setdefault("recoleccion_desde", None)
        b.setdefault("recoleccion_hasta", None)
        b.setdefault("foto", None)
        b.setdefault("iniciada_en", a_iso(ahora))
        return b

    def _guardar_foto(self, conv: Conversacion, imagen: Imagen, ahora: datetime) -> str:
        datos, mime = imagen
        carpeta = self.carpeta_datos / "uploads"
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = f"conv{conv.id}_{ahora:%Y%m%d%H%M%S}{_EXT_IMAGEN.get(mime, '.bin')}"
        (carpeta / nombre).write_bytes(datos)
        return f"uploads/{nombre}"

    # ------------------------------------------------------------------ interpretación
    def _fusionar(self, b: dict, ext: Extraccion) -> list[str]:
        """Incorpora lo que entendió el motor de lenguaje al borrador. Devuelve avisos para el donante."""
        avisos: list[str] = []
        for it in ext.items:
            if it.nombre is None:  # cantidad suelta: "20 kg", "son 30 kg"
                if it.cantidad is None:
                    continue
                destino = next((i for i in b["items"] if i["cantidad"] is None), None)
                if destino is None and len(b["items"]) == 1:
                    destino = b["items"][0]  # corrección de la única cantidad
                if destino is not None:
                    _poner_cantidad(destino, it.cantidad, it.unidad)
                elif b["items"]:
                    avisos.append("No supe a qué alimento corresponde esa cantidad. Dímelo así: «30 kg de pan».")
                else:
                    avisos.append("Primero dime qué alimento es.")
                continue
            alimento = resolver_alimento(it.nombre)
            existente = self._buscar_item(b, alimento, it.nombre)
            if existente is not None:
                if it.cantidad is not None:
                    _poner_cantidad(existente, it.cantidad, it.unidad)
            else:
                b["items"].append(_item(it.nombre, alimento, it.cantidad, it.unidad))

        if ext.caduca_en:
            b["caduca_en"], b["caducidad_estimada"] = a_iso(ext.caduca_en), False
        if ext.recoleccion_desde:
            b["recoleccion_desde"] = a_iso(ext.recoleccion_desde)
            if b["recoleccion_hasta"] and de_iso(b["recoleccion_hasta"]) <= ext.recoleccion_desde:
                b["recoleccion_hasta"] = None
        if ext.recoleccion_hasta:
            b["recoleccion_hasta"] = a_iso(ext.recoleccion_hasta)
        b["condiciones"] = sorted(set(b["condiciones"]) | set(ext.condiciones))
        return avisos

    @staticmethod
    def _buscar_item(b: dict, alimento: Alimento, nombre: str) -> dict | None:
        n = normalizar(nombre)
        for it in b["items"]:
            otro = normalizar(it["nombre"])
            if n == otro:
                return it
            if alimento.clave != "desconocido" and it["clave"] == alimento.clave and (n in otro or otro in n):
                return it
        return None

    # ------------------------------------------------------------------ conversación
    def _avanzar(self, conv: Conversacion, b: dict, ahora: datetime, avisos: list[str]) -> ResultadoCaptador:
        def responder(*textos: str) -> ResultadoCaptador:
            conv.borrador = b
            decir(self.db, conv, self.nombre, "\n".join(t for t in (*avisos, *textos) if t))
            return ResultadoCaptador()

        if not b["items"]:
            if b["foto"] and "claude" not in self.extractor.nombre:
                return responder("Recibí tu foto, pero en este modo no puedo leerla. Dime qué alimento "
                                 "es y cuánto hay; por ejemplo: «25 kg de pan dulce».")
            return responder("Cuéntame qué alimento quieres donar y cuánto. Por ejemplo: "
                             "«25 kg de pan dulce, caduca hoy».")

        faltan = [i for i in b["items"] if i["cantidad"] is None]
        if faltan:
            b["pendiente"] = "cantidad"
            return responder(f"¿Cuánto {faltan[0]['nombre']} tienes? Puedes decirlo en kg, piezas, cajas o charolas.")
        if b["pendiente"] == "cantidad":
            b["pendiente"] = None

        self._valores_por_defecto(b, ahora)
        ev = self._evaluar(b, ahora)
        if ev.bloqueada:
            return self._rechazar(conv, b, ev)

        if ev.confirmar_frio:
            b["pendiente"] = "cadena_frio"
            frios = ", ".join(i["nombre"] for i in b["items"] if i["almacenamiento"] == "refrigerado")
            return responder(f"{frios.capitalize()} necesita cadena de frío. ¿Se mantuvo refrigerado todo el "
                             "tiempo? Responde «sí» o «no».")

        b["etapa"], b["pendiente"] = "confirmando", None
        return responder(self._resumen(b, ev, ahora))

    def _valores_por_defecto(self, b: dict, ahora: datetime) -> None:
        if not b["caduca_en"]:
            vidas = [CATALOGO.get(i["clave"], DESCONOCIDO).vida_util_horas for i in b["items"]]
            horas = min([v for v in vidas if v > 0] or [24])
            b["caduca_en"], b["caducidad_estimada"] = a_iso(ahora + timedelta(hours=horas)), True
        caduca = de_iso(b["caduca_en"])
        desde = de_iso(b["recoleccion_desde"]) or ahora + timedelta(minutes=15)
        hasta = de_iso(b["recoleccion_hasta"]) or min(max(desde, ahora) + timedelta(hours=3), caduca)
        if hasta <= desde:
            hasta = desde + timedelta(hours=1)
        b["recoleccion_desde"], b["recoleccion_hasta"] = a_iso(desde), a_iso(hasta)

    @staticmethod
    def _evaluar(b: dict, ahora: datetime) -> inocuidad.Evaluacion:
        return inocuidad.evaluar(b["items"], b["condiciones"], de_iso(b["caduca_en"]), ahora)

    def _resumen(self, b: dict, ev: inocuidad.Evaluacion, ahora: datetime) -> str:
        lineas = ["Esto es lo que entendí:"]
        lineas += [f"• {_texto_cantidad(i)} de {i['nombre']}" for i in b["items"]]
        total = sum(i["kg"] for i in b["items"])
        estimado = any(i["estimado"] for i in b["items"])
        lineas.append(f"Total: {'aprox. ' if estimado else ''}{fmt_kg(total)}"
                      + (" (peso estimado; corrígelo si no es correcto)" if estimado else ""))
        caduca = fmt_momento(de_iso(b["caduca_en"]), ahora)
        lineas.append(f"Caduca: {caduca}" + (" (estimado)" if b["caducidad_estimada"] else ""))
        desde, hasta = de_iso(b["recoleccion_desde"]), de_iso(b["recoleccion_hasta"])
        fin = f"{hasta:%H:%M}" if hasta.date() == desde.date() else fmt_momento(hasta, ahora)
        lineas.append(f"Recolección: {fmt_momento(desde, ahora)} a {fin}")
        if ev.requiere_revision:
            lineas.append("⚠ Incluye alimentos de riesgo: una persona del equipo lo revisará antes de asignarlo.")
        lineas += [f"⚠ {a}" for a in ev.advertencias]
        lineas.append("¿Lo confirmo? Responde «sí» o dime qué corregir.")
        return "\n".join(lineas)

    def _rechazar(self, conv: Conversacion, b: dict, ev: inocuidad.Evaluacion) -> ResultadoCaptador:
        motivos = "\n".join(f"• {m}" for m in ev.motivos)
        registrar_evento(
            self.db, self.nombre, "donacion_bloqueada",
            "Inocuidad bloqueó el registro: " + "; ".join(ev.motivos),
            conversacion_id=conv.id, detalle={"motivos": ev.motivos, "items": b["items"]},
        )
        conv.borrador = {}
        decir(self.db, conv, self.nombre,
              f"No puedo registrar esta donación:\n{motivos}\nGracias por avisar. Si tienes otro "
              "excedente, cuéntame.")
        return ResultadoCaptador(bloqueada=True)

    def _registrar(self, conv: Conversacion, b: dict, ahora: datetime) -> ResultadoCaptador:
        ev = self._evaluar(b, ahora)
        if ev.bloqueada:
            return self._rechazar(conv, b, ev)

        por_categoria: dict[str, float] = {}
        for i in b["items"]:
            por_categoria[i["categoria"]] = por_categoria.get(i["categoria"], 0.0) + i["kg"]
        iniciada = de_iso(b["iniciada_en"]) or ahora
        donacion = Donacion(
            donante_id=conv.donante_id, conversacion_id=conv.id, estado=EstadoDonacion.REGISTRADA,
            items=b["items"], total_kg=round(sum(i["kg"] for i in b["items"]), 2),
            categoria_principal=max(por_categoria, key=por_categoria.get),
            requiere_frio=ev.requiere_frio, caduca_en=de_iso(b["caduca_en"]),
            caducidad_estimada=b["caducidad_estimada"],
            recoleccion_desde=de_iso(b["recoleccion_desde"]), recoleccion_hasta=de_iso(b["recoleccion_hasta"]),
            condiciones=b["condiciones"], foto=b["foto"], inocuidad=ev.a_dict(),
            segundos_registro=max(0, int((ahora - iniciada).total_seconds())), creada_en=ahora,
        )
        self.db.add(donacion)
        self.db.flush()

        resumen_items = ", ".join(f"{_texto_cantidad(i)} de {i['nombre']}" for i in b["items"])
        registrar_evento(
            self.db, self.nombre, "donacion_registrada",
            f"Registré la donación #{donacion.id}: {resumen_items} ({fmt_kg(donacion.total_kg)}).",
            donacion_id=donacion.id, conversacion_id=conv.id,
            detalle={"motor_lenguaje": self.extractor.nombre, "segundos_registro": donacion.segundos_registro,
                     "pesos_estimados": [i["nombre"] for i in b["items"] if i["estimado"]],
                     "caducidad_estimada": b["caducidad_estimada"]},
        )
        registrar_evento(
            self.db, self.nombre, "inocuidad_evaluada",
            f"Inocuidad: riesgo {ev.nivel}"
            + (" · requiere revisión humana" if ev.requiere_revision else " · sin revisión necesaria")
            + (" · requiere cadena de frío" if ev.requiere_frio else ""),
            donacion_id=donacion.id, detalle=ev.a_dict(),
        )
        conv.donacion_id = donacion.id
        conv.borrador = {}
        decir(self.db, conv, self.nombre,
              f"¡Listo! Registré tu donación #{donacion.id} ({fmt_kg(donacion.total_kg)}). "
              "Ahora la turno al resto del equipo de agentes.")
        return ResultadoCaptador(donacion=donacion)
