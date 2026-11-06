# Casos de uso del MVP

Insumo directo para dos entregables del 24 de noviembre: el **diagrama de casos de uso** (UML) y el **video con
todos los casos de uso**. Cada caso indica dónde se ve en la interfaz, qué endpoint lo ejecuta y qué prueba lo cubre.

## Actores

| Actor | Quién es | Cómo "actúa" en la demo |
|---|---|---|
| **Donante** | Encargado de tienda, cocina o puesto | Pestaña *Donar* (elige el donante en la lista) |
| **Receptor** | Responsable de un comedor, albergue o banco de alimentos | Pestaña *Receptor* |
| **Voluntario** | Persona con vehículo que recoge y entrega | Pestaña *Voluntario* |
| **Administrador** | Supervisa, valida y atiende excepciones | Pestaña *Admin* |
| **Sistema** | Los agentes y el orquestador (actor secundario) | Automático |

## Lista de casos de uso

| ID | Caso de uso | Actor principal | Requisito |
|---|---|---|---|
| CU-01 | Registrar una donación por chat | Donante | CP-01, CP-02 |
| CU-02 | Adjuntar una foto del excedente | Donante | CP-01 |
| CU-03 | Validar un alimento de riesgo | Administrador | CP-02, CP-09 |
| CU-04 | Responder una oferta de donación | Receptor | CP-04 |
| CU-05 | Reasignar por rechazo o por falta de respuesta | Sistema | CP-04 |
| CU-06 | Aceptar y completar una recolección | Voluntario | CP-05, CP-06 |
| CU-07 | Confirmar la recepción | Receptor | CP-06 |
| CU-08 | Consultar el seguimiento y las decisiones de los agentes | Donante / Administrador | CP-06 |
| CU-09 | Consultar el tablero de impacto | Todos | CP-07 |
| CU-10 | Consultar el reporte de un donante | Donante | CP-08 (parcial) |
| CU-11 | Registrar y verificar un receptor | Administrador | CP-03, CP-09 |
| CU-12 | Atender una donación atorada | Administrador | CP-09 |
| CU-13 | Cancelar por caducidad | Sistema | CP-06 |

Relaciones útiles para el diagrama: CU-01 *incluye* la evaluación de inocuidad; CU-03 *extiende* a CU-01 (solo si hay
riesgo); CU-05 *extiende* a CU-04; CU-02 *extiende* a CU-01; CU-07 *incluye* el registro de impacto.

## Fichas

### CU-01 Registrar una donación por chat
- **Precondición:** el donante existe. **Disparador:** el donante escribe en el chat.
- **Flujo principal:** 1) el donante describe qué, cuánto y (opcional) hasta cuándo y a qué hora pueden pasar; 2) el Captador
  estructura la donación y evalúa la inocuidad; 3) muestra un resumen marcando lo estimado; 4) el donante responde "sí";
  5) se registra la donación y el orquestador la enruta (CU-04 o CU-03).
- **Alternos:** falta la cantidad → el agente la pregunta · alimento refrigerado → pregunta por la cadena de frío ·
  producto caducado, alcohol, medicamentos, mal estado o cadena rota → se **bloquea** con explicación · el donante corrige
  ("son 30 kg") o cancela.
- **Dónde:** *Donar* · `POST /api/conversaciones/{id}/mensajes` · `tests/test_captador.py`, `tests/test_api.py`.

### CU-02 Adjuntar una foto del excedente
- **Flujo:** el donante adjunta una imagen (JPEG/PNG/WebP/GIF, máx. 5 MB) junto con su mensaje; se guarda y queda ligada a la donación.
- **Alterno:** con el motor de reglas la foto no se interpreta (el agente pide el dato por texto); con Claude se lee (no probado con la API real).
- **Dónde:** *Donar* (botón “📎 Foto”) · `tests/test_captador.py::TestFotos`, `tests/test_api.py::TestFotos`.

### CU-03 Validar un alimento de riesgo
- **Disparador:** una donación queda en `pendiente_validacion` (carnes, lácteos, comida preparada o alimento no reconocido).
- **Flujo:** el administrador revisa motivos, condiciones y alimentos; **aprueba** (se abre de nuevo la ventana de
  recolección y el Coordinador ofrece solo a receptores con refrigeración) o **rechaza** (se avisa al donante).
