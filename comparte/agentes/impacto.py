"""Agente de Impacto (CP-07 Tablero de impacto y CP-08 Reportes para donantes).

Convierte cada rescate completado en métricas y las agrega para el tablero. Las definiciones están en
``docs/ALCANCE_MVP.md`` (sección 4) y los factores en ``conocimiento/factores_impacto.py``:

* **kg rescatados**: kg confirmados por el receptor (o los registrados si no corrigió la cantidad).
* **Raciones**: ``kg / KG_POR_RACION``.
* **Personas beneficiadas (estimado)**: ``raciones / RACIONES_POR_PERSONA_DIA`` = personas alimentadas el
  equivalente a un día completo.
* **CO2e evitado**: ``Σ kg x factor de emisión de cada alimento``.

El registro de impacto se guarda como una "foto" al completar el rescate, así las cifras históricas no
cambian si después se ajustan los factores. Los KPIs de **proceso** (tiempo de registro, tiempo de
primera oferta, aceptación a la primera oferta) se calculan solo con donaciones **reales** de la
sesión: el historial simulado no los tiene y no se inventan.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import reloj
from ..conocimiento.catalogo import CATEGORIAS
from ..conocimiento.factores_impacto import (
    KG_POR_RACION,
    RACIONES_POR_PERSONA_DIA,
    factor_co2e,
)
from ..modelos import (
    Agente,
    Donacion,
    Donante,
    EstadoDonacion,
    EstadoOferta,
    Oferta,
    RegistroImpacto,
)
from .base import fmt_kg, notificar_donante, registrar_evento


def metricas_de_items(items: list[dict], kg_confirmados: float | None = None) -> dict[str, float]:
    """Calcula kg, raciones, personas y CO2e. Si el receptor confirmó una cantidad distinta de la
    registrada, los kg de cada alimento se escalan proporcionalmente."""
    registrado = sum(i["kg"] or 0.0 for i in items)
    escala = (kg_confirmados / registrado) if (kg_confirmados is not None and registrado) else 1.0
    kg = registrado * escala
    co2e = sum((i["kg"] or 0.0) * escala * factor_co2e(i["clave"]) for i in items)
    raciones = kg / KG_POR_RACION
    return {
        "kg": round(kg, 2),
        "raciones": round(raciones, 1),
        "personas": round(raciones / RACIONES_POR_PERSONA_DIA, 1),
        "co2e_kg": round(co2e, 1),
    }


class AgenteImpacto:
    nombre = Agente.IMPACTO

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ registro de un rescate
    def registrar(self, donacion: Donacion) -> RegistroImpacto:
        """Guarda el impacto de una donación que el receptor acaba de confirmar."""
        m = metricas_de_items(donacion.items, donacion.kg_recibidos)
        registro = RegistroImpacto(
            donacion_id=donacion.id, donante_id=donacion.donante_id, receptor_id=donacion.receptor_id,
            municipio_origen=donacion.donante.municipio, municipio_destino=donacion.receptor.municipio,
            categoria=donacion.categoria_principal, kg=m["kg"], raciones=m["raciones"],
            personas=m["personas"], co2e_kg=m["co2e_kg"], simulada=donacion.simulada, creado_en=reloj.ahora(),
        )
        self.db.add(registro)
        self.db.flush()
        registrar_evento(
            self.db, self.nombre, "impacto_registrado",
            f"Impacto del rescate: {fmt_kg(m['kg'])}, {m['raciones']:.0f} raciones, "
            f"≈{m['personas']:.0f} personas, {m['co2e_kg']:.0f} kg de CO2e evitados.",
            donacion_id=donacion.id, detalle=m,
        )
        notificar_donante(self.db, donacion, self.nombre, self.constancia(donacion, m))
        return registro

    @staticmethod
    def constancia(donacion: Donacion, m: dict[str, float]) -> str:
        return (
            f"¡Rescate completado! Tu donación #{donacion.id} llegó a {donacion.receptor.nombre}.\n"
            f"• {fmt_kg(m['kg'])} rescatados\n• {m['raciones']:.0f} raciones\n"
            f"• ≈{m['personas']:.0f} personas alimentadas un día completo\n"
            f"• {m['co2e_kg']:.0f} kg de CO2e evitados\nGracias por compartir."
        )

    # ------------------------------------------------------------------ tablero
    def resumen(
        self, *, donante_id: int | None = None, receptor_id: int | None = None,
        dias: int = 30, incluir_simuladas: bool = True,
    ) -> dict:
        ahora = reloj.ahora()
        consulta = select(RegistroImpacto)
        if donante_id is not None:
            consulta = consulta.where(RegistroImpacto.donante_id == donante_id)
        if receptor_id is not None:
            consulta = consulta.where(RegistroImpacto.receptor_id == receptor_id)
        if not incluir_simuladas:
            consulta = consulta.where(RegistroImpacto.simulada.is_(False))
        registros = list(self.db.scalars(consulta))

        def suma(campo: str) -> float:
            return round(sum(getattr(r, campo) for r in registros), 1)

        diario: dict = defaultdict(lambda: {"kg": 0.0, "rescates": 0})
        for r in registros:
            dia = diario[r.creado_en.date()]
            dia["kg"] += r.kg
            dia["rescates"] += 1
        serie = []
        for i in range(dias - 1, -1, -1):
            fecha = (ahora - timedelta(days=i)).date()
            serie.append({"fecha": fecha.isoformat(), "kg": round(diario[fecha]["kg"], 1),
                          "rescates": diario[fecha]["rescates"]})

        def agrupar(clave, nombre_de=None) -> list[dict]:
            acum: dict = defaultdict(lambda: {"kg": 0.0, "rescates": 0})
            for r in registros:
                k = clave(r)
                acum[k]["kg"] += r.kg
                acum[k]["rescates"] += 1
            filas = [{"clave": k, "etiqueta": nombre_de(k) if nombre_de else k,
                      "kg": round(v["kg"], 1), "rescates": v["rescates"]} for k, v in acum.items()]
            return sorted(filas, key=lambda f: -f["kg"])

        nombres_donantes = {d.id: d.nombre for d in self.db.scalars(select(Donante))}
        simuladas = [r for r in registros if r.simulada]
        return {
            "totales": {
                "rescates": len(registros), "kg": suma("kg"), "raciones": suma("raciones"),
                "personas": suma("personas"), "co2e_kg": suma("co2e_kg"),
            },
            "serie_diaria": serie,
            "por_municipio_origen": agrupar(lambda r: r.municipio_origen),
            "por_municipio_destino": agrupar(lambda r: r.municipio_destino),
            "por_categoria": agrupar(lambda r: r.categoria, lambda c: CATEGORIAS.get(c, c)),
            "top_donantes": agrupar(lambda r: r.donante_id, lambda i: nombres_donantes.get(i, f"#{i}"))[:5],
            "simuladas": {"rescates": len(simuladas), "kg": round(sum(r.kg for r in simuladas), 1)},
            "kpis": self._kpis(donante_id, receptor_id),
            "supuestos": {"kg_por_racion": KG_POR_RACION, "raciones_por_persona_dia": RACIONES_POR_PERSONA_DIA},
        }

    def _kpis(self, donante_id: int | None, receptor_id: int | None) -> dict:
        """KPIs de proceso con donaciones reales (no simuladas)."""
        consulta = select(Donacion).where(Donacion.simulada.is_(False))
        if donante_id is not None:
            consulta = consulta.where(Donacion.donante_id == donante_id)
        reales = list(self.db.scalars(consulta))
        if receptor_id is not None:
            reales = [d for d in reales if d.receptor_id == receptor_id]

        completadas = [d for d in reales if d.estado == EstadoDonacion.COMPLETADA]
        registro = [d.segundos_registro for d in reales if d.segundos_registro is not None]
        primera_oferta = [
            (d.primera_oferta_en - d.creada_en).total_seconds() for d in reales if d.primera_oferta_en
        ]

        primeras_aceptadas = total_con_oferta = 0
        for d in reales:
            primera = self.db.scalar(select(Oferta).where(Oferta.donacion_id == d.id).order_by(Oferta.id))
            if primera is None or primera.estado == EstadoOferta.PENDIENTE:
                continue
            total_con_oferta += 1
            primeras_aceptadas += primera.estado == EstadoOferta.ACEPTADA

        return {
            "donaciones_reales": len(reales),
            "completadas_reales": len(completadas),
            "en_curso": sum(d.estado in EstadoDonacion.ACTIVAS for d in reales),
            "tasa_completadas": round(len(completadas) / len(reales), 2) if reales else None,
            "segundos_registro_mediana": round(median(registro)) if registro else None,
            "segundos_primera_oferta_mediana": round(median(primera_oferta)) if primera_oferta else None,
            "aceptacion_primera_oferta": round(primeras_aceptadas / total_con_oferta, 2) if total_con_oferta else None,
        }

    # ------------------------------------------------------------------ CP-08
    def reporte_donante(self, donante_id: int) -> dict:
        """Reporte de impacto de un donante: totales y la lista de sus rescates."""
        donante = self.db.get(Donante, donante_id)
        if donante is None:
            raise ValueError(f"No existe el donante {donante_id}")
        registros = list(self.db.scalars(
            select(RegistroImpacto).where(RegistroImpacto.donante_id == donante_id)
            .order_by(RegistroImpacto.creado_en.desc())
        ))
        rescates = []
        for r in registros[:20]:
            d = self.db.get(Donacion, r.donacion_id)
            rescates.append({
                "donacion_id": r.donacion_id, "fecha": r.creado_en.isoformat(timespec="minutes"),
                "kg": r.kg, "raciones": r.raciones, "co2e_kg": r.co2e_kg,
                "receptor": d.receptor.nombre if d and d.receptor else None,
                "alimentos": [i["nombre"] for i in d.items] if d else [], "simulada": r.simulada,
            })
        return {
            "donante": {"id": donante.id, "nombre": donante.nombre, "municipio": donante.municipio},
            "resumen": self.resumen(donante_id=donante_id),
            "rescates": rescates,
        }
