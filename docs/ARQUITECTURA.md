# Arquitectura de ComParte

> Borradores en Mermaid (GitHub los dibuja directamente) de los diagramas que el equipo debe entregar el
> 24 de noviembre: **componentes, estados, secuencias y clases**. Reflejan el código del MVP; si el código
> cambia, actualiza el diagrama. Para el de **casos de uso** ver [`CASOS_DE_USO.md`](CASOS_DE_USO.md).
> Mermaid sirve para revisar rápido; para la entrega final conviene redibujarlos en draw.io o PlantUML.

## 1. Diagrama de componentes

Los cuatro agentes y el orquestador son componentes separados (como pidió el profesor). Los agentes **no se
llaman entre sí**: el orquestador decide quién actúa según el estado de la donación.

```mermaid
flowchart TB
  subgraph Canales
    WEB["Chat web (MVP)"]
    WA["WhatsApp Business (pendiente)"]:::futuro
  end

  subgraph Backend["Backend FastAPI"]
    API["API REST /api"]
    ORQ["Orquestador"]
    subgraph Agentes
      CAP["Agente Captador"]
      COO["Agente Coordinador"]
      LOG["Agente Logistico"]
      IMP["Agente de Impacto"]
    end
    LLM["Motor de lenguaje: reglas o Claude"]
    CON["Conocimiento: catalogo, inocuidad, factores"]
    GEO["Geo: distancias y tiempos"]
    BIT[("Bitacora de auditoria")]
  end

  DB[("Base de datos: SQLite, luego PostgreSQL")]
  CLAUDE["API de Claude (opcional)"]:::externo
  MAPAS["OpenStreetMap (mosaicos del mapa)"]:::externo

  WEB --> API
  WA -. "adaptador pendiente" .-> API
  API --> ORQ
  ORQ --> CAP
  ORQ --> COO
  ORQ --> LOG
  ORQ --> IMP
  CAP --> LLM
  LLM -. "si hay clave" .-> CLAUDE
  CAP --> CON
  IMP --> CON
  COO --> GEO
  LOG --> GEO
  ORQ --> BIT
  CAP --> DB
  COO --> DB
  LOG --> DB
  IMP --> DB
  ORQ --> DB
  WEB -. "tiles" .-> MAPAS

  classDef futuro stroke-dasharray: 5 5
  classDef externo fill:#eeeeee
```

| Componente | Módulo | Responsabilidad |
|---|---|---|
| Orquestador | `comparte/orquestador.py` | Enruta, pide revisión humana, aplica vencimientos, registra traspasos |
| Captador | `comparte/agentes/captador.py` | Conversación, estructura la donación, inocuidad |
| Coordinador | `comparte/agentes/coordinador.py` | Puntaje de receptores, ofertas, reasignación |
| Logístico | `comparte/agentes/logistico.py` | Voluntario, ruta, seguimiento |
| Impacto | `comparte/agentes/impacto.py` | Métricas, tablero, reporte por donante |
| Motor de lenguaje | `comparte/llm/` | `ExtractorReglas` y `ExtractorClaude` tras la misma interfaz |
| Conocimiento | `comparte/conocimiento/` | Catálogo de alimentos, reglas de inocuidad, factores de impacto |
| API | `comparte/api/` | Rutas REST y serialización |
| Interfaz | `web/` | Chat y consolas (HTML + JS modular) |

## 2. Estados de una donación

```mermaid
stateDiagram-v2
  [*] --> registrada: el Captador la registra
  registrada --> pendiente_validacion: riesgo alto o alimento desconocido
  registrada --> ofrecida: sin riesgo, el Coordinador ofrece
  pendiente_validacion --> ofrecida: una persona aprueba
  pendiente_validacion --> rechazada: una persona rechaza
  ofrecida --> ofrecida: rechaza o no responde, se reasigna
  ofrecida --> asignada: el receptor acepta
  ofrecida --> sin_receptor: ningun receptor viable
  sin_receptor --> ofrecida: reintento del administrador
  asignada --> en_recoleccion: el voluntario acepta
  asignada --> sin_voluntario: ningun voluntario viable
  sin_voluntario --> asignada: reintento con propuesta nueva
  en_recoleccion --> en_camino: el voluntario recoge
  en_camino --> entregada: el voluntario entrega
  entregada --> completada: el receptor confirma
  completada --> [*]
  rechazada --> [*]
  caducada --> [*]
  note right of caducada
    Desde cualquier estado activo
    salvo entregada, si pasa la
    fecha de caducidad
  end note
```

## 3. Secuencias

### 3.1 Rescate completo sin riesgo

