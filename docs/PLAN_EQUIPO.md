# Plan del equipo hasta el 24 de noviembre

Este documento convierte lo que **falta** (ver [`ALCANCE_MVP.md`](ALCANCE_MVP.md), secciones 3 y 6, y la retroalimentación del
profesor) en tareas repartibles entre tres personas. El reparto en **pistas A, B y C** es una sugerencia: decidan quién toma
cuál según sus gustos y su disponibilidad.

## Cómo empezar mañana (30 minutos)

1. Cada quien clona el repositorio y corre la demo: `.\scripts\demo.ps1` (o `./scripts/demo.sh`).
2. Cada quien corre las pruebas: `pip install -r requirements-dev.txt` y `pytest`.
3. Recorran juntos el guion de [`GUION_VIDEO.md`](GUION_VIDEO.md) una vez para que todos conozcan el sistema.
4. Lean [`ARQUITECTURA.md`](ARQUITECTURA.md) y [`CONTRIBUTING.md`](../CONTRIBUTING.md) (flujo de ramas y convenciones).
5. Conviertan las tareas de abajo en *issues* del repositorio (una por fila) y asígnenlas.

## Reparto sugerido

| Pista | Foco | Tareas |
|---|---|---|
| **A · Backend y agentes** | Código de agentes, IA, datos, despliegue | A1–A8 |
| **B · Interfaz, usabilidad y video** | Frontend, pruebas con personas, grabación | B1–B6 |
| **C · Diseño, validación y negocio** | UML, banco de alimentos real, costos, documentos | C1–C7 |

## Backlog

Tamaños: **S** ≈ medio día · **M** ≈ 1–2 días · **L** ≈ 3 o más días. “Hecho cuando” es el criterio de aceptación.

### Pista A · Backend y agentes

| ID | Tarea | Tam. | Hecho cuando |
|---|---|---|---|
| A1 | **Probar el modo Claude con una clave real** (`python scripts/evaluar_captador.py --motor claude`), comparar `claude-opus-5-5` con `claude-haiku-5-5` en precisión, latencia y costo | S | Hay un informe en `docs/` con las tres métricas; el lote B ≥ 90 %; si falla algo, corregido. **Prioridad máxima: es lo único que el MVP no pudo verificar** |
| A2 | Ampliar el catálogo y las reglas con lo que digan los donantes/banco reales (empanadas, totopos…) | S | Los casos fallidos del lote B pasan y no baja la precisión del lote A |
| A3 | **Autenticación y roles** (donante, receptor, voluntario, administrador): sesión simple, endpoints protegidos | M | Un receptor no puede responder ofertas de otro; `test_api.py` cubre 401/403 |
| A4 | PostgreSQL + Docker (`docker compose up`) y migraciones (Alembic) | M | La app corre con PostgreSQL y las pruebas siguen pasando con SQLite |
| A5 | Rutas reales (OSRM o API de mapas) detrás de `geo.py` | M | Distancias y ETA salen del servicio; hay respaldo a la estimación actual si falla |
| A6 | Planificador en segundo plano para `Orquestador.tick()` | S | Las ofertas expiran sin que nadie consulte la API |
| A7 | Dividir una donación entre varios receptores cuando ninguno tiene capacidad total | M | Prueba: 150 kg se reparten entre dos receptores |
| A8 | **Adaptador de WhatsApp** (webhook → `Orquestador.mensaje_donante`, avisos de salida) **solo si C3 lo justifica** | L | Una conversación completa por WhatsApp (entorno de pruebas de Meta) |

### Pista B · Interfaz, usabilidad y video

| ID | Tarea | Tam. | Hecho cuando |
|---|---|---|---|
| B1 | **Prueba de usabilidad** con 3 personas ajenas al equipo: donar sin ayuda | S | Se mide el tiempo de registro (meta ≤ 1 min) y se anotan los tropiezos en `docs/` |
| B2 | Formulario de **alta de receptor** en la interfaz (CP-03 completo) | S | Un administrador da de alta y verifica un receptor sin tocar la API |
| B3 | Auditoría de accesibilidad WCAG 2.1 AA (Lighthouse/axe) y correcciones | S | Sin errores críticos; contrastes y foco revisados |
| B4 | Pruebas de extremo a extremo de la interfaz (Playwright) del recorrido feliz | M | Una prueba automatizada recorre Donar → Receptor → Voluntario → Impacto |
| B5 | **Video final con todos los casos de uso** (usar [`CASOS_DE_USO.md`](CASOS_DE_USO.md)) | M | Muestra CU-01 a CU-13 y dura ≤ 10 min |
| B6 | Pulido: estados de carga, errores amigables, textos | S | Revisión cruzada sin pendientes |

