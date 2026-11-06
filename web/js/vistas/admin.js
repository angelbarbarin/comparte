// Vista "Admin": supervisión humana (CP-02, CP-09): revisar alimentos de riesgo, verificar receptores,
// atender donaciones atoradas, ver la bitácora de decisiones y controlar la demostración.
import { el, llenar, Pintor, chipEstado, insignia, textoItems, fmtKg, fmtHora, fmtMomento } from '../util.js';

export function crear(ctx) {
  const seccion = document.getElementById('vista-admin');
  const pintor = new Pintor();

  const controles = el('div', { class: 'tarjeta' });
  const pendientes = el('div');
  const bitacora = el('div', { class: 'tarjeta' });
  seccion.append(controles, pendientes, bitacora);

  // -------------------------------------------------------------------- controles de demo
  function pintarControles() {
    const hora = ctx.ahora().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
    llenar(controles, 
      el('h2', null, 'Controles de la demostración'),
      el('p', { class: 'sub', style: 'margin:.2rem 0 .7rem' }, `Hora actual de la aplicación: ${hora}. Fija una hora razonable antes de grabar (de noche, casi todos los receptores estarían cerrados) y adelanta el reloj para mostrar que una oferta sin respuesta se reasigna.`),
      el('div', { class: 'acciones' },
        boton('Fijar hora a las 16:00', () => accion('/demo/fijar-hora', { hora: '16:00' }, 'Hora fijada a las 16:00')),
        boton('Adelantar 16 min', () => accion('/demo/avanzar-reloj', { minutos: 16 }, 'Reloj adelantado 16 minutos (una oferta sin respuesta vence a los 15)')),
        boton('Adelantar 1 hora', () => accion('/demo/avanzar-reloj', { minutos: 60 }, 'Reloj adelantado 1 hora')),
        boton('Reiniciar datos de demo', () => reiniciar(true), 'peligro'),
        boton('Reiniciar sin historial', () => reiniciar(false), 'peligro')));
  }

  function boton(texto, fn, clase = '') {
    return el('button', { class: `boton ${clase}`, type: 'button', onclick: fn }, texto);
  }

  async function accion(ruta, cuerpo, mensaje) {
    try { await ctx.api.post(ruta, cuerpo); ctx.aviso(mensaje, 'ok'); }
    catch (e) { ctx.aviso(e.message, 'error'); }
    await ctx.recargarEstado();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  async function reiniciar(conHistorial) {
    if (!window.confirm('Se borrarán TODAS las donaciones y conversaciones de esta sesión. ¿Continuar?')) return;
    try {
      const r = await ctx.api.post('/demo/reiniciar', { con_historial: conHistorial });
      ctx.aviso(`Datos de demostración recargados (${r.historial} rescates simulados).`, 'ok');
      await ctx.reiniciado();
    } catch (e) { ctx.aviso(e.message, 'error'); }
  }

  // ------------------------------------------------------------------------ pendientes
  async function revisar(id, aprobar, nota) {
    try {
      await ctx.api.post(`/donaciones/${id}/revision`, { aprobar, nota: nota || null });
      ctx.aviso(aprobar ? 'Donación aprobada: el Coordinador ya busca receptor.' : 'Donación rechazada; se avisó al donante.', 'ok');
    } catch (e) { ctx.aviso(e.message, 'error'); }
    pintor.olvidar();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  function tarjetaValidacion(d) {
    const nota = el('input', { type: 'text', placeholder: 'Nota opcional (p. ej. “viene en hielera, aprobado”)', maxlength: 300, 'aria-label': 'Nota de la revisión' });
    const motivos = (d.inocuidad.motivos || []).concat(d.inocuidad.advertencias || []);
    return el('div', { class: 'tarea urgente' },
      el('div', { class: 'fila espacio' }, el('b', null, `Donación #${d.id} · ${d.donante.nombre}`), chipEstado(d.estado)),
      el('p', null, el('b', null, textoItems(d.items)), ` · ${fmtKg(d.total_kg)} · caduca ${fmtMomento(d.caduca_en, ctx.ahora())}`),
      el('div', { class: 'etiquetas' },
        el('span', { class: 'chip alerta' }, `Riesgo ${d.inocuidad.nivel}`),
        d.requiere_frio ? el('span', { class: 'chip info' }, 'Requiere cadena de frío') : null,
        (d.condiciones || []).map((c) => el('span', { class: 'chip' }, c.replaceAll('_', ' ')))),
      el('ul', { class: 'sub', style: 'margin:0;padding-left:1.1rem' }, motivos.map((m) => el('li', null, m))),
      el('div', { class: 'acciones' },
        el('div', { class: 'campo' }, el('label', null, 'Nota'), nota),
        boton('Aprobar', () => revisar(d.id, true, nota.value), 'primario'),
        boton('Rechazar', () => revisar(d.id, false, nota.value), 'peligro')));
  }

  async function reintentar(id) {
    try { await ctx.api.post(`/donaciones/${id}/reintento`); ctx.aviso('Reintento solicitado.', 'ok'); }
    catch (e) { ctx.aviso(e.message, 'error'); }
    pintor.olvidar();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  async function verificar(id) {
    try { await ctx.api.post(`/receptores/${id}/verificacion`, { verificado: true }); ctx.aviso('Receptor verificado.', 'ok'); await ctx.recargarCatalogos(); }
    catch (e) { ctx.aviso(e.message, 'error'); }
    pintor.olvidar();
    window.dispatchEvent(new Event('comparte:refrescar'));
  }

  function pintarPendientes(p) {
    llenar(pendientes, 
      el('div', { class: 'tarjeta' }, el('h2', null, 'Alimentos de riesgo por validar'),
        el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Supervisión humana: carnes, lácteos, comida preparada y alimentos no reconocidos no avanzan sin que una persona los apruebe.'),
        p.validacion.length ? p.validacion.map(tarjetaValidacion) : el('p', { class: 'vacio' }, 'Nada por validar.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Donaciones atoradas'),
        p.atoradas.length ? p.atoradas.map((d) => el('div', { class: 'tarea' },
          el('div', { class: 'fila espacio' }, el('b', null, `Donación #${d.id} · ${d.donante.nombre}`), chipEstado(d.estado)),
          el('p', { class: 'sub' }, `${textoItems(d.items)} · ${fmtKg(d.total_kg)}. Revisa el detalle en “Seguimiento” y reintenta cuando haya receptores o voluntarios.`),
          el('div', { class: 'acciones' }, boton('Reintentar', () => reintentar(d.id), 'primario'), boton('Ver detalle', () => ctx.ir('seguimiento', d.id))))) : el('p', { class: 'vacio' }, 'Ninguna.')),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Receptores por verificar'),
        el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Las organizaciones nuevas no reciben ofertas hasta que una persona las valida.'),
        p.receptores_sin_verificar.length ? p.receptores_sin_verificar.map((r) => el('div', { class: 'tarea' },
          el('div', { class: 'fila espacio' }, el('b', null, r.nombre), el('span', { class: 'chip alerta' }, 'Sin verificar')),
          el('p', { class: 'sub' }, `${r.tipo.replace('_', ' ')} · ${r.municipio} · contacto: ${r.contacto || '—'} · capacidad ${fmtKg(r.capacidad_diaria_kg)}/día`),
          el('div', { class: 'acciones' }, boton('Verificar organización', () => verificar(r.id), 'primario')))) : el('p', { class: 'vacio' }, 'Todos verificados.')));
  }

  // ------------------------------------------------------------------------ bitácora
  function pintarBitacora(eventos) {
    llenar(bitacora, 
      el('h2', null, 'Bitácora de decisiones de los agentes'),
      el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Registro de auditoría (requisito de seguridad del documento de visión): quién decidió qué y por qué. Más recientes primero.'),
      eventos.length ? el('div', { class: 'tabla-envoltura' }, el('table', { class: 'tabla' },
        el('thead', null, el('tr', null, el('th', null, 'Hora'), el('th', null, 'Donación'), el('th', null, 'Agente'), el('th', null, 'Decisión'))),
        el('tbody', null, eventos.map((e) => el('tr', null,
          el('td', null, fmtHora(e.creado_en)),
          el('td', null, e.donacion_id ? el('a', { href: `#seguimiento/${e.donacion_id}` }, `#${e.donacion_id}`) : '—'),
          el('td', null, insignia(e.agente)), el('td', null, e.resumen)))))) : el('p', { class: 'vacio' }, 'Sin eventos todavía.'));
  }

  return {
    async activar() { pintor.olvidar(); await this.refrescar(); },
    async refrescar() {
      pintor.pintar('controles', ctx.estado.hora, pintarControles);
      const [p, e] = await Promise.all([ctx.api.get('/admin/pendientes'), ctx.api.get('/eventos?limite=60')]);
      pintor.pintar('pendientes', p, pintarPendientes);
      pintor.pintar('bitacora', e, pintarBitacora);
    },
  };
}