```mermaid
sequenceDiagram
  actor D as Donante
  participant O as Orquestador
  participant CA as Captador
  participant CO as Coordinador
  participant L as Logistico
  participant I as Impacto
  actor R as Receptor
  actor V as Voluntario

  D->>O: "25 kg de pan del dia..."
  O->>CA: procesar_mensaje
  CA-->>D: resumen y pide confirmar
  D->>O: "si"
  O->>CA: procesar_mensaje
  CA-->>O: donacion registrada con su evaluacion de inocuidad
  O->>CO: ofrecer(donacion)
  CO-->>R: oferta con puntaje y justificacion
  R->>O: responder_oferta(aceptar)
  O->>L: proponer(donacion)
  L-->>V: propuesta con ruta y horarios
  V->>O: aceptar, recogida, entregada
  R->>O: confirmar_recepcion(kg)
  O->>I: registrar(donacion)
  I-->>D: constancia de impacto
```

### 3.2 Alimento de riesgo con supervisión humana

```mermaid
sequenceDiagram
  actor D as Donante
  participant O as Orquestador
  participant CA as Captador
  actor A as Administrador
  participant CO as Coordinador

  D->>O: "12 kg de pollo y 8 L de leche"
  O->>CA: procesar_mensaje
  CA-->>D: pregunta por la cadena de frio
  D->>O: "si"
  CA-->>D: resumen con aviso de revision humana
  D->>O: "si"
  CA-->>O: donacion registrada, requiere_revision
  O-->>A: pendiente_validacion (nadie recibe ofertas)
  A->>O: revision_humana(aprobar, nota)
  O->>CO: ofrecer(donacion)
  Note over CO: solo receptores con refrigeracion y capacidad de frio
```

### 3.3 Rechazo o falta de respuesta

```mermaid
sequenceDiagram
  participant O as Orquestador
  participant CO as Coordinador
  actor R1 as Receptor 1
  actor R2 as Receptor 2

  CO-->>R1: oferta (vence en 15 min)
  alt rechaza
    R1->>O: responder_oferta(rechazar, motivo)
  else no responde
    O->>O: tick() marca la oferta como expirada
  end
  O->>CO: ofrecer(donacion) excluyendo a R1
  CO-->>R2: nueva oferta con el siguiente mejor puntaje
```

## 4. Clases del dominio

```mermaid
classDiagram
  class Donante {
    id
    nombre
    giro
    municipio
    lat
    lon
  }
  class Receptor {
    id
    nombre
    tipo
    horario_apertura
    horario_cierre
    necesidades
    capacidad_diaria_kg
    capacidad_frio_kg
    verificado
  }
  class Voluntario {
    id
    nombre
    vehiculo
    capacidad_kg
    tiene_hielera
    disponible
  }
  class Conversacion {
    id
    canal
    borrador
  }
  class Mensaje {
    id
    rol
    texto
    imagen
  }
  class Donacion {
    id
    estado
    items
    total_kg
    caduca_en
    requiere_frio
    inocuidad
    evaluacion
    simulada
  }
  class Oferta {
    id
    estado
    puntaje
    desglose
    justificacion
    vence_en
  }
  class Recoleccion {
    id
    estado
    ruta
    recoger_estimado
    entrega_estimada
  }
  class RegistroImpacto {
    kg
    raciones
    personas
    co2e_kg
  }
  class EventoAgente {
    agente
    accion
    resumen
    detalle
  }

  Donante "1" --> "*" Conversacion
  Conversacion "1" --> "*" Mensaje
  Donante "1" --> "*" Donacion
  Donacion "*" --> "0..1" Receptor : asignada a
  Donacion "1" --> "*" Oferta
  Oferta "*" --> "1" Receptor
  Donacion "1" --> "*" Recoleccion
  Recoleccion "*" --> "1" Voluntario
  Donacion "1" --> "0..1" RegistroImpacto
  Donacion "1" --> "*" EventoAgente
```

### Clases de los agentes

```mermaid
classDiagram
  class Orquestador {
    mensaje_donante()
    revision_humana()
    responder_oferta()
    responder_recoleccion()
    avanzar_recoleccion()
    confirmar_recepcion()
    reintentar()
    tick()
  }
  class AgenteCaptador {
    procesar_mensaje()
  }
  class AgenteCoordinador {
    evaluar_receptores()
    ofrecer()
    responder()
    expirar_vencidas()
  }
  class AgenteLogistico {
    evaluar_voluntarios()
    proponer()
    responder()
    avanzar()
    expirar_vencidas()
  }
  class AgenteImpacto {
    registrar()
    resumen()
    reporte_donante()
  }
  class Extractor {
    <<interface>>
    extraer()
  }
  class ExtractorReglas
  class ExtractorClaude

  Orquestador --> AgenteCaptador
  Orquestador --> AgenteCoordinador
  Orquestador --> AgenteLogistico
  Orquestador --> AgenteImpacto
  AgenteCaptador --> Extractor
  Extractor <|.. ExtractorReglas
  Extractor <|.. ExtractorClaude
```