### Pista C · Diseño, validación y negocio

| ID | Tarea | Tam. | Hecho cuando |
|---|---|---|---|
| C1 | **Diagramas UML** (casos de uso, componentes, clases y secuencias), a partir de [`ARQUITECTURA.md`](ARQUITECTURA.md) y [`CASOS_DE_USO.md`](CASOS_DE_USO.md) | M | Cuatro diagramas exportados a `docs/uml/`; en el de componentes se ven los **cuatro agentes y el orquestador** (pedido del profesor) |
| C2 | **Validar el flujo con un banco de alimentos real del AMG** (30 min de entrevista, ver preguntas abajo) | M | `docs/VALIDACION.md` con hallazgos; ajustes a necesidades, reglas de inocuidad y factores |
| C3 | **Estimar el costo de la API de WhatsApp Business** (Don Inversionista) con las tarifas vigentes de Meta para México y el volumen de 500 donaciones/día | S | Tabla de costo mensual y recomendación (web vs. WhatsApp) |
| C4 | Verificar los **factores de CO2e** y de raciones contra sus fuentes | S | Cada factor cita su fuente y fecha en `factores_impacto.py` |
| C5 | Manual breve de uso para donantes, receptores y voluntarios (sección 9.5 del documento de visión) | S | Una página por rol con capturas |
| C6 | Documentación técnica final y README revisados por alguien que no los escribió | S | Otra persona instala y corre todo solo con el README |
| C7 | Presentación final | M | Diapositivas ensayadas |

## Calendario sugerido

| Fechas | Meta | Tareas |
|---|---|---|
| **9–12 nov** | Quitar incertidumbres | A1, C3, C4; contactar al banco de alimentos (C2); empezar C1 |
| **13–17 nov** | Cerrar funcionalidad | A2, A3 (mínimo), B1, B2, C2 realizada, borrador de C1 |
| **18–20 nov** | Calidad | A6, B3, B4, C5; **congelar funcionalidades el 20** |
| **21–22 nov** | Entregables | C1 final, B5 (grabar), C6 |
| **23–24 nov** | Ensayo y entrega | C7, revisión cruzada, subir todo |

## Preguntas para el banco de alimentos (C2)

1. ¿Cómo reciben hoy las donaciones pequeñas o de último momento? ¿Qué los hace rechazarlas?
2. ¿Qué alimentos aceptan y cuáles nunca? ¿Qué exigen de cadena de frío y de caducidad? (compara con `conocimiento/inocuidad.py`)
3. ¿Cuántos kg al día pueden recibir y almacenar, con y sin refrigeración?
4. ¿Cuánto tardan en responder una oferta? (¿15 min es razonable?) ¿Por qué canal (WhatsApp, llamada)?
5. ¿Cómo estiman raciones y personas beneficiadas? (compara con 0.5 kg por ración y 3 raciones por persona al día)
6. ¿Qué los haría desconfiar de un sistema automático? ¿Qué decisiones querrían aprobar ellos?
7. ¿Cuentan con voluntarios y vehículos propios? ¿Cómo coordinan hoy las recolecciones?

## Riesgos y cómo manejarlos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| El modo Claude falla o cuesta más de lo esperado | Media | A1 va primero; si no sirve, la demo final sigue con el motor de reglas (ya funciona) y se documenta |
| No consiguen al banco de alimentos a tiempo | Media | Contactar el **9 de noviembre**; si no, validar con un comedor comunitario o con una entrevista a una persona que haya trabajado en uno, y decirlo |
| WhatsApp resulta caro o lento de aprobar | Alta | C3 decide pronto; el plan B web ya está cubierto y es lo que se presenta |
| El video queda largo o con errores | Media | Grabar por escenas, ensayar, usar el botón de reinicio de datos |
| Se acumulan cambios sin probar cerca de la entrega | Media | Congelar funcionalidades el 20 de nov; PRs pequeños; CI en cada PR |

## Deuda técnica conocida

- Sin autenticación (A3) · sin planificador (A6) · una donación = un receptor (A7) · distancias estimadas (A5).
- Las colecciones del ORM pueden quedar desactualizadas dentro de una sesión: usar `select` (ya nos costó dos errores).
- La interfaz no tiene pruebas automáticas (B4).
- El historial simulado usa los mismos factores que el resto: si cambian, hay que reiniciar los datos de demo.
