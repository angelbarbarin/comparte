// Vista "Voluntario": la consola de quien recoge y entrega (CP-05 y la parte del voluntario de CP-06).
import { el, llenar, Pintor, chipEstado, textoItems, fmtKg, fmtMomento, fmtHora, cuentaRegresiva } from '../util.js';

const MOTIVOS = ['Tengo un imprevisto', 'Me queda muy lejos', 'Mi vehículo no es adecuado', 'Otro motivo'];

export function crear(ctx) {
  const seccion = document.getElementById('vista-voluntario');
  const pintor = new Pintor();
  let voluntarioId = ctx.prefs.leer('voluntarioId', null);
  let temporizador = null;

  const selector = el('select', { id: 'voluntario', onchange: () => { voluntarioId = Number(selector.value); ctx.prefs.guardar('voluntarioId', voluntarioId); pintor.olvidar(); window.dispatchEvent(new Event('comparte:refrescar')); } });
  const perfil = el('div');
  const tareas = el('div');

  seccion.append(el('div', { class: 'rejilla-doc' },
    el('div', null,
      el('div', { class: 'tarjeta' }, el('h2', null, 'Actuar como voluntario'),
        el('div', { style: 'margin-top:.6rem' }, el('label', { for: 'voluntario' }, 'Voluntario'), selector)),
      el('div', { class: 'tarjeta' }, perfil)),
    tareas));

  function llenarSelector() {
    llenar(selector, ...ctx.datos.voluntarios.map((v) => el('option', { value: v.id }, `${v.nombre} · ${v.vehiculo}`)));
    if (!ctx.datos.voluntarios.some((v) => v.id === voluntarioId)) voluntarioId = ctx.datos.voluntarios[0]?.id ?? null;
    selector.value = voluntarioId;
  }

  function pintarPerfil() {
    const v = ctx.datos.voluntarios.find((x) => x.id === voluntarioId);
    if (!v) return;
    llenar(perfil, el('h3', null, v.nombre),
      el('p', { class: 'sub' }, `${v.vehiculo} · carga hasta ${fmtKg(v.capacidad_kg)} · ${v.municipio}`),
      el('div', { class: 'etiquetas', style: 'margin-top:.5rem' },
        el('span', { class: 'chip' }, `Turno ${v.disponible_desde}–${v.disponible_hasta}`),
        el('span', { class: `chip ${v.tiene_hielera ? 'ok' : ''}` }, v.tiene_hielera ? 'Con hielera' : 'Sin hielera'),
        el('span', { class: `chip ${v.disponible ? 'ok' : 'alerta'}` }, v.disponible ? 'Disponible' : 'No disponible')),
      el('p', { class: 'meta', style: 'margin-top:.7rem' }, 'La disponibilidad de los voluntarios es simulada en el MVP.'));
  }

  function resumenRuta(r) {
    const ruta = r.ruta;
    const d = r.donacion;
    return el('div', { class: 'sub' },
      el('p', null, el('b', null, '1. Recoger'), ` en ${d.donante.nombre} (${d.donante_direccion || d.donante.municipio}) · ${ruta.tramos[0].km} km, ~${ruta.tramos[0].min} min desde tu base`),
      el('p', null, el('b', null, '2. Entregar'), ` en ${d.receptor ? d.receptor.nombre : '—'} (${d.receptor_direccion || ''}) · ${ruta.tramos[1].km} km, ~${ruta.tramos[1].min} min`),
      el('p', null, `Recoges hacia las ${fmtHora(r.recoger_estimado)} y entregas hacia las ${fmtHora(r.entrega_estimada)} · total ${ruta.distancia_km} km`),
      d.requiere_frio ? el('p', { class: 'chip alerta' }, 'Requiere cadena de frío: lleva la hielera') : null);
  }

  function tarjetaPropuesta(r) {
    const motivo = el('select', { 'aria-label': 'Motivo del rechazo' }, MOTIVOS.map((m) => el('option', null, m)));
    const d = r.donacion;
    return el('div', { class: 'tarea urgente' },
      el('div', { class: 'fila espacio' }, el('b', null, `Propuesta · donación #${d.id}`), el('span', { class: 'chip alerta' }, 'Responde en ', el('b', { 'data-vence': r.vence_en }, cuentaRegresiva(r.vence_en, ctx.ahora())))),
      el('p', null, el('b', null, textoItems(d.items)), ` · ${fmtKg(d.total_kg)} · caduca ${fmtMomento(d.caduca_en, ctx.ahora())}`),
      resumenRuta(r),
      el('div', { class: 'acciones' },
        el('button', { class: 'boton primario', type: 'button', onclick: () => responder(r.id, true) }, 'Aceptar recolección'),
        el('div', { class: 'campo' }, el('label', null, 'Si no puedes'), motivo),
        el('button', { class: 'boton peligro', type: 'button', onclick: () => responder(r.id, false, motivo.value) }, 'Rechazar')));
  }

  function tarjetaActiva(r) {
    const d = r.donacion;
    const recogida = r.estado === 'recogida';
    return el('div', { class: 'tarea' },
      el('div', { class: 'fila espacio' }, el('b', null, `Donación #${d.id}`), chipEstado(d.estado)),
      el('p', null, el('b', null, textoItems(d.items)), ` · ${fmtKg(d.total_kg)}`),
      resumenRuta(r),
      el('div', { class: 'acciones' },
        recogida
          ? el('button', { class: 'boton primario', type: 'button', onclick: () => avanzar(r.id, 'entregada') }, 'Ya entregué en el receptor')
          : el('button', { class: 'boton primario', type: 'button', onclick: () => avanzar(r.id, 'recogida') }, 'Ya recogí con el donante')));
  }

  function pintarTareas(t) {
    llenar(tareas, 
      el('div', { class: 'tarjeta' }, el('h2', null, 'Propuestas de recolección'),
        t.propuestas.length ? t.propuestas.map(tarjetaPropuesta) : el('p', { class: 'vacio' }, 'Sin propuestas. Cuando un receptor acepte una donación y seas el voluntario más conveniente, te llegará aquí.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Mis recolecciones activas'),
        t.activas.length ? t.activas.map(tarjetaActiva) : el('p', { class: 'vacio' }, 'Ninguna en curso.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Entregadas'),
        t.entregadas.length ? t.entregadas.map((r) => el('p', { class: 'sub' }, `#${r.donacion.id} · ${textoItems(r.donacion.items)} → ${r.donacion.receptor ? r.donacion.receptor.nombre : '—'} · ${fmtHora(r.respondida_en)}`)) : el('p', { class: 'vacio' }, 'Todavía ninguna.')));
  }

  async function responder(id, aceptar, motivo) {
    try {
      await ctx.api.post(`/recolecciones/${id}/respuesta`, { aceptar, motivo: aceptar ? null : motivo });
      ctx.aviso(aceptar ? 'Recolección aceptada. El donante ya fue avisado.' : 'Rechazaste la recolección; el Logístico buscará otro voluntario.', 'ok');
    } catch (e) { ctx.aviso(e.message, 'error'); }
    pintor.olvidar();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  async function avanzar(id, estado) {
    try {
      await ctx.api.post(`/recolecciones/${id}/avance`, { estado });
      ctx.aviso(estado === 'recogida' ? 'Registrado: ya recogiste la donación.' : 'Registrado: entregaste. Falta que el receptor confirme.', 'ok');
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
      if (!voluntarioId) return;
      pintor.pintar('perfil', ctx.datos.voluntarios.find((v) => v.id === voluntarioId), pintarPerfil);
      const t = await ctx.api.get(`/voluntarios/${voluntarioId}/tareas`);
      pintor.pintar('tareas', t, pintarTareas);
    },
  };
}