## 5. Decisiones de diseño y sus razones

| Decisión | Razón | Costo / alternativa |
|---|---|---|
| **Canal web primero**, WhatsApp después | La API de WhatsApp Business puede ser costosa (retroalimentación del profesor); el orquestador no depende del canal | WhatsApp requiere un adaptador y una cuenta de Meta Business |
| **Motor de lenguaje intercambiable** (reglas o Claude) | La demo es gratis, determinista y funciona sin internet; Claude se activa con una clave y agrega visión | El motor de reglas entiende un subconjunto del español (ver `ALCANCE_MVP.md`) |
| **Política del agente fuera del motor de lenguaje** | El comportamiento (qué preguntar, cuándo bloquear) es igual con ambos motores y es testeable | El Captador no es un bucle libre con herramientas; es un diálogo guiado |
| **Orquestador central; agentes que no se hablan entre sí** | Módulos independientes y probables por separado (mantenibilidad); un solo lugar para el flujo | El orquestador concentra la lógica de flujo |
| **Decisiones explicables y bitácora de auditoría** | Confianza y auditoría exigidas en la sección 7; se ve qué agente hizo qué | Más datos guardados por donación |
| **Supervisión humana en riesgo y organizaciones nuevas** | Restricciones éticas y de inocuidad del documento de visión | Una persona se vuelve cuello de botella (por eso el tablero de pendientes) |
| **Equidad como componente del puntaje** | Medida concreta contra "no discriminar entre receptores" | El peso (10 %) es una decisión a validar con un banco de alimentos |
| **Reloj controlable (`reloj.py`)** | Pruebas deterministas y demo reproducible a cualquier hora | Hay que recordar usar `reloj.ahora()` y no `datetime.now()` |
| **Vencimientos evaluados al consultar (`tick`)** | Sin planificador en segundo plano: menos piezas móviles | Si nadie consulta, no se reasigna; pendiente un planificador |
| **SQLite + SQLAlchemy** | Cero instalación; PostgreSQL es solo cambiar `COMPARTE_DB_URL` | Sin PostGIS (distancias en Python) |
| **Interfaz sin compilación** (JS modular) | Cualquiera del equipo la edita sin instalar Node | Sin tipado ni empaquetado |

## 6. Del requisito al código

| Requisito | Dónde vive | Pruebas |
|---|---|---|
| CP-01 Registro conversacional | `agentes/captador.py`, `llm/` | `test_captador.py`, `test_extractor_*.py`, `test_evaluacion.py` |
| CP-02 Inocuidad | `conocimiento/inocuidad.py`, revisión en `orquestador.py` | `test_conocimiento.py`, `test_orquestador.py` |
| CP-03 Perfil de receptores | `modelos.py`, `datos_demo.py`, `api/rutas.py` | `test_datos_demo.py`, `test_api.py` |
| CP-04 Asignación inteligente | `agentes/coordinador.py` | `test_coordinador.py` |
| CP-05 Coordinación de recolección | `agentes/logistico.py` | `test_logistico.py` |
| CP-06 Confirmación y trazabilidad | `orquestador.py`, bitácora | `test_orquestador.py`, `test_api.py` |
| CP-07 Tablero de impacto | `agentes/impacto.py`, `web/js/vistas/impacto.js` | `test_impacto.py` |
| CP-08 Reportes para donantes (parcial) | `AgenteImpacto.reporte_donante` | `test_impacto.py` |
| CP-09 Administración (parcial) | `web/js/vistas/admin.js`, rutas `/admin` | `test_api.py` |

## 7. Rangos de calidad (sección 7 del documento de visión)

| Atributo | Estado en el MVP |
|---|---|
| Rendimiento: respuesta ≤ 5 s | Con reglas, milisegundos. Con Claude **no medido** |
| Precisión ≥ 90 % | Reglas: lote B 85 % en la primera corrida y 90 % tras corregir un error real; ver `ALCANCE_MVP.md`. Claude **no medido** |
| Usabilidad: donar en ≤ 1 min | Dos mensajes; el tiempo de registro se mide en el tablero |
| Seguridad: cifrado, roles, auditoría | **Auditoría sí** (bitácora). Roles **no**. Cifrado depende del despliegue (HTTPS) |
| Mantenibilidad: agentes independientes | Sí: módulos separados y probados por separado |
| Escalabilidad: 500 donaciones/día | **No medido** |
| Disponibilidad ≥ 99 % | **No aplica** hasta desplegar |
