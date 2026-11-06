# Entrega del MVP

## Los tres entregables

| # | Entregable | Estado | Dónde |
|---|---|---|---|
| 1 | Video de la demo con el proyecto funcionando | ⏳ **Por grabar** | Instrucciones en [`GUION_VIDEO.md`](GUION_VIDEO.md) |
| 2 | Entrada de texto describiendo el entregable |  ✅ Borrador abajo | Sección siguiente |
| 3 | Liga al Git con código y documentación | ✅ | <https://github.com/angelbarbarin/comparte> |

## Entrada de texto (lista para pegar)

> **ComParte — MVP de la plataforma agéntica de rescate de alimentos (ODS 2: Hambre cero)**
>
> Entregamos la primera versión funcional de ComParte, construida a partir del Documento de Visión y Alcances. Un negocio donante
> reporta su excedente por chat y un sistema de cuatro agentes, coordinados por un orquestador, lo lleva hasta el receptor que más
> lo necesita, organiza quién lo recoge y mide el impacto, con supervisión humana en las decisiones sensibles.
>
> **Funcionalidad entregada**
> - **Agente Captador:** conversa en español coloquial (texto y foto), estructura la donación, pregunta lo que falta, aplica reglas de
>   inocuidad (bloquea alcohol, producto caducado, mal estado o cadena de frío rota) y pide confirmación antes de registrar.
> - **Agente Coordinador:** elige al receptor con un puntaje explicable (necesidad, cercanía, margen de caducidad, capacidad y equidad),
>   registra por qué descartó a cada uno y reasigna si el receptor rechaza o no responde.
> - **Agente Logístico:** elige al voluntario con la ruta más corta que cumpla capacidad del vehículo, hielera, horarios y caducidad, y
>   da seguimiento hasta la entrega.
> - **Agente de Impacto:** calcula kg rescatados, raciones, personas beneficiadas y CO2e evitado; tablero y reporte por donante.
> - **Orquestador y supervisión humana:** enruta entre agentes; los alimentos de riesgo (carnes, lácteos, comida preparada) esperan la
>   aprobación de una persona; toda decisión queda en una bitácora de auditoría visible como línea de tiempo.
> - **Interfaz web:** chat del donante, seguimiento con mapa, consolas de receptor y voluntario, tablero de impacto y panel de administración.
> - **Piloto simulado del AMG:** 10 donantes, 6 receptores, 6 voluntarios y 40 rescates históricos (rotulados como simulados).
>
> **Métricas definidas** (retroalimentación del profesor): kg rescatados; raciones (kg ÷ 0.5); personas beneficiadas (raciones ÷ 3, personas
> alimentadas un día completo); y CO2e evitado. Son supuestos editables y quedan pendientes de validar con un banco de alimentos real.
>
> **Retroalimentación atendida:** canal web como plan B ante el costo de WhatsApp Business; métricas de impacto; y agentes y orquestador
> claramente separados y visibles. Pendientes: validar el flujo con un banco de alimentos real y estimar el costo de WhatsApp.
>
> **Calidad y límites:** 244 pruebas automáticas (sin red ni claves). En un conjunto de mensajes escritos por nosotros, el Captador con reglas
> logra 85 % de precisión en mensajes no vistos durante su ajuste (90 % tras corregir un error que reveló), contra la meta de 90 %. El modo con
> Claude (visión) está implementado pero aún no se probó con la API real; no hay autenticación; las rutas son estimadas; los datos son simulados.
>
> **Siguientes pasos hasta el 24 de noviembre:** diagramas UML, video con todos los casos de uso, validación con un banco de alimentos,
> costo de WhatsApp, prueba con Claude real y autenticación por roles.
>
> **Video:** `VIDEO_URL` · **Código y documentación:** <https://github.com/angelbarbarin/comparte>

## Enlaces

- **Repositorio (código y documentación):** <https://github.com/angelbarbarin/comparte>
- **Video de la demo:** `VIDEO_URL` (pendiente de grabar)

## Lista de verificación antes de entregar

- [ ] `pytest` pasa en limpio y el README funciona siguiendo solo sus instrucciones (pruébenlo en otra computadora o carpeta).
- [ ] El video muestra el recorrido de [`GUION_VIDEO.md`](GUION_VIDEO.md) y abre en una ventana de incógnito.
- [ ] La entrada de texto tiene las ligas reales (sustituyan `VIDEO_URL` por la liga real del video).
- [ ] El repositorio es accesible para el profesor (público, o privado con acceso concedido).
- [ ] No hay claves, `.env` ni datos personales en el historial de git (`git log -p | findstr /i "sk-ant-"` no debe encontrar nada).

## Preguntas probables y respuestas honestas

| Pregunta | Respuesta |
|---|---|
| ¿Funciona con WhatsApp? | No. El canal es web (plan B por costo). El orquestador es independiente del canal; WhatsApp es un adaptador pendiente |
| ¿Usa un LLM de verdad? | El Captador tiene dos motores: reglas (por defecto, para demo y pruebas) y Claude con visión. El de Claude está implementado y probado con un cliente simulado, **no contra la API real** |
| ¿Los datos son reales? | No: donantes, receptores y voluntarios son ficticios; el historial del tablero es simulado y está rotulado |
| ¿Por qué esas métricas? | Las pidió la retroalimentación. Sus factores (0.5 kg por ración, 3 raciones por persona al día, factores de CO2e) son supuestos documentados y editables |
| ¿Es seguro para producción? | No todavía: sin autenticación, sin cifrado propio y sin despliegue. Las reglas de inocuidad son heurísticas, no una certificación sanitaria |
| ¿Qué tan bien entiende el español? | Ver la medición en `docs/ALCANCE_MVP.md`: 85–90 % en mensajes escritos por el equipo; los fallos conocidos son alimentos fuera del catálogo |
