# Guion e instrucciones para grabar el video de la demo

Duración objetivo: **8 minutos** (máximo 10). Una sola persona puede grabarlo; si son varias, repartan las escenas.
Todo lo que se hace en pantalla y los resultados esperados fueron **verificados contra la aplicación real** (hora de demo
16:00 y datos recién cargados). Lo único que puede variar es el número de la donación (#41 con historial simulado, #1 sin él).

## 0. Qué pide la entrega y qué cubre este video

La entrega tiene tres partes: **(1)** video de la demo describiendo la funcionalidad entregada, **(2)** entrada de texto
([`ENTREGA.md`](ENTREGA.md)) y **(3)** liga al Git con código y documentación. Este video cubre el (1).

Para el video **final del 24 de noviembre** (todos los casos de uso) usen [`CASOS_DE_USO.md`](CASOS_DE_USO.md) como lista de
verificación; este guion ya recorre CU-01, 03, 04, 05, 06, 07, 08, 09, 12 y 13 (parcial).

## 1. Antes de grabar (20 minutos)

**Checklist**

- [ ] Estás en la última versión de `main` (`git pull`) y `pytest` pasa.
- [ ] Cerraste correo, chats y cualquier notificación (modo *No molestar* / Asistente de concentración).
- [ ] Navegador en pantalla completa (F11), zoom 100 % o 110 %, sin barra de marcadores ni extensiones visibles.
- [ ] Resolución 1920×1080. Micrófono probado (graba 10 segundos y escúchalos).
- [ ] Tienes internet (para que se vean los mosaicos del mapa; si no, ver la sección 5).

**Arranque limpio** (cada vez que repitas la grabación completa):

```powershell
.\scripts\demo.ps1
```

Abre <http://127.0.0.1:8000> en el navegador. Verifica arriba a la derecha: *Motor de lenguaje: reglas*, *Hora de demo: 16:00*
y *Datos de demostración*. Si algo quedó a medias, en **Admin → Reiniciar datos de demo** vuelve todo al inicio (y F5 en el navegador).

**Cómo grabar en Windows:** Xbox Game Bar (`Win + G` → botón de grabar; el atajo `Win + Alt + R` inicia y detiene) o
[OBS Studio](https://obsproject.com/) (gratis; fuente *Captura de pantalla* + *Captura de audio de entrada*). Graba cada
escena por separado: si te equivocas solo repites esa. Para unir las escenas sirve *Clipchamp* (incluido en Windows 11).

**Haz una prueba en seco completa antes de grabar de verdad.**

## 2. Estructura y tiempos

| # | Escena | Pestaña | Tiempo | Casos de uso |
|---|---|---|---|---|
| 0 | Introducción: problema y solución | (diapositiva o la pestaña Donar) | 0:45 | — |
| 1 | Un donante registra su excedente por chat | Donar | 1:15 | CU-01 |
| 2 | Cómo decidieron los agentes | Seguimiento | 1:15 | CU-08 |
| 3 | El receptor rechaza y el sistema reasigna | Receptor / Seguimiento | 0:45 | CU-04, CU-05 |
| 4 | El voluntario recoge y entrega | Voluntario | 0:50 | CU-06 |
| 5 | El receptor confirma y se mide el impacto | Receptor / Impacto / Donar | 1:00 | CU-07, CU-09 |
| 6 | Alimento de riesgo, revisión humana y tiempo | Donar / Admin / Seguimiento | 1:30 | CU-01, CU-03, CU-05, CU-13 |
| 7 | Un alimento que no se acepta | Donar | 0:20 | CU-01 |
| 8 | Cierre: lo que hay, lo que falta | (diapositiva) | 0:40 | — |

## 3. Guion escena por escena

> Los textos de **Decir** son sugerencias; háganlos suyos. Lo importante es que se vea lo descrito en **Debe verse**.

### Escena 0 · Introducción (0:45)

**Mostrar:** una diapositiva con el logo, el nombre del equipo y "ODS 2: Hambre cero" (o la pestaña *Donar*).

**Decir:**
> "En México se desperdician millones de toneladas de alimentos mientras casi 1 de cada 5 personas tiene carencia por acceso
> a la alimentación. Mucho excedente sale de panaderías, mercados y cocinas dispuestas a donar, pero coordinarlo a mano es
> lento. ComParte es un sistema de agentes de IA que recibe la donación por chat, elige al receptor que más la necesita,
> organiza quién la recoge y mide el impacto. Les mostramos el MVP funcionando con datos de prueba del Área Metropolitana
> de Guadalajara. Usamos un chat web como canal principal; WhatsApp es la siguiente fase."

### Escena 1 · Registrar una donación por chat (1:15)

**Hacer:**
1. Pestaña **Donar**. El donante por defecto es *Panadería La Espiga · Tlaquepaque*.
2. Pulsa el ejemplo **“Pan del día y fruta”** (llena el mensaje: *Tengo 25 kg de pan dulce del día y 10 kg de fruta madura,
   pueden pasar después de las 5 pm*) y **Enviar**.
3. El Captador responde con un resumen. Léelo en voz alta.
4. Escribe **sí** y Enter.

**Debe verse:**
- Resumen: `25 kg de pan dulce`, `10 kg de fruta`, `Total: 35 kg`, `Caduca: hoy 23:59`, `Recolección: hoy 17:00 a 20:00`, y “¿Lo confirmo?”.
- Tras el “sí”: *“¡Listo! Registré tu donación #41 (35 kg)…”* y un mensaje del **Agente Coordinador**: *“Ofrecí tu donación a
  Comedor Comunitario Santa Cecilia (91/100)…”*. A la derecha, el panel **Tu donación** con su avance.

> 💡 **Ojo con el tiempo:** el tablero mide cuánto tardó el registro, desde tu primer mensaje hasta el “sí”. Si te detienes a
> narrar mucho entre los dos mensajes, en la escena 5 el indicador *Registrar una donación* marcará “No cumple” (la meta es ≤ 60 s).
> Es honesto y no es un error, pero si quieres que se vea el caso feliz, narra el resumen **después** de confirmar o repite la escena.

**Decir:**
> "Escribimos como hablaría un encargado de panadería, sin formularios. El Agente Captador entiende cantidades, la caducidad
> y el horario, y nos pide confirmar antes de registrar. En dos mensajes quedó registrada, y el Coordinador ya la ofreció al
> receptor que mejor la aprovecha."

### Escena 2 · Cómo decidieron los agentes (1:15)

**Hacer:** pestaña **Seguimiento** (se selecciona la donación). Recorre de arriba abajo, despacio:
1. Los **pasos** de progreso (Registrada → Receptor → …).
2. El **mapa** (donante naranja, receptor verde).
3. **“Cómo eligió al receptor”**: la tabla con el puntaje y las barras de colores.
4. **“Línea de tiempo de los agentes”** (abajo).

**Debe verse:** en la tabla, receptores *Viables* con su puntaje (Santa Cecilia ≈ 91, Banco de Alimentos ≈ 90…) y *Descartados*
con su motivo (por ejemplo *Comedor Los Pinos: cerrado al llegar (cierra a las 18:00)* y *Centro Comunitario Nuevo Sol: organización
sin verificar*). En la línea de tiempo: Captador → Orquestador → Coordinador.

**Decir:**
> "Aquí está lo que más nos importa: las decisiones no son una caja negra. El puntaje combina necesidad, cercanía, margen de
> caducidad, capacidad y equidad; cada receptor descartado queda con su motivo. La equidad evita favorecer siempre al mismo.
> Y esta línea de tiempo es la bitácora de auditoría: se ve qué agente decidió qué y cuándo intervino el orquestador."

### Escena 3 · El receptor rechaza y se reasigna (0:45)

**Hacer:**
1. Pestaña **Receptor** → Organización **Comedor Comunitario Santa Cecilia**. Aparece la oferta con cuenta regresiva.
2. En “Si no puedes” deja **Sin espacio hoy** y pulsa **Rechazar**.
3. Vuelve a **Seguimiento**: la oferta se reasignó (ahora a **Banco de Alimentos Nueva Esperanza**, ≈ 90).
4. Pestaña **Receptor** → cambia la organización a **Banco de Alimentos Nueva Esperanza** y pulsa **Aceptar**.

**Decir:**
> "El receptor puede rechazar con un motivo, o simplemente no responder; en ambos casos el Coordinador reasigna al siguiente
> mejor. Ahora lo acepta el Banco de Alimentos y el Agente Logístico busca quién la recoja."

### Escena 4 · El voluntario recoge y entrega (0:50)

**Hacer:**
1. Pestaña **Voluntario** → **Mariana López · auto** (es la propuesta; si en Seguimiento aparece otro voluntario como “propuesta”, elige ese).
2. Muestra la propuesta (ruta, km, horarios) y pulsa **Aceptar recolección**.
3. Pulsa **Ya recogí con el donante** y después **Ya entregué en el receptor**.

**Debe verse:** ruta ≈ 11.7 km, “Recoges hacia las 17:00 y entregas hacia las 17:14”. Los avisos verdes en pantalla.

**Decir:**
> "El Logístico elige al voluntario con la ruta más corta que cumpla las reglas: capacidad del vehículo, horario, hielera si hace
> falta frío y que llegue antes de que caduque o cierre el receptor. Los voluntarios son simulados en este MVP."

### Escena 5 · Confirmación e impacto (1:00)

**Hacer:**
1. Pestaña **Receptor** (Banco de Alimentos) → “Por confirmar recepción”: cambia los kilos a **33** y **Confirmar recepción**.
2. Pestaña **Impacto**: muestra las tarjetas, la gráfica y los **indicadores de proceso**.
3. Pestaña **Donar**: baja al final del chat para mostrar la **constancia** del Agente de Impacto.

**Debe verse:** Impacto → incluye el rescate (en “Indicadores de proceso (sesión real)”: *1/1 completados*, *Registrar una donación: Cumple*;
la *aceptación a la 1.ª oferta* será 0 % porque se rechazó la primera, y eso está bien). En el chat: *“¡Rescate completado!… 33 kg
rescatados · 66 raciones · ≈22 personas… 45 kg de CO2e evitados”*.

**Decir:**
> "El receptor confirma lo que realmente recibió, y el Agente de Impacto lo convierte en métricas: kilos rescatados, raciones,
> personas beneficiadas y CO2e evitado. Los supuestos —media ración por kilo, tres raciones por persona al día— están a la vista
> y los vamos a validar con un banco de alimentos real. El historial de las barras es simulado y está rotulado como tal. El
> donante recibe su constancia en el mismo chat."

### Escena 6 · Alimento de riesgo, supervisión humana y tiempo (1:30)

**Hacer:**
1. Pestaña **Donar** → donante **Hotel Plaza Real (cocina) · Guadalajara**. Pulsa el ejemplo **“Pollo y leche (riesgo)”** → Enviar.
2. El Captador pregunta por la cadena de frío → escribe **sí**. Ve el resumen (con ⚠ “una persona del equipo lo revisará”) → escribe **sí**.
3. Pestaña **Admin** → “Alimentos de riesgo por validar”: muestra los motivos y pulsa **Aprobar** (nota opcional: “Viene en hielera”).
4. Pestaña **Seguimiento** → en la tabla del Coordinador: solo receptores con refrigeración son viables.
5. De vuelta en **Admin**, pulsa **Adelantar 16 min** y regresa a **Seguimiento**: la oferta *expiró* y se reasignó.

**Debe verse:** primera oferta a **Albergue Casa del Camino** (≈ 84); descartados: *Comedor Comunitario Santa Cecilia: sin refrigeración*,
*Casa Hogar Semillas: capacidad insuficiente (le quedan 15 kg hoy)*. Tras adelantar el reloj, la oferta pasa a **Banco de Alimentos Nueva
Esperanza** (≈ 83) y en la línea de tiempo aparece “no respondió en 15 min; reasigno la donación”.

**Decir:**
> "Cuando hay carne o lácteos, el agente pregunta por la cadena de frío y ninguna decisión sensible se ejecuta sin una persona:
> la donación espera en la cola de validación y nadie recibe ofertas hasta que se aprueba. Ya aprobada, solo califican receptores
> con refrigeración y capacidad. Y si el receptor no contesta en 15 minutos —adelantamos el reloj para mostrarlo— el sistema
> reasigna solo."

### Escena 7 · Un alimento que no se acepta (0:20)

**Hacer:** pestaña **Donar** (cualquier donante), ejemplo **“Alimento no aceptado”** → Enviar.

**Debe verse:** *“No puedo registrar esta donación: ‘cerveza’ no se acepta: ComParte no gestiona alcohol, medicamentos ni tabaco.”*

**Decir:** "Las reglas de inocuidad también bloquean: alcohol, producto caducado, en mal estado o con la cadena de frío rota."

### Escena 8 · Cierre (0:40)

**Decir (con una diapositiva de resumen):**
> "En resumen: cuatro agentes coordinados por un orquestador, supervisión humana en lo sensible, decisiones explicables y un
> tablero de impacto, todo en código abierto con 244 pruebas automáticas. Con honestidad: es un MVP con datos simulados; el
> modo con Claude y lectura de fotos está implementado pero aún no probado con la API real, no hay autenticación y WhatsApp,
> rutas reales y la validación con un banco de alimentos son lo que sigue antes del 24 de noviembre."

## 4. Después de grabar

- [ ] Revisa el video completo: ¿se escucha bien?, ¿se leen los textos?, ¿no aparece información personal ni notificaciones?
- [ ] Súbelo (YouTube *no listado* o la plataforma que pida el curso) y verifica que abre en una ventana de incógnito.
- [ ] Pega la liga en [`ENTREGA.md`](ENTREGA.md) y en la entrega.

## 5. Si algo sale distinto

| Problema | Qué hacer |
|---|---|
| Ofrecieron a otro receptor distinto del esperado | Es normal si cambió la hora o los datos: narra con el que aparezca y usa el que muestre **Seguimiento**. Los motivos de descarte siguen siendo visibles |
| Quedó una donación a medias o el estado se ve raro | **Admin → Reiniciar datos de demo** y F5; repite la escena |
| La hora de la aplicación ya no es 16:00 | **Admin → Fijar hora a las 16:00**. Con horas tardías casi todos los receptores cierran y la donación queda “sin receptor” |
| No cargan los mosaicos del mapa | Falta internet: se ven los puntos y las rutas sobre fondo gris. Di que los mosaicos vienen de OpenStreetMap |
| “No pude conectar con la API” | El servidor no está corriendo: vuelve a ejecutar `.\scripts\demo.ps1` |
| Puerto 8000 ocupado | `.\scripts\demo.ps1 -Puerto 8080` y abre <http://127.0.0.1:8080> |
| Un mensaje no lo entendió el agente | Usa los **ejemplos** de la pestaña Donar, que están probados |

## 6. Qué NO decir ni mostrar

- No digas que funciona con WhatsApp: el canal es web.
- No digas que se probó con Claude real: está implementado, no se ha ejecutado contra la API (sin clave). Si lo prueban antes de grabar, díganlo.
- No presentes las cifras del historial como rescates reales ni los factores de CO2e como definitivos.
- No muestres la pestaña de `/docs` ni la terminal con claves o rutas personales.

## 7. Qué mostrar para cada criterio de evaluación

| Criterio del hackathon | Dónde se ve en el video |
|---|---|
| Alineación con los ODS (ODS 2) | Escena 0 y las métricas de la escena 5 |
| Innovación (cuatro agentes + orquestador) | Escenas 2, 3, 4 y 6: cada agente aparece con su color y sus decisiones |
| Viabilidad (plan B web) | Escena 0 y 8: canal web, costo cero con el motor de reglas |
| Impacto (kg rescatados y personas beneficiadas) | Escena 5 |
| Presentación | Orden, claridad y honestidad sobre los límites (escena 8) |
