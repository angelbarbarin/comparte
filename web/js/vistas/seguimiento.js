// Vista "Seguimiento": cómo avanza cada donación y, sobre todo, POR QUÉ decidió cada agente lo que decidió.
import { el, vaciar, llenar, Pintor, chipEstado, insignia, textoItems, fmtKg, fmtHora, fmtMomento } from '../util.js';
import { pasosDe, lineaTiempo, montarMapa, pintarMapa, ajustarMapa, usarReceptores } from '../componentes.js';

const COMPONENTES = [
  ['necesidad', 'Necesidad', '#1d4f91'], ['cercania', 'Cercanía', '#6b3fb5'], ['caducidad', 'Margen de caducidad', '#b45309'],
  ['capacidad', 'Capacidad', '#17663f'], ['equidad', 'Equidad', '#a3254f'],
];

export function crear(ctx) {
  const seccion = document.getElementById('vista-seguimiento');
  const pintor = new Pintor();
  let seleccionada = null;
  let ultimoEvento = 0;

  const lista = el('ul', { class: 'lista-donaciones' });
  const detalle = el('div');
  const mapaDiv = el('div', { id: 'mapa', role: 'img', 'aria-label': 'Mapa con donante, receptor y voluntario' });
  let mapaMontado = false;

  seccion.append(el('div', { class: 'rejilla-doc' },
    el('div', { class: 'tarjeta' }, el('h2', null, 'Donaciones'), el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Las de esta sesión (sin el historial simulado).'), lista),
    detalle));

  // ----------------------------------------------------------------------------- lista
  function pintarLista(donaciones) {
    vaciar(lista);
    if (!donaciones.length) {
      lista.append(el('li', { class: 'vacio' }, 'Aún no hay donaciones. Registra una en “Donar”.'));
      return;
    }
    for (const d of donaciones) {
      lista.append(el('li', null, el('button', { type: 'button', 'aria-pressed': String(d.id === seleccionada), onclick: () => ctx.ir('seguimiento', d.id) },
        el('span', { class: 'fila espacio' }, el('b', null, `#${d.id} · ${d.donante.nombre}`)),
        el('span', { class: 'sub' }, `${textoItems(d.items)} · ${fmtKg(d.total_kg)}`),
        el('span', null, chipEstado(d.estado)))));
    }
  }

  // --------------------------------------------------------------------- decisión del Coordinador
  function tablaCoordinador(d) {
    const ev = d.evaluacion;
    if (!ev || !ev.candidatos) return el('p', { class: 'vacio' }, 'Aún no se evalúan receptores (la donación espera revisión o no ha sido asignada).');
    const pesos = ctx.estado.pesos_asignacion || {};
    const filas = ev.candidatos.map((c) => {
      const barra = el('div', { class: 'barra', role: 'img', 'aria-label': `Puntaje ${c.puntaje} de 100` },
        COMPONENTES.map(([clave, nombre, color]) => {
          const aporte = 100 * (pesos[clave] || 0) * (c.componentes[clave] || 0);
          return el('i', { style: `width:${aporte}%;background:${color}`, title: `${nombre}: ${Math.round(100 * (c.componentes[clave] || 0))} % (peso ${Math.round(100 * (pesos[clave] || 0))} %)` });
        }));
      return el('tr', { class: c.viable ? '' : 'descartado' },
        el('td', null, el('b', null, c.nombre), el('div', { class: 'meta' }, `${c.distancia_km} km · llegaría ${fmtHora(c.llegada)}`)),
        el('td', null, c.viable ? el('div', null, el('b', null, c.puntaje.toFixed(0)), ' / 100', barra) : el('span', { class: 'meta' }, `${c.puntaje.toFixed(0)} (referencia)`)),
        el('td', null, c.viable ? el('span', { class: 'chip ok' }, 'Viable') : el('div', null, el('span', { class: 'chip error' }, 'Descartado'), el('ul', { class: 'meta', style: 'margin:.3rem 0 0;padding-left:1rem' }, c.motivos_exclusion.map((m) => el('li', null, m))))));
    });
    return el('div', null,
      el('div', { class: 'tabla-envoltura' }, el('table', { class: 'tabla' },
        el('thead', null, el('tr', null, el('th', null, 'Receptor'), el('th', null, 'Puntaje'), el('th', null, 'Resultado'))),
        el('tbody', null, filas))),
      el('div', { class: 'leyenda' }, COMPONENTES.map(([clave, nombre, color]) => el('span', { style: `--color:${color}` }, `${nombre} (${Math.round(100 * (pesos[clave] || 0))} %)`))));
  }

  function bloqueOfertas(d) {
    if (!d.ofertas.length) return null;
    return el('div', { style: 'margin-top:.8rem' }, el('h4', null, 'Ofertas'),
      d.ofertas.map((o) => el('p', { class: 'sub', style: 'margin-top:.35rem' },
        el('b', null, o.receptor.nombre), ' · ', o.estado, o.motivo ? ` (${o.motivo})` : '', ' — ', o.justificacion)));
  }

  // ---------------------------------------------------------------------- decisión del Logístico
  function tablaLogistico(d) {
    const ev = [...d.eventos].reverse().find((e) => e.detalle && e.detalle.candidatos && e.agente === 'logistico');
    if (!ev) return el('p', { class: 'vacio' }, 'Aún no se busca voluntario (primero debe aceptar un receptor).');
    return el('div', { class: 'tabla-envoltura' }, el('table', { class: 'tabla' },
      el('thead', null, el('tr', null, el('th', null, 'Voluntario'), el('th', null, 'Ruta'), el('th', null, 'Resultado'))),
      el('tbody', null, ev.detalle.candidatos.map((c) => el('tr', { class: c.viable ? '' : 'descartado' },
        el('td', null, el('b', null, c.nombre)),
        el('td', null, `${c.distancia_total_km} km · ~${c.duracion_total_min} min`, el('div', { class: 'meta' }, `recoge ${fmtHora(c.recoger)} · entrega ${fmtHora(c.entrega)}`)),
        el('td', null, c.viable ? el('span', { class: 'chip ok' }, 'Viable') : el('div', null, el('span', { class: 'chip error' }, 'Descartado'),
          el('ul', { class: 'meta', style: 'margin:.3rem 0 0;padding-left:1rem' }, c.motivos_exclusion.map((m) => el('li', null, m))))))))));
  }

  // --------------------------------------------------------------------------------- detalle
  function pintarDetalle(d) {
    const ahora = ctx.ahora();
    const inoc = d.inocuidad || {};
    llenar(detalle, 
      el('div', { class: 'tarjeta' },
        el('div', { class: 'fila espacio' },
          el('h2', null, `Donación #${d.id} · ${d.donante.nombre}`), chipEstado(d.estado)),
        el('div', { class: 'rejilla-4', style: 'margin-top:.8rem' },
          dato('Alimentos', textoItems(d.items)), dato('Peso total', fmtKg(d.total_kg)),
          dato('Caduca', `${fmtMomento(d.caduca_en, ahora)}${d.caducidad_estimada ? ' (estimado)' : ''}`),
          dato('Inocuidad', `Riesgo ${inoc.nivel || '—'}${inoc.requiere_revision ? ' · revisión humana' : ''}${d.requiere_frio ? ' · frío' : ''}`),
          dato('Receptor', d.receptor ? d.receptor.nombre : '—'),
          dato('Recolección', `${fmtMomento(d.recoleccion_desde, ahora)} – ${fmtHora(d.recoleccion_hasta)}`),
          dato('Tiempo de registro', d.segundos_registro != null ? `${d.segundos_registro} s` : '—')),
        pasosDe(d),
        d.foto ? el('p', { style: 'margin-top:.6rem' }, el('img', { src: d.foto, alt: 'Foto del excedente', style: 'max-height:110px;border-radius:8px;border:1px solid var(--borde)' })) : null),
      el('div', { class: 'tarjeta' }, el('h3', null, 'Mapa y ruta'), mapaDiv,
        el('p', { class: 'meta', style: 'margin-top:.4rem' }, 'Naranja: donante · Verde: receptor · Azul: voluntario. Distancias estimadas en línea recta x 1.3 (sin API de mapas en el MVP).')),
      el('div', { class: 'tarjeta' }, el('div', { class: 'fila' }, insignia('coordinador'), el('h3', null, 'Cómo eligió al receptor')),
        el('p', { class: 'sub', style: 'margin:.3rem 0 .6rem' }, 'Puntaje 0-100 = necesidad + cercanía + margen de caducidad + capacidad + equidad. Cada descarte conserva su motivo.'),
        tablaCoordinador(d), bloqueOfertas(d)),
      el('div', { class: 'tarjeta' }, el('div', { class: 'fila' }, insignia('logistico'), el('h3', null, 'Cómo eligió al voluntario')),
        d.recoleccion_activa ? el('p', { class: 'sub', style: 'margin:.3rem 0 .6rem' }, d.recoleccion_activa.justificacion) : null,
        tablaLogistico(d)),
      el('div', { class: 'tarjeta' }, el('h3', null, 'Línea de tiempo de los agentes'),
        el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Cada traspaso del orquestador y cada decisión quedan registrados (bitácora de auditoría).'),
        lineaTiempo(d.eventos, ultimoEvento)));
    ultimoEvento = d.eventos.length ? d.eventos[d.eventos.length - 1].id : 0;
    // El mapa se crea una sola vez; al repintar el detalle su contenedor se vuelve a insertar en el DOM.
    if (!mapaMontado) { montarMapa(mapaDiv); mapaMontado = true; }
    pintarMapa(d);
    setTimeout(ajustarMapa, 50);
  }

  function dato(nombre, valor) {
    return el('div', { class: 'dato' }, el('span', null, nombre), el('b', { style: 'font-size:.95rem;font-weight:600' }, valor));
  }

  return {
    async activar(param) {
      usarReceptores(ctx.datos.receptores);
      if (param) { seleccionada = Number(param); ultimoEvento = 0; pintor.olvidar(); }
      await this.refrescar();
      setTimeout(ajustarMapa, 100); // el contenedor estaba oculto: Leaflet debe recalcular su tamaño
    },
    async refrescar() {
      const donaciones = await ctx.api.get('/donaciones');
      if (!seleccionada && donaciones.length) seleccionada = donaciones[0].id;
      pintor.pintar('lista', [donaciones, seleccionada], () => pintarLista(donaciones));
      if (!seleccionada) {
        pintor.pintar('detalle', null, () => llenar(detalle, el('div', { class: 'tarjeta' }, el('p', { class: 'vacio' }, 'Elige una donación para ver su avance y las decisiones de los agentes.'))));
        return;
      }
      let d;
      try { d = await ctx.api.get(`/donaciones/${seleccionada}`); }
      catch { seleccionada = null; return; }
      pintor.pintar('detalle', d, () => pintarDetalle(d));
    },
  };
}
