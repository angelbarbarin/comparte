# Alcance del MVP de ComParte

> Documento de definición del alcance de la **primera versión funcional (MVP)**.
> Parte del [Documento de Visión y Alcances v1.0](Vision_y_Alcances_ComParte.docx) y de la
> retroalimentación del profesor (2 de noviembre). Si algo de este documento contradice
> al código, gana el código y hay que corregir el documento.

## 1. Objetivo del MVP

Demostrar de punta a punta, con datos de prueba del Área Metropolitana de Guadalajara (AMG),
que **un excedente de alimentos reportado por un donante se convierte en un rescate
completado sin que ninguna persona del equipo coordine nada a mano**:

```
Donante (chat) → Captador → [revisión humana si hay riesgo] → Coordinador → Logístico → Impacto
                                         ▲ todo mediado por el Orquestador y registrado en bitácora ▲
```

El MVP **no** busca ser un producto desplegable en producción. Busca ser una demostración
creíble, medible y explicable del concepto, y una base de código que el equipo pueda extender
hasta la entrega final del **24 de noviembre de 2026**.

### Decisiones que salen de la retroalimentación

| Retroalimentación | Decisión en el MVP |
|---|---|
| "La integración con WhatsApp puede ser costosa; ten un plan B (web)" | **El canal principal de la demo es un chat web.** El orquestador es independiente del canal, así que WhatsApp se agrega después como un adaptador (ver `docs/PLAN_EQUIPO.md`). |
| "Define métricas de kg rescatados y personas beneficiadas" | Sección 4 de este documento + tablero de impacto en la aplicación. |
| "Los cuatro agentes y el orquestador deben verse claramente" | Cada agente es un módulo propio (`comparte/agentes/`), el orquestador es otro (`comparte/orquestador.py`) y **cada decisión queda en una bitácora visible en la interfaz** con el agente que la tomó. |
| "Valida el flujo con un banco de alimentos real" | **No se hizo en el MVP**; está en el plan del equipo. Los perfiles de receptores y las reglas de inocuidad son supuestos razonables, no validados. |

## 2. Dimensionamiento: ¿por qué esto cabe en dos semanas con tres personas?

Se recortó verticalmente (todos los agentes, pero con la lógica más simple que sea demostrable)
y no horizontalmente (no se dejó un agente sin hacer). Lo que **no** se construyó es lo caro
y poco visible en una demo: autenticación real, WhatsApp, mapas de pago, despliegue en nube,
PostGIS, notificaciones push.

## 3. Estado por característica del documento de visión

Leyenda: ✅ incluido · 🟡 parcial (se indica hasta dónde llega) · ⛔ fuera del MVP.

| ID | Característica | MoSCoW | Estado | Hasta dónde llega en el MVP |
|---|---|---|---|---|
| CP-01 | Registro conversacional de donaciones | Must | ✅ | Chat web en español. Entiende texto libre (cantidades, unidades, caducidad, ventana de recolección). Pregunta lo que falta y **confirma antes de registrar**. La foto se adjunta y se guarda; **solo se interpreta si hay `ANTHROPIC_API_KEY`** (modo Claude con visión). Sin clave funciona un motor de reglas, determinista y gratuito. |
| CP-02 | Evaluación de inocuidad | Must | ✅ | Reglas por categoría (no perecedero / perecedero / refrigerado / preparado), alimentos prohibidos, producto caducado o en mal estado. Los casos de riesgo **quedan en cola de revisión humana** y no avanzan hasta que alguien los aprueba. Las reglas son heurísticas del equipo, **no una certificación sanitaria**. |
| CP-03 | Perfil de receptores | Must | 🟡 | Perfil completo en base de datos (ubicación, horario, necesidades con prioridad, capacidad diaria, cadena de frío, verificación). Se consulta y se crea por API y se ve en el mapa. **No hay formulario de autoalta en la interfaz.** Un receptor nuevo nace *no verificado* y no recibe ofertas hasta que un administrador lo valida. |
| CP-04 | Asignación inteligente | Must | ✅ | Puntaje 0-100 con cinco componentes explicables (necesidad, cercanía, margen de caducidad, capacidad, equidad). Filtros duros con motivo (sin cadena de frío, no llega a tiempo, sin capacidad, no verificado). Oferta con tiempo límite; si rechaza o no responde, **reasigna** al siguiente. **No divide** una donación entre varios receptores. |
| CP-05 | Coordinación de recolección | Should | 🟡 | Elige voluntario por disponibilidad, capacidad del vehículo, hielera y tiempo total de ruta; calcula ruta donante→receptor y ETA con distancia en línea recta ajustada (sin API de mapas); reasigna si el voluntario rechaza. **Los voluntarios son simulados** (como permite la sección 4.3 del documento de visión). |
| CP-06 | Confirmación y trazabilidad | Should | ✅ | Voluntario (acepta, recogí, entregué) y receptor (confirma recepción y kg reales) confirman cada etapa; el donante recibe avisos en su chat. Línea de tiempo completa por donación. |
| CP-07 | Tablero de impacto | Should | ✅ | kg rescatados, raciones, personas beneficiadas, CO2e evitado, serie de 30 días, por municipio, por categoría, ranking de donantes y KPIs de proceso. Incluye un **historial simulado** (claramente rotulado) para que el tablero no esté vacío. |
| CP-08 | Reportes para donantes | Could | 🟡 | Constancia/reporte de impacto **por donante** (API + vista en la interfaz). No hay reporte mensual programado ni PDF. |
| CP-09 | Panel de administración | Could | 🟡 | Cola de aprobación de casos de riesgo, validación de receptores nuevos, bitácora de decisiones de agentes y controles de demo (reiniciar datos, avanzar el reloj). No hay ajuste de reglas desde la interfaz. |
| CP-10 | Notificaciones proactivas | Won't | ⛔ | Excluida en el propio documento de visión para esta versión. |

