// Vista "Receptor": la consola de un comedor, albergue o banco de alimentos (CP-03 y la parte del receptor de CP-06).
import { el, llenar, Pintor, chipEstado, textoItems, fmtKg, fmtNum, fmtMomento, fmtHora, cuentaRegresiva, CATEGORIAS } from '../util.js';

const MOTIVOS = ['Sin espacio hoy', 'No necesitamos estos alimentos', 'No hay personal para recibirlo', 'Otro motivo'];

export function crear(ctx) {
  const seccion = document.getElementById('vista-receptor');
  const pintor = new Pintor();
  let receptorId = ctx.prefs.leer('receptorId', null);
  let temporizador = null;

  const selector = el('select', { id: 'receptor', onchange: () => { receptorId = Number(selector.value); ctx.prefs.guardar('receptorId', receptorId); pintor.olvidar(); window.dispatchEvent(new Event('comparte:refrescar')); } });
  const perfil = el('div');
  const tareas = el('div');

  seccion.append(el('div', { class: 'rejilla-doc' },
    el('div', null,
      el('div', { class: 'tarjeta' }, el('h2', null, 'Actuar como receptor'),
        el('div', { style: 'margin-top:.6rem' }, el('label', { for: 'receptor' }, 'Organización'), selector)),
      el('div', { class: 'tarjeta' }, perfil)),
    tareas));

  function llenarSelector() {
    llenar(selector, ...ctx.datos.receptores.map((r) => el('option', { value: r.id }, `${r.nombre}${r.verificado ? '' : ' (sin verificar)'}`)));
    if (!ctx.datos.receptores.some((r) => r.id === receptorId)) receptorId = ctx.datos.receptores[0]?.id ?? null;
    selector.value = receptorId;
  }

  function pintarPerfil() {
    const r = ctx.datos.receptores.find((x) => x.id === receptorId);
    if (!r) return;
    llenar(perfil, 
      el('h3', null, r.nombre),
      el('p', { class: 'sub' }, `${r.tipo.replace('_', ' ')} · ${r.municipio}`),
      el('div', { class: 'etiquetas', style: 'margin:.5rem 0' },
        el('span', { class: `chip ${r.verificado ? 'ok' : 'alerta'}` }, r.verificado ? 'Verificado' : 'Pendiente de verificación'),
        el('span', { class: 'chip' }, `Horario ${r.horario_apertura}–${r.horario_cierre}`)),
      el('p', { class: 'sub' }, `Atiende ~${fmtNum(r.personas_atendidas)} personas · recibe hasta ${fmtKg(r.capacidad_diaria_kg)} al día`
        + (r.capacidad_frio_kg > 0 ? ` (${fmtKg(r.capacidad_frio_kg)} con refrigeración)` : ' · sin refrigeración')),
      el('h4', { style: 'margin-top:.7rem' }, 'Necesidades (prioridad 1-3)'),
      el('div', { class: 'etiquetas', style: 'margin-top:.3rem' }, Object.entries(r.necesidades).map(([c, n]) => el('span', { class: 'chip info' }, `${CATEGORIAS[c] || c}: ${n}`))),
      !r.verificado ? el('p', { class: 'meta', style: 'margin-top:.7rem' }, 'Mientras no esté verificada por un administrador, esta organización no recibe ofertas.') : null);
  }

  function tarjetaOferta(o) {
    const d = o.donacion;
    const motivo = el('select', { 'aria-label': 'Motivo del rechazo' }, MOTIVOS.map((m) => el('option', null, m)));
    const cuenta = el('b', { 'data-vence': o.vence_en }, cuentaRegresiva(o.vence_en, ctx.ahora()));
    return el('div', { class: 'tarea urgente' },
      el('div', { class: 'fila espacio' }, el('b', null, `Oferta · donación #${d.id}`), el('span', { class: 'chip alerta' }, 'Responde en ', cuenta)),
      el('p', null, el('b', null, textoItems(d.items)), ` · ${fmtKg(d.total_kg)} de ${d.donante.nombre} (${d.donante.municipio})`),
      el('p', { class: 'sub' }, `Caduca ${fmtMomento(d.caduca_en, ctx.ahora())} · puntaje ${o.puntaje}/100`),
      el('p', { class: 'sub' }, `Por qué a ti: ${o.justificacion}`),
      el('div', { class: 'acciones' },
        el('button', { class: 'boton primario', type: 'button', onclick: () => responder(o.id, true) }, 'Aceptar'),
        el('div', { class: 'campo' }, el('label', null, 'Si no puedes'), motivo),
        el('button', { class: 'boton peligro', type: 'button', onclick: () => responder(o.id, false, motivo.value) }, 'Rechazar')));
  }

  function tarjetaPorConfirmar(d) {
    const kg = el('input', { type: 'number', min: '0.1', step: '0.1', value: d.total_kg, 'aria-label': 'Kilos realmente recibidos' });
    return el('div', { class: 'tarea' },
      el('div', { class: 'fila espacio' }, el('b', null, `Donación #${d.id} entregada`), chipEstado(d.estado)),
      el('p', null, `${textoItems(d.items)} · registrada como ${fmtKg(d.total_kg)} desde ${d.donante.nombre}`),
      el('div', { class: 'acciones' },
        el('div', { class: 'campo' }, el('label', null, 'Kilos que recibiste (corrígelos si difieren)'), kg),
        el('button', { class: 'boton primario', type: 'button', onclick: () => confirmar(d.id, Number(kg.value)) }, 'Confirmar recepción')));
  }

  function pintarTareas(t) {
    llenar(tareas, 
      el('div', { class: 'tarjeta' }, el('h2', null, 'Ofertas por responder'),
        t.ofertas.length ? t.ofertas.map(tarjetaOferta) : el('p', { class: 'vacio' }, 'Sin ofertas por ahora. Cuando el Coordinador te elija para una donación, aparecerá aquí.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Por confirmar recepción'),
        t.por_confirmar.length ? t.por_confirmar.map(tarjetaPorConfirmar) : el('p', { class: 'vacio' }, 'Nada pendiente de confirmar.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'En camino hacia ti'),
        t.en_camino.length ? t.en_camino.map((d) => el('div', { class: 'tarea' },
          el('div', { class: 'fila espacio' }, el('b', null, `Donación #${d.id} · ${d.donante.nombre}`), chipEstado(d.estado)),
          el('p', { class: 'sub' }, `${textoItems(d.items)} · ${fmtKg(d.total_kg)} · caduca ${fmtMomento(d.caduca_en, ctx.ahora())}`))) : el('p', { class: 'vacio' }, 'Ninguna donación en camino.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Recibidas en esta sesión'),
        t.completadas.length ? t.completadas.map((d) => el('p', { class: 'sub' }, `#${d.id} · ${textoItems(d.items)} · ${fmtKg(d.total_kg)} de ${d.donante.nombre} · ${fmtHora(d.completada_en)}`)) : el('p', { class: 'vacio' }, 'Todavía ninguna.')));
  }

  async function responder(ofertaId, aceptar, motivo) {
    try {
      await ctx.api.post(`/ofertas/${ofertaId}/respuesta`, { aceptar, motivo: aceptar ? null : motivo });
      ctx.aviso(aceptar ? 'Aceptaste la donación. El Logístico buscará quién la recoja.' : 'Rechazaste la oferta; el Coordinador buscará otro receptor.', 'ok');
    } catch (e) { ctx.aviso(e.message, 'error'); }
    pintor.olvidar();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  async function confirmar(donacionId, kg) {
    try {
      await ctx.api.post(`/donaciones/${donacionId}/confirmacion-recepcion`, { kg_recibidos: kg > 0 ? kg : null });
      ctx.aviso('Recepción confirmada. El Agente de Impacto registró el rescate.', 'ok');
    } catch (e) { ctx.aviso(e.message, 'error'); }
    pintor.olvidar();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  function actualizarCuentas() {
    for (const nodo of tareas.querySelectorAll('[data-vence]')) nodo.textContent = cuentaRegresiva(nodo.dataset.vence, ctx.ahora());
  }

  return {
    async activar() {
      llenarSelector();
      pintor.olvidar();
      clearInterval(temporizador);
      temporizador = setInterval(actualizarCuentas, 1000);
      await this.refrescar();
    },
    desactivar() { clearInterval(temporizador); },
    async refrescar() {
      if (!receptorId) return;
      pintor.pintar('perfil', ctx.datos.receptores.find((r) => r.id === receptorId), pintarPerfil);
      const t = await ctx.api.get(`/receptores/${receptorId}/tareas`);
      pintor.pintar('tareas', t, pintarTareas);
    },
  };
}
