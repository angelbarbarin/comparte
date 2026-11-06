"""Datos de prueba del piloto simulado (AMG).

El documento de visión promete un piloto simulado con al menos 10 donantes y 5 receptores del
Área Metropolitana de Guadalajara. Aquí se cargan:

* 10 donantes, 6 receptores (uno sin verificar, para mostrar la regla de organizaciones nuevas) y
  6 voluntarios.
* Un historial de rescates *simulados* (ver ``sembrar_historial``) para que el tablero de
  impacto no esté vacío.

⚠️  **Todos los nombres, teléfonos y organizaciones son ficticios.** Las coordenadas son
aproximadas de colonias y centros reales del AMG, solo para que las distancias sean verosímiles.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .modelos import Donante, Receptor, Voluntario

DONANTES = [
    # nombre, giro, dirección, municipio, lat, lon, contacto
    ("Panadería La Espiga", "panaderia", "Independencia 123, Centro", "Tlaquepaque", 20.6402, -103.3120, "Rosa Medina"),
    ("Supermercado Fresko Chapalita", "supermercado", "Av. Guadalupe 1200, Chapalita", "Guadalajara", 20.6685, -103.3920, "Jorge Salas"),
    ("Frutas Don Chuy (Abastos)", "mercado", "Mercado de Abastos, bodega 14", "Guadalajara", 20.6525, -103.3610, "Jesús Cortés"),
    ("Restaurante Los Arcos", "restaurante", "Av. Hidalgo 45, Centro", "Zapopan", 20.7215, -103.3860, "Elena Prieto"),
    ("Comedor Corporativo TechSur", "comedor_institucional", "Av. Patria 2100, Puerta de Hierro", "Zapopan", 20.7105, -103.4130, "Raúl Íñiguez"),
    ("Tortillería La Güera", "tortilleria", "Hidalgo 310, Centro", "Tonalá", 20.6245, -103.2335, "Guadalupe Ramos"),
    ("Cocina Universitaria Campus Sur", "comedor_institucional", "Periférico Sur 8585", "Tlaquepaque", 20.6075, -103.4145, "Mónica Aguirre"),
    ("Supermercado La Canasta", "supermercado", "Av. López Mateos Sur 5600", "Tlajomulco", 20.4738, -103.4432, "Héctor Vela"),
    ("Verdulería El Campo", "verduleria", "Calz. Independencia 400, Centro", "Guadalajara", 20.6772, -103.3455, "Irma Duarte"),
    ("Hotel Plaza Real (cocina)", "hotel", "Av. Providencia 2400", "Guadalajara", 20.6935, -103.3895, "Chef Tomás Beltrán"),
]

RECEPTORES = [
    # nombre, tipo, dirección, municipio, lat, lon, abre, cierra, personas,
    # necesidades {categoría: prioridad 1-3}, capacidad kg/día, capacidad frío kg, verificado
    ("Banco de Alimentos Nueva Esperanza", "banco_alimentos", "Calz. del Ejército 800", "Guadalajara",
     20.6350, -103.3400, "07:00", "19:00", 1200,
     {"pan": 2, "fruta": 3, "verdura": 3, "abarrotes": 3, "lacteos": 2, "proteina": 2, "preparado": 1},
     800, 200, True, "Coord. Patricia Núñez"),
    ("Comedor Comunitario Santa Cecilia", "comedor", "Av. Tonaltecas 55", "Tonalá",
     20.6270, -103.2430, "09:00", "19:00", 120,
     {"pan": 3, "verdura": 3, "fruta": 2, "abarrotes": 3, "preparado": 2},
     80, 0, True, "Doña Lupita Cruz"),
    ("Albergue Casa del Camino", "albergue", "Calle Oblatos 210", "Guadalajara",
     20.7000, -103.3150, "00:00", "23:59", 60,
     {"preparado": 3, "proteina": 3, "lacteos": 2, "pan": 2, "fruta": 2, "verdura": 2},
     120, 30, True, "Hno. Samuel Ortega"),
    ("Casa Hogar Semillas", "casa_hogar", "Camino a Nextipac 12", "Zapopan",
     20.7380, -103.4020, "08:00", "21:00", 45,
     {"lacteos": 3, "fruta": 3, "pan": 2, "abarrotes": 2, "verdura": 2},
     60, 15, True, "Lic. Verónica Soto"),
    ("Comedor Los Pinos", "comedor", "Av. Los Pinos 90", "Tlajomulco",
     20.4980, -103.4400, "08:00", "18:00", 150,
     {"verdura": 3, "abarrotes": 3, "pan": 2, "fruta": 2},
     100, 0, True, "Sr. Gilberto Paz"),
    ("Centro Comunitario Nuevo Sol", "comedor", "Calle Sol 7, El Salto Centro", "El Salto",
     20.5230, -103.1800, "09:00", "17:00", 90,
     {"pan": 3, "abarrotes": 3},
     70, 0, False, "Marisol Tapia"),  # sin verificar: no recibe ofertas hasta que el admin lo valide
]

VOLUNTARIOS = [
    # nombre, vehículo, capacidad kg, hielera, municipio, lat, lon, desde, hasta
    ("Mariana López", "auto", 40, False, "Guadalajara", 20.6700, -103.3600, "08:00", "22:00"),
    ("Carlos Ramírez", "camioneta", 300, True, "Zapopan", 20.7150, -103.4000, "08:00", "22:00"),
    ("Fernanda Ortiz", "moto", 15, False, "Tlaquepaque", 20.6450, -103.3200, "09:00", "21:00"),
    ("Luis Hernández", "auto", 50, True, "Tonalá", 20.6300, -103.2400, "08:00", "22:00"),
    ("Sofía Mendoza", "camioneta", 200, False, "Tlajomulco", 20.4900, -103.4450, "08:00", "20:00"),
    ("Andrés Navarro", "bicicleta", 10, False, "Guadalajara", 20.6760, -103.3480, "09:00", "19:00"),
]


def sembrar_actores(db: Session) -> dict[str, int]:
    """Carga donantes, receptores y voluntarios si la base está vacía. Devuelve conteos."""
    if db.scalar(select(Donante.id).limit(1)) is not None:
        return {"donantes": 0, "receptores": 0, "voluntarios": 0}

    for n, g, d, m, la, lo, c in DONANTES:
        db.add(Donante(nombre=n, giro=g, direccion=d, municipio=m, lat=la, lon=lo, contacto=c,
                       telefono="33 0000 0000"))
    for (n, t, d, m, la, lo, ab, ci, p, nec, cap, frio, ver, c) in RECEPTORES:
        db.add(Receptor(nombre=n, tipo=t, direccion=d, municipio=m, lat=la, lon=lo,
                        horario_apertura=ab, horario_cierre=ci, personas_atendidas=p,
                        necesidades=nec, capacidad_diaria_kg=cap, capacidad_frio_kg=frio,
                        verificado=ver, contacto=c, telefono="33 0000 0000"))
    for (n, v, cap, hiel, m, la, lo, de, ha) in VOLUNTARIOS:
        db.add(Voluntario(nombre=n, vehiculo=v, capacidad_kg=cap, tiene_hielera=hiel, municipio=m,
                          lat=la, lon=lo, disponible=True, disponible_desde=de, disponible_hasta=ha,
                          telefono="33 0000 0000"))
    db.commit()
    return {"donantes": len(DONANTES), "receptores": len(RECEPTORES), "voluntarios": len(VOLUNTARIOS)}
