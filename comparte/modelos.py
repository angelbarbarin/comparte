"""Modelo de dominio (tablas) de ComParte.

Las clases mapean 1 a 1 al diagrama de clases que el equipo debe entregar el 24 de noviembre
(ver ``docs/ARQUITECTURA.md``). Convención: nombres de dominio en español, sin acentos.

Las fechas son hora local del AMG (*naive*); ver ``reloj.py``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# --------------------------------------------------------------------------- catálogos de estados
class EstadoDonacion:
    """Ciclo de vida de una donación (lo mueve el orquestador)."""

    REGISTRADA = "registrada"  # el Captador la creó; el orquestador aún no la enruta
    PENDIENTE_VALIDACION = "pendiente_validacion"  # esperando revisión humana (alimento de riesgo)
    RECHAZADA = "rechazada"  # la persona revisora la rechazó
    OFRECIDA = "ofrecida"  # hay una oferta pendiente con un receptor
    SIN_RECEPTOR = "sin_receptor"  # ningún receptor viable; requiere atención del administrador
    ASIGNADA = "asignada"  # un receptor aceptó; se busca/espera voluntario
    SIN_VOLUNTARIO = "sin_voluntario"  # ningún voluntario viable; requiere atención
    EN_RECOLECCION = "en_recoleccion"  # un voluntario aceptó y va por la donación
    EN_CAMINO = "en_camino"  # el voluntario la recogió y va hacia el receptor
    ENTREGADA = "entregada"  # el voluntario entregó; falta la confirmación del receptor
    COMPLETADA = "completada"  # el receptor confirmó; el impacto quedó registrado
    CADUCADA = "caducada"  # pasó la fecha de caducidad antes de completarse

    FINALES = frozenset({RECHAZADA, COMPLETADA, CADUCADA})
    ACTIVAS = frozenset(
        {
            REGISTRADA,
            PENDIENTE_VALIDACION,
            OFRECIDA,
            SIN_RECEPTOR,
            ASIGNADA,
            SIN_VOLUNTARIO,
            EN_RECOLECCION,
            EN_CAMINO,
            ENTREGADA,
        }
    )


class EstadoOferta:
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    EXPIRADA = "expirada"
    CANCELADA = "cancelada"


class EstadoRecoleccion:
    PROPUESTA = "propuesta"
    ACEPTADA = "aceptada"
    RECOGIDA = "recogida"
    ENTREGADA = "entregada"
    RECHAZADA = "rechazada"
    EXPIRADA = "expirada"
    CANCELADA = "cancelada"


class Agente:
    """Nombres de quien toma una decisión (para la bitácora de auditoría)."""

    CAPTADOR = "captador"
    COORDINADOR = "coordinador"
    LOGISTICO = "logistico"
    IMPACTO = "impacto"
    ORQUESTADOR = "orquestador"
    HUMANO = "humano"
    SISTEMA = "sistema"


# ------------------------------------------------------------------------------------ actores
class Donante(Base):
    __tablename__ = "donantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    giro: Mapped[str] = mapped_column(String(40))  # panaderia, supermercado, restaurante, ...
    direccion: Mapped[str] = mapped_column(String(200))
    municipio: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    contacto: Mapped[str] = mapped_column(String(80), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")


class Receptor(Base):
    __tablename__ = "receptores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(40))  # banco_alimentos, comedor, albergue, casa_hogar
    direccion: Mapped[str] = mapped_column(String(200))
    municipio: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    horario_apertura: Mapped[str] = mapped_column(String(5), default="08:00")  # "HH:MM"
    horario_cierre: Mapped[str] = mapped_column(String(5), default="20:00")
    personas_atendidas: Mapped[int] = mapped_column(Integer, default=0)
    # categoria -> prioridad 1 (útil) a 3 (muy necesario). Categorías: ver conocimiento/catalogo.py
    necesidades: Mapped[dict] = mapped_column(JSON, default=dict)
    capacidad_diaria_kg: Mapped[float] = mapped_column(Float, default=0.0)
    capacidad_frio_kg: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = sin refrigeración
    verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    contacto: Mapped[str] = mapped_column(String(80), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")


class Voluntario(Base):
    __tablename__ = "voluntarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    telefono: Mapped[str] = mapped_column(String(30), default="")
    vehiculo: Mapped[str] = mapped_column(String(40))  # auto, camioneta, moto, bicicleta
    capacidad_kg: Mapped[float] = mapped_column(Float)
    tiene_hielera: Mapped[bool] = mapped_column(Boolean, default=False)
    municipio: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)  # ubicación base simulada
    lon: Mapped[float] = mapped_column(Float)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True)
    disponible_desde: Mapped[str] = mapped_column(String(5), default="08:00")
    disponible_hasta: Mapped[str] = mapped_column(String(5), default="22:00")


# -------------------------------------------------------------------------------- conversación
class Conversacion(Base):
    __tablename__ = "conversaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    donante_id: Mapped[int] = mapped_column(ForeignKey("donantes.id"))
    canal: Mapped[str] = mapped_column(String(20), default="web")
    estado: Mapped[str] = mapped_column(String(20), default="abierta")  # abierta | cerrada
    borrador: Mapped[dict] = mapped_column(JSON, default=dict)  # donación en construcción
    donacion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime)

    donante: Mapped[Donante] = relationship()
    mensajes: Mapped[list[Mensaje]] = relationship(
        back_populates="conversacion", order_by="Mensaje.id", cascade="all, delete-orphan"
    )


class Mensaje(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversacion_id: Mapped[int] = mapped_column(ForeignKey("conversaciones.id"))
    # "donante" o el nombre del agente que habla (captador, coordinador, logistico, impacto, sistema)
    rol: Mapped[str] = mapped_column(String(20))
    texto: Mapped[str] = mapped_column(Text)
    imagen: Mapped[str | None] = mapped_column(String(300), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime)

    conversacion: Mapped[Conversacion] = relationship(back_populates="mensajes")


# ----------------------------------------------------------------------------------- donación
class Donacion(Base):
    __tablename__ = "donaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    donante_id: Mapped[int] = mapped_column(ForeignKey("donantes.id"))
    conversacion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default=EstadoDonacion.REGISTRADA)

    # [{"nombre","clave","categoria","cantidad","unidad","kg"}]
    items: Mapped[list] = mapped_column(JSON, default=list)
    total_kg: Mapped[float] = mapped_column(Float, default=0.0)
    categoria_principal: Mapped[str] = mapped_column(String(30), default="abarrotes")
    requiere_frio: Mapped[bool] = mapped_column(Boolean, default=False)
    caduca_en: Mapped[datetime] = mapped_column(DateTime)
    caducidad_estimada: Mapped[bool] = mapped_column(Boolean, default=False)
    recoleccion_desde: Mapped[datetime] = mapped_column(DateTime)
    recoleccion_hasta: Mapped[datetime] = mapped_column(DateTime)
    condiciones: Mapped[list] = mapped_column(JSON, default=list)
    foto: Mapped[str | None] = mapped_column(String(300), nullable=True)
    inocuidad: Mapped[dict] = mapped_column(JSON, default=dict)  # resultado de la evaluación
    evaluacion: Mapped[dict] = mapped_column(JSON, default=dict)  # ranking de receptores (explicable)

    receptor_id: Mapped[int | None] = mapped_column(ForeignKey("receptores.id"), nullable=True)
    kg_recibidos: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulada: Mapped[bool] = mapped_column(Boolean, default=False)  # historial de demostración
    segundos_registro: Mapped[int | None] = mapped_column(Integer, nullable=True)

    creada_en: Mapped[datetime] = mapped_column(DateTime)
    primera_oferta_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    asignada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entregada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    donante: Mapped[Donante] = relationship()
    receptor: Mapped[Receptor | None] = relationship()
    ofertas: Mapped[list[Oferta]] = relationship(
        back_populates="donacion", order_by="Oferta.id", cascade="all, delete-orphan"
    )
    recolecciones: Mapped[list[Recoleccion]] = relationship(
        back_populates="donacion", order_by="Recoleccion.id", cascade="all, delete-orphan"
    )


class Oferta(Base):
    """Propuesta del Agente Coordinador a un receptor (CP-04)."""

    __tablename__ = "ofertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    donacion_id: Mapped[int] = mapped_column(ForeignKey("donaciones.id"))
    receptor_id: Mapped[int] = mapped_column(ForeignKey("receptores.id"))
    estado: Mapped[str] = mapped_column(String(20), default=EstadoOferta.PENDIENTE)
    puntaje: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    desglose: Mapped[dict] = mapped_column(JSON, default=dict)
    justificacion: Mapped[str] = mapped_column(Text, default="")
    creada_en: Mapped[datetime] = mapped_column(DateTime)
    vence_en: Mapped[datetime] = mapped_column(DateTime)
    respondida_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)

    donacion: Mapped[Donacion] = relationship(back_populates="ofertas")
    receptor: Mapped[Receptor] = relationship()


class Recoleccion(Base):
    """Asignación del Agente Logístico a un voluntario (CP-05)."""

    __tablename__ = "recolecciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    donacion_id: Mapped[int] = mapped_column(ForeignKey("donaciones.id"))
    voluntario_id: Mapped[int] = mapped_column(ForeignKey("voluntarios.id"))
    estado: Mapped[str] = mapped_column(String(20), default=EstadoRecoleccion.PROPUESTA)
    ruta: Mapped[dict] = mapped_column(JSON, default=dict)  # puntos, tramos, distancia_km, duracion_min
    recoger_estimado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entrega_estimada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    justificacion: Mapped[str] = mapped_column(Text, default="")
    creada_en: Mapped[datetime] = mapped_column(DateTime)
    vence_en: Mapped[datetime] = mapped_column(DateTime)
    respondida_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recogida_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entregada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)

    donacion: Mapped[Donacion] = relationship(back_populates="recolecciones")
    voluntario: Mapped[Voluntario] = relationship()


# ----------------------------------------------------------------------- impacto y auditoría
class RegistroImpacto(Base):
    """Foto del impacto de un rescate completado (CP-07). Se guarda para que no cambie si
    después se ajustan los factores de conversión."""

    __tablename__ = "registros_impacto"

    id: Mapped[int] = mapped_column(primary_key=True)
    donacion_id: Mapped[int] = mapped_column(ForeignKey("donaciones.id"), unique=True)
    donante_id: Mapped[int] = mapped_column(ForeignKey("donantes.id"))
    receptor_id: Mapped[int] = mapped_column(ForeignKey("receptores.id"))
    municipio_origen: Mapped[str] = mapped_column(String(60))
    municipio_destino: Mapped[str] = mapped_column(String(60))
    categoria: Mapped[str] = mapped_column(String(30))
    kg: Mapped[float] = mapped_column(Float)
    raciones: Mapped[float] = mapped_column(Float)
    personas: Mapped[float] = mapped_column(Float)
    co2e_kg: Mapped[float] = mapped_column(Float)
    simulada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime)


class EventoAgente(Base):
    """Bitácora de auditoría: qué agente decidió qué y por qué (requisito de seguridad, sección 7)."""

    __tablename__ = "eventos_agente"

    id: Mapped[int] = mapped_column(primary_key=True)
    donacion_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    conversacion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agente: Mapped[str] = mapped_column(String(20))
    accion: Mapped[str] = mapped_column(String(60))
    resumen: Mapped[str] = mapped_column(Text)
    detalle: Mapped[dict] = mapped_column(JSON, default=dict)
    creado_en: Mapped[datetime] = mapped_column(DateTime)