## 4. Métricas definidas

Las pidió explícitamente el profesor. Todas se calculan en `comparte/agentes/impacto.py` con las
constantes de `comparte/conocimiento/factores_impacto.py`, que **son supuestos editables y deben
validarse** antes de presentarlos como cifras reales.

| Métrica | Definición | Supuesto a validar |
|---|---|---|
| **kg rescatados** | Suma de los kg *confirmados como recibidos* por el receptor (si no confirma cantidad, los kg registrados). | — |
| **Raciones** | `kg rescatados ÷ 0.5` | 1 ración = 0.5 kg de alimento. |
| **Personas beneficiadas (estimado)** | `raciones ÷ 3` = personas alimentadas el equivalente a un día completo (3 comidas). | 3 raciones por persona al día. Alternativa a futuro: usar el padrón real de cada receptor. |
| **CO2e evitado (kg)** | `Σ kg × factor de emisión de la categoría` (huella de producción del alimento que no se desperdicia). | Factores de referencia aproximados (Poore y Nemecek, 2018, vía Our World in Data) **tomados de memoria, sin verificar contra la fuente**; revisar antes de la entrega final. |

KPIs de proceso (contra los rangos de calidad de la sección 7 del documento de visión):

| KPI | Meta del documento | Cómo se mide en el MVP |
|---|---|---|
| Registro de una donación | ≤ 1 min | Del primer mensaje del donante a la confirmación. Con dos mensajes (describir + "sí") es posible. |
| Tiempo del agente para proponer receptor | ≤ 2 min en el 90 % de los casos | `registro → primera oferta` (no incluye el tiempo humano de respuesta del receptor). |
| Respuesta del agente al donante | ≤ 5 s | Latencia de `POST /mensajes`. Con motor de reglas son milisegundos; con Claude depende de la red y del modelo. |
| Precisión de estructuración | ≥ 90 % | `scripts/evaluar_captador.py` sobre un conjunto de mensajes etiquetados. **Los mensajes los escribimos nosotros**, así que es una línea base, no una validación con datos reales. |
| Aceptación a la primera oferta | — | Rescates cuya primera oferta fue aceptada ÷ rescates con oferta. |

## 5. Datos de prueba (piloto simulado)

Cumple lo prometido en el alcance del documento de visión (≥ 10 donantes y ≥ 5 receptores del AMG):

- 10 donantes, 6 receptores (5 verificados + 1 pendiente de validación) y 6 voluntarios.
- ~40 rescates históricos simulados en los últimos 30 días, marcados como `simulada`.
- **Todos los nombres son ficticios.** Las coordenadas son aproximadas de colonias reales del AMG.

## 6. Fuera de alcance y limitaciones conocidas

- Sin autenticación ni control de acceso por rol: la interfaz permite "actuar como" cualquier
  donante, receptor, voluntario o administrador (modo demo). *Esto incumple el atributo de
  seguridad de la sección 7 del documento de visión y es prioridad antes de cualquier piloto real.*
- Sin WhatsApp, sin voz, sin notificaciones push.
- Sin API de mapas: la distancia es línea recta × 1.3 y la velocidad media es 25 km/h.
- Una donación se asigna a **un** receptor y **un** voluntario (no se parte).
- Zona horaria fija `America/Mexico_City`; solo opera en el AMG.
- SQLite en lugar de PostgreSQL/PostGIS (el modelo es compatible; se cambia `COMPARTE_DB_URL`).
- Los tiempos límite de ofertas se evalúan al consultar la API, no con un planificador en segundo plano.
- El motor de reglas entiende un subconjunto razonable del español coloquial; el modo Claude
  existe y está implementado, pero **no pudo probarse contra la API real durante la construcción
  (sin clave)**: solo está cubierto con pruebas que simulan al cliente.
- Los datos de impacto de la demo mezclan rescates reales de la sesión con historial simulado.

## 7. Definición de terminado del MVP

El MVP se considera entregable cuando se cumplen **todas** estas condiciones:

1. `pytest` pasa completo en limpio, sin clave de API ni internet.
2. Con tres comandos (instalar, cargar datos, arrancar) el equipo ve la aplicación funcionando.
3. Se pueden recorrer sin errores los tres escenarios del guion de video (`docs/GUION_VIDEO.md`):
   rescate feliz, rechazo con reasignación y alimento de riesgo con aprobación humana.
4. Cada decisión de cada agente aparece en la bitácora de la donación.
5. El tablero refleja el rescate recién completado.
6. El repositorio está en línea con README, documentación, licencia e historial de commits legible.

## 8. Qué sigue

Ver [`PLAN_EQUIPO.md`](PLAN_EQUIPO.md): reparto sugerido para tres personas hasta el 24 de
noviembre (diagramas UML, video final, validación con un banco de alimentos real, costo de
WhatsApp Business, autenticación y endurecimiento).
