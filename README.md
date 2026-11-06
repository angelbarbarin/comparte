# ComParte

**Plataforma agéntica de rescate de alimentos** para el Área Metropolitana de Guadalajara (AMG).
Conecta el excedente de panaderías, supermercados, mercados y cocinas con bancos de alimentos, comedores y
albergues que lo necesitan, antes de que caduque. Proyecto del Hackathon de Desarrollo Sustentable de la
materia *Diseño de Software* (ITESO, otoño 2026) · **ODS 2: Hambre cero** (secundarios: ODS 12 y 13).

> **Estado: MVP (versión 0.1).** Recorre de punta a punta el ciclo completo con datos de prueba:
> donante → Captador → (revisión humana si hay riesgo) → Coordinador → Logístico → Impacto.
> Lo que sí hace y lo que **no** hace está en [`docs/ALCANCE_MVP.md`](docs/ALCANCE_MVP.md).

## Cómo funciona

Cuatro agentes especializados coordinados por un orquestador, con supervisión humana en las decisiones sensibles:

| Agente | Qué hace | Código |
|---|---|---|
| **Captador** | Conversa con el donante (texto y foto), estructura la donación y aplica reglas de inocuidad | [`comparte/agentes/captador.py`](comparte/agentes/captador.py) |
| **Coordinador** | Elige al receptor óptimo con un puntaje explicable (necesidad, cercanía, caducidad, capacidad, equidad) y reasigna si rechaza o no responde | [`comparte/agentes/coordinador.py`](comparte/agentes/coordinador.py) |
| **Logístico** | Elige voluntario, calcula la ruta y da seguimiento hasta la entrega | [`comparte/agentes/logistico.py`](comparte/agentes/logistico.py) |
| **Impacto** | Calcula kg rescatados, raciones, personas beneficiadas y CO2e evitado | [`comparte/agentes/impacto.py`](comparte/agentes/impacto.py) |
| **Orquestador** | Enruta entre los agentes, pide revisión humana y registra cada decisión | [`comparte/orquestador.py`](comparte/orquestador.py) |

Cada decisión queda en una **bitácora de auditoría** y la interfaz la muestra como línea de tiempo, junto con el
desglose del puntaje y los motivos de cada descarte. Diagramas y decisiones de diseño en
[`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

El canal principal es un **chat web** (plan B ante el costo de la API de WhatsApp Business). El orquestador no
depende del canal, así que WhatsApp se agrega después como un adaptador.

## Probarlo en 3 comandos

Requisitos: Python 3.11 o superior (probado con 3.13). Funciona **sin internet y sin claves de API**; con
internet se ven además los mosaicos del mapa.

**Windows (PowerShell)**

```powershell
.\scripts\demo.ps1
```

**macOS / Linux**

```bash
./scripts/demo.sh
```

Abre <http://127.0.0.1:8000>. El script crea el entorno virtual, instala dependencias, recarga los datos de
prueba, fija la hora de la aplicación a las 16:00 (para que la demo no dependa de la hora real) y arranca el
servidor. Para ver el recorrido paso a paso sigue [`docs/GUION_VIDEO.md`](docs/GUION_VIDEO.md).

<details>
<summary>Instalación manual</summary>

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m comparte servir --hora-demo 16:00 --reiniciar
```

Si tu carpeta está dentro de OneDrive, crea el entorno virtual fuera (por ejemplo en `%USERPROFILE%\.venvs\comparte`)
para no sincronizar miles de archivos.
</details>

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest                                   # 244 pruebas, ~25 s, sin red ni claves
python scripts/evaluar_captador.py       # precisión del Captador sobre mensajes etiquetados
```

## Motor de lenguaje del Captador

| Modo | Cómo activarlo | Cuándo |
|---|---|---|
| **Reglas** (defecto) | no hacer nada | Demo, pruebas y desarrollo: gratis, determinista, sin internet |
| **Claude** (con visión) | definir `ANTHROPIC_API_KEY` (ver [`.env.example`](.env.example)) | Entiende lenguaje más libre y **lee la foto** del excedente. Si falla la red, cae al motor de reglas |

> ⚠️ El modo Claude está implementado y probado con un cliente simulado, pero **no se ha ejecutado contra la API
> real** (no había clave durante la construcción). La primera tarea con una clave es correr
> `python scripts/evaluar_captador.py --motor claude`.

## Estructura

```
comparte/            backend (Python / FastAPI / SQLAlchemy)
  agentes/           captador, coordinador, logistico, impacto
  orquestador.py     enruta entre agentes y pide revisión humana
  llm/               motores de lenguaje: reglas y Claude
  conocimiento/      catálogo de alimentos, reglas de inocuidad, factores de impacto
  api/               rutas REST (/api) y serialización
  modelos.py         modelo de dominio (Donante, Receptor, Voluntario, Donacion, Oferta, ...)
  datos_demo.py      piloto simulado del AMG
web/                 interfaz estática (HTML + CSS + JS modular, sin compilación)
tests/               pruebas (pytest)
docs/                alcance, arquitectura, guion del video, plan del equipo, entrega
scripts/             arranque de la demo y evaluación del Captador
```

## Documentación

- [`docs/ALCANCE_MVP.md`](docs/ALCANCE_MVP.md): qué entra, hasta dónde llega, métricas y limitaciones.
- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md): componentes, estados, secuencias y clases (borradores de los UML).
- [`docs/GUION_VIDEO.md`](docs/GUION_VIDEO.md): instrucciones para grabar el video de la demo.
- [`docs/ENTREGA.md`](docs/ENTREGA.md): texto de la entrega y lista de verificación.
- [`docs/PLAN_EQUIPO.md`](docs/PLAN_EQUIPO.md): pendientes hasta el 24 de noviembre y cómo repartirlos.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): cómo trabajar en equipo en este repositorio.
- [`docs/Vision_y_Alcances_ComParte.docx`](docs/Vision_y_Alcances_ComParte.docx): documento de visión y alcances (origen de todos los requisitos).

## Datos y supuestos

Los donantes, receptores y voluntarios del piloto son **ficticios** (con coordenadas aproximadas de colonias
reales del AMG). El historial de rescates del tablero es **simulado** y está rotulado como tal. Los factores de
raciones, personas y CO2e son supuestos por validar ([`comparte/conocimiento/factores_impacto.py`](comparte/conocimiento/factores_impacto.py)).
Las reglas de inocuidad son heurísticas del equipo, **no una certificación sanitaria**.

## Equipo y licencia

Diego Alejandro Álvarez Hernández · Angel Isaac Barbarín Cuevas · Diego Valerio.
Código abierto bajo licencia [MIT](LICENSE).
