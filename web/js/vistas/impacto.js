// Vista "Impacto": tablero del Agente de Impacto (CP-07) y reporte/constancia por donante (CP-08, parcial).
import { el, llenar, Pintor, fmtNum, fmtKg, fmtHora } from '../util.js';

const NS = 'http://www.w3.org/2000/svg';

function svg(tag, props, ...hijos) {
  const nodo = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(props || {})) nodo.setAttribute(k, v);
  for (const h of hijos.flat()) if (h) nodo.append(h);
  return nodo;
}

export function crear(ctx) {
  const seccion = document.getElementById('vista-impacto');
  const pintor = new Pintor();
  let incluirSimuladas = ctx.prefs.leer('incluirSimuladas', true);
  let donanteReporte = null;

  const contenido = el('div');
  const reporte = el('div');
  const selDonante = el('select', { id: 'donante-reporte', onchange: () => { donanteReporte = Number(selDonante.value); } });
  const interruptor = el('input', { type: 'checkbox', id: 'simuladas', checked: incluirSimuladas,
    onchange: () => { incluirSimuladas = interruptor.checked; ctx.prefs.guardar('incluirSimuladas', incluirSimuladas); pintor.olvidar(); window.dispatchEvent(new Event('comparte:refrescar')); } });
  interruptor.checked = incluirSimuladas;

  seccion.append(
    el('div', { class: 'tarjeta' },
      el('div', { class: 'fila espacio' },
        el('div', null, el('h2', null, 'Impacto del rescate'), el('p', { class: 'sub' }, 'Medido por el Agente de Impacto a partir de las recepciones confirmadas por los receptores.')),
        el('label', { for: 'simuladas', style: 'display:flex;gap:.5rem;align-items:center;margin:0' }, interruptor, 'Incluir historial simulado'))),
    contenido,
    el('div', { class: 'tarjeta' },
      el('h3', null, 'Reporte para donantes'),
      el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Constancia del impacto que ha logrado cada donante (versión en pantalla del reporte mensual del documento de visión).'),
      el('div', { class: 'acciones' },
        el('div', { class: 'campo' }, el('label', { for: 'donante-reporte' }, 'Donante'), selDonante),
        el('button', { class: 'boton primario', type: 'button', onclick: verReporte }, 'Ver reporte')),
      reporte));

  // ------------------------------------------------------------------------------- gráficas
  function graficaDiaria(serie) {
    const ancho = 760, alto = 190, margen = { i: 36, d: 8, s: 10, b: 28 };
    const maximo = Math.max(10, ...serie.map((d) => d.kg));
    const paso = (ancho - margen.i - margen.d) / serie.length;
    const y = (kg) => alto - margen.b - ((alto - margen.b - margen.s) * kg) / maximo;
    const nodo = svg('svg', { viewBox: `0 0 ${ancho} ${alto}`, class: 'grafica', role: 'img',
      'aria-label': `Kilos rescatados por día durante ${serie.length} días. Máximo ${fmtNum(maximo)} kg en un día.` });
    for (const marca of [0, 0.5, 1]) {
      const v = maximo * marca;
      nodo.append(svg('line', { x1: margen.i, x2: ancho - margen.d, y1: y(v), y2: y(v), stroke: '#d6ded8', 'stroke-width': 1 }),
        Object.assign(svg('text', { x: margen.i - 6, y: y(v) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#4b5a52' }), { textContent: fmtNum(v) }));
    }
    serie.forEach((d, i) => {
      const x = margen.i + i * paso + 1.5;
      const barra = svg('rect', { x, y: y(d.kg), width: Math.max(paso - 3, 2), height: alto - margen.b - y(d.kg), rx: 2, fill: d.rescates ? '#17663f' : '#e1e8e3' });
      barra.append(Object.assign(svg('title'), { textContent: `${d.fecha}: ${fmtNum(d.kg, 1)} kg en ${d.rescates} rescate(s)` }));
      nodo.append(barra);
    });
    for (const i of [0, Math.floor(serie.length / 2), serie.length - 1]) {
      const f = new Date(`${serie[i].fecha}T00:00:00`).toLocaleDateString('es-MX', { day: 'numeric', month: 'short' });
      nodo.append(Object.assign(svg('text', { x: margen.i + i * paso + paso / 2, y: alto - 8, 'text-anchor': i === 0 ? 'start' : i === serie.length - 1 ? 'end' : 'middle', 'font-size': 11, fill: '#4b5a52' }), { textContent: f }));
    }
    return nodo;
  }

  function barras(filas, unidad = 'kg') {
    if (!filas.length) return el('p', { class: 'vacio' }, 'Sin datos.');
    const maximo = Math.max(...filas.map((f) => f.kg));
    return filas.map((f) => el('div', { class: 'fila-barra' },
      el('span', { title: f.etiqueta }, f.etiqueta),
      el('span', { class: 'pista' }, el('i', { style: `width:${(100 * f.kg) / maximo}%` })),
      el('span', null, `${fmtNum(f.kg)} ${unidad}`)));
  }

  function kpi(valor, nombre, nota) {
    return el('div', { class: 'kpi' }, el('div', { class: 'valor' }, valor), el('div', { class: 'nombre' }, nombre), nota ? el('div', { class: 'nota' }, nota) : null);
  }

  function filaProceso(nombre, valor, meta, cumple) {
    return el('tr', null, el('td', null, nombre),
      el('td', null, valor ?? el('span', { class: 'meta' }, 'Sin datos aún')),
      el('td', null, meta),
      el('td', null, cumple === null || valor === null ? '' : el('span', { class: `chip ${cumple ? 'ok' : 'error'}` }, cumple ? 'Cumple' : 'No cumple')));
  }

  function pintar(r) {
    const t = r.totales, k = r.kpis, s = r.supuestos;
    llenar(contenido, 
      el('div', { class: 'rejilla-4', style: 'margin-top:1rem' },
        kpi(fmtNum(t.kg), 'kg rescatados', `${fmtNum(t.rescates)} rescates`),
        kpi(fmtNum(t.raciones), 'raciones', `1 ración = ${s.kg_por_racion} kg`),
        kpi(fmtNum(t.personas), 'personas beneficiadas (est.)', `= raciones ÷ ${s.raciones_por_persona_dia}: personas alimentadas un día completo`),
        kpi(fmtNum(t.co2e_kg), 'kg de CO2e evitados', 'factores de referencia por validar')),
      r.simuladas.rescates
        ? el('p', { class: 'meta', style: 'margin:.6rem 0' }, `Incluye ${r.simuladas.rescates} rescates SIMULADOS (${fmtKg(r.simuladas.kg)}) del piloto de demostración. Desactívalos arriba para ver solo lo hecho en esta sesión.`)
        : null,
      el('div', { class: 'tarjeta', style: 'margin-top:1rem' }, el('h3', null, 'Kilos rescatados por día'), graficaDiaria(r.serie_diaria)),
      el('div', { class: 'rejilla-2', style: 'margin-top:1rem' },
        el('div', { class: 'tarjeta' }, el('h3', null, 'Por municipio donde se origina'), barras(r.por_municipio_origen)),
        el('div', { class: 'tarjeta' }, el('h3', null, 'Por tipo de alimento'), barras(r.por_categoria))),
      el('div', { class: 'rejilla-2', style: 'margin-top:1rem' },
        el('div', { class: 'tarjeta' }, el('h3', null, 'Donantes que más han aportado'), barras(r.top_donantes)),
        el('div', { class: 'tarjeta' }, el('h3', null, 'Indicadores de proceso (sesión real)'),
          el('p', { class: 'meta', style: 'margin:.2rem 0 .5rem' }, `Solo cuentan donaciones hechas en esta sesión (${k.donaciones_reales}), no el historial simulado.`),
          el('div', { class: 'tabla-envoltura' }, el('table', { class: 'tabla' },
            el('thead', null, el('tr', null, el('th', null, 'Indicador'), el('th', null, 'Valor'), el('th', null, 'Meta'), el('th'))),
            el('tbody', null,
              filaProceso('Registrar una donación', k.segundos_registro_mediana != null ? `${k.segundos_registro_mediana} s` : null, '≤ 60 s', k.segundos_registro_mediana != null ? k.segundos_registro_mediana <= 60 : null),
              filaProceso('Proponer receptor (agente)', k.segundos_primera_oferta_mediana != null ? `${k.segundos_primera_oferta_mediana} s` : null, '≤ 120 s', k.segundos_primera_oferta_mediana != null ? k.segundos_primera_oferta_mediana <= 120 : null),
              filaProceso('Aceptación a la 1.ª oferta', k.aceptacion_primera_oferta != null ? `${Math.round(100 * k.aceptacion_primera_oferta)} %` : null, '—', null),
              filaProceso('Rescates completados', k.tasa_completadas != null ? `${Math.round(100 * k.tasa_completadas)} % (${k.completadas_reales}/${k.donaciones_reales})` : null, '—', null)))),
          el('p', { class: 'meta', style: 'margin-top:.5rem' }, 'Las metas vienen de los rangos de calidad del documento de visión (sección 7). El tiempo de registro mide hasta que el donante confirma.'))));
  }

  async function verReporte() {
    if (!donanteReporte) return;
    try {
      const rep = await ctx.api.get(`/impacto/donantes/${donanteReporte}`);
      const t = rep.resumen.totales;
      llenar(reporte, 
        el('div', { class: 'rejilla-4', style: 'margin:1rem 0' }, kpi(fmtNum(t.kg), 'kg rescatados'), kpi(fmtNum(t.raciones), 'raciones'), kpi(fmtNum(t.personas), 'personas (est.)'), kpi(fmtNum(t.co2e_kg), 'kg CO2e evitados')),
        rep.rescates.length
          ? el('div', { class: 'tabla-envoltura' }, el('table', { class: 'tabla' },
            el('thead', null, el('tr', null, el('th', null, 'Fecha'), el('th', null, 'Alimentos'), el('th', null, 'Receptor'), el('th', null, 'kg'), el('th', null, 'Origen'))),
            el('tbody', null, rep.rescates.map((x) => el('tr', null,
              el('td', null, `${new Date(x.fecha).toLocaleDateString('es-MX', { day: 'numeric', month: 'short' })} ${fmtHora(x.fecha)}`),
              el('td', null, x.alimentos.join(', ')), el('td', null, x.receptor || '—'), el('td', null, fmtNum(x.kg, 1)),
              el('td', null, x.simulada ? el('span', { class: 'chip alerta' }, 'Simulado') : el('span', { class: 'chip ok' }, 'Real')))))))
          : el('p', { class: 'vacio' }, `${rep.donante.nombre} aún no tiene rescates completados.`));
    } catch (e) { ctx.aviso(e.message, 'error'); }
  }

  return {
    async activar() {
      llenar(selDonante, ...ctx.datos.donantes.map((d) => el('option', { value: d.id }, d.nombre)));
      donanteReporte = donanteReporte && ctx.datos.donantes.some((d) => d.id === donanteReporte) ? donanteReporte : ctx.datos.donantes[0]?.id;
      selDonante.value = donanteReporte;
      pintor.olvidar();
      await this.refrescar();
    },
    async refrescar() {
      const r = await ctx.api.get(`/impacto?simuladas=${incluirSimuladas}`);
      pintor.pintar('impacto', r, pintar);
    },
  };
}