- **Dónde:** *Admin* → “Alimentos de riesgo por validar” · `POST /api/donaciones/{id}/revision` · `tests/test_orquestador.py::TestSupervisionHumana`.

### CU-04 Responder una oferta de donación
- **Flujo:** el receptor ve la oferta (alimentos, kg, donante, caducidad, justificación, cuenta regresiva) y la **acepta** o
  la **rechaza** con motivo. Si acepta, el Logístico propone la recolección.
- **Dónde:** *Receptor* · `POST /api/ofertas/{id}/respuesta` · `tests/test_coordinador.py`, `tests/test_orquestador.py`.

### CU-05 Reasignar por rechazo o falta de respuesta
- **Flujo:** si el receptor rechaza o pasan 15 min sin respuesta, el Coordinador ofrece al siguiente mejor receptor. Si no queda
  ninguno, la donación pasa a `sin_receptor` (CU-12). Igual para voluntarios (10 min).
- **Dónde:** *Admin* → “Adelantar 16 min” para simular el tiempo · `POST /api/demo/avanzar-reloj` · `tests/test_api.py::TestControlesDeDemo`.

### CU-06 Aceptar y completar una recolección
- **Flujo:** el voluntario ve la propuesta (ruta, tiempos, aviso de hielera), la **acepta** o **rechaza**; luego avisa “ya recogí” y
  “ya entregué”. El donante recibe avisos en su chat.
- **Alterno:** los estados no se pueden saltar (no se entrega lo que no se recogió).
- **Dónde:** *Voluntario* · `POST /api/recolecciones/{id}/respuesta` y `/avance` · `tests/test_logistico.py`.

### CU-07 Confirmar la recepción
- **Flujo:** el receptor confirma que recibió y puede **corregir los kg reales**; el Agente de Impacto registra el rescate y el
  donante recibe su constancia.
- **Dónde:** *Receptor* → “Por confirmar recepción” · `POST /api/donaciones/{id}/confirmacion-recepcion` · `tests/test_impacto.py`.

### CU-08 Consultar el seguimiento y las decisiones de los agentes
- **Flujo:** se ve el progreso, el mapa con la ruta, **por qué** se eligió ese receptor (puntaje desglosado y motivos de cada
  descarte), por qué ese voluntario y la línea de tiempo con cada agente y cada traspaso del orquestador.
- **Dónde:** *Seguimiento* y *Admin* (bitácora) · `GET /api/donaciones/{id}`, `GET /api/eventos`.

### CU-09 Consultar el tablero de impacto
- **Flujo:** kg rescatados, raciones, personas beneficiadas, CO2e, serie de 30 días, por municipio, por alimento, ranking de
  donantes e indicadores de proceso; se puede ocultar el historial simulado.
- **Dónde:** *Impacto* · `GET /api/impacto` · `tests/test_impacto.py`.

### CU-10 Consultar el reporte de un donante
- **Flujo:** totales y lista de rescates de un donante (versión en pantalla del reporte mensual; sin PDF).
- **Dónde:** *Impacto* → “Reporte para donantes” · `GET /api/impacto/donantes/{id}`.

### CU-11 Registrar y verificar un receptor
- **Flujo:** un receptor nuevo (alta por API) nace **sin verificar** y no recibe ofertas; el administrador lo verifica.
- **Limitación:** no hay formulario de alta en la interfaz.
- **Dónde:** *Admin* → “Receptores por verificar” · `POST /api/receptores`, `POST /api/receptores/{id}/verificacion`.

### CU-12 Atender una donación atorada
- **Flujo:** si no hay receptor o voluntario viable, el administrador ve la donación, resuelve la causa (p. ej. verifica un
  receptor) y pulsa “Reintentar”.
- **Dónde:** *Admin* → “Donaciones atoradas” · `POST /api/donaciones/{id}/reintento` · `tests/test_orquestador.py`.

### CU-13 Cancelar por caducidad
- **Flujo:** si pasa la fecha de caducidad antes de completarse, el sistema cancela ofertas y recolecciones pendientes y avisa al donante.
- **Dónde:** automático al consultar · `tests/test_orquestador.py::TestCaducidadYTransicionesInvalidas`.
