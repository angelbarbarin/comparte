# Cómo trabajar en ComParte (equipo de 3)

## Flujo de trabajo

1. `main` siempre debe estar verde: `pytest` pasa y la demo arranca.
2. Una rama por tarea: `feat/<area>-<tema>`, `fix/<area>-<tema>`, `docs/<tema>` (ej. `feat/logistico-api-mapas`).
3. Abre un *pull request* a `main` y pide revisión a otra persona del equipo. Quien revisa corre `pytest` y, si
   el cambio toca la interfaz, la prueba en el navegador.
4. Haz *squash* o deja los commits limpios; no mezcles tareas en un mismo PR.

```bash
git switch -c feat/captador-mas-alimentos
# ... trabajar, probar ...
git add -p && git commit
git push -u origin feat/captador-mas-alimentos
```

## Mensajes de commit

Formato: `tipo(área): resumen en imperativo` y un cuerpo que explique **qué cambió y por qué**.

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`. Áreas: `captador`, `coordinador`, `logistico`,
`impacto`, `orquestador`, `api`, `web`, `datos`, `conocimiento`, `llm`.

## Convenciones del código

- El **dominio va en español** (Donante, Receptor, Voluntario, Donacion, Oferta, Recoleccion) para que el código
  coincida con los diagramas UML y el documento de visión. La infraestructura (`config`, `db`, `api`) usa nombres
  convencionales.
- **Cada agente es un módulo independiente** y solo el orquestador los conecta. Si un agente necesita algo de otro,
  pásalo por el orquestador, no importes un agente desde otro.
- **Toda decisión de un agente deja un evento** con `registrar_evento(...)`: es la bitácora de auditoría.
- La hora siempre sale de `reloj.ahora()`, nunca de `datetime.now()` (así se puede congelar en pruebas y fijar en la demo).
- Para leer colecciones relacionadas (ofertas de una donación, mensajes de una conversación) **consulta con `select`**,
  no uses las listas del ORM: pueden estar desactualizadas dentro de la misma sesión (nos mordió dos veces).
- En el frontend nunca uses `innerHTML` con datos; usa `el(...)` y `llenar(...)` de `web/js/util.js`.

## Antes de abrir un PR

```bash
pytest                              # todo debe pasar
python scripts/evaluar_captador.py  # si tocaste el motor de reglas o el catálogo: la precisión no debe bajar
```

Si tocaste la interfaz: arranca `scripts/demo.ps1` y recorre las pestañas afectadas.

## Recetas comunes

| Quiero... | Toca... |
|---|---|
| Que el Captador reconozca un alimento nuevo | `comparte/conocimiento/catalogo.py` (sinónimos) + factor en `factores_impacto.py` + un caso en `tests/data/mensajes_captador.json` |
| Cambiar cómo puntúa el Coordinador | `PESOS` y constantes de `comparte/agentes/coordinador.py` (la interfaz lee los pesos de `/api/estado`) |
| Cambiar una regla de inocuidad | `comparte/conocimiento/inocuidad.py` y sus pruebas |
| Cambiar métricas de impacto | `comparte/conocimiento/factores_impacto.py` y `docs/ALCANCE_MVP.md` (sección 4) |
| Agregar un endpoint | `comparte/api/rutas.py` + serializador en `esquemas.py` + prueba en `tests/test_api.py` |
| Agregar una pestaña | `web/js/vistas/<nombre>.js` (copia `admin.js`) + registrarla en `web/js/app.js` y `web/index.html` |
| Conectar WhatsApp | Un adaptador nuevo que llame a `Orquestador.mensaje_donante(...)` (ver `docs/PLAN_EQUIPO.md`) |

## Secretos

Nunca subas claves. `.env` está ignorado; copia `.env.example` y rellénalo localmente.
