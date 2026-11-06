// Componentes visuales compartidos por varias vistas: progreso, línea de tiempo y mapa.
import { el, insignia, fmtHora } from './util.js';

// ----------------------------------------------------------------------------------- progreso
export function pasosDe(d) {
  const revision = d.inocuidad && d.inocuidad.requiere_revision;
  const nombres = ['Registrada', ...(revision ? ['Revisión humana'] : []), 'Receptor', 'Voluntario', 'Recolección', 'Entrega', 'Completada'];
  const indice = (n) => nombres.indexOf(n);
  const porEstado = {
    registrada: indice('Registrada'), pendiente_validacion: indice('Revisión humana'),
    ofrecida: indice('Receptor'), sin_receptor: indice('Receptor'),
    asignada: indice('Voluntario'), sin_voluntario: indice('Voluntario'),
    en_recoleccion: indice('Recolección'), en_camino: indice('Entrega'),
    entregada: indice('Completada'), completada: nombres.length,
    rechazada: revision ? indice('Revisión humana') : 0,
    caducada: d.receptor ? indice('Recolección') : indice('Receptor'),
  };
  const activo = porEstado[d.estado] ?? 0;
  const fallo = ['sin_receptor', 'sin_voluntario', 'rechazada', 'caducada'].includes(d.estado);
  return el('ol', { class: 'pasos', 'aria-label': 'Progreso de la donación' },
    nombres.map((nombre, i) => el('li', {
      class: i < activo ? 'hecho' : i === activo ? (fallo ? 'fallo' : 'activo') : '',
      'aria-current': i === activo ? 'step' : null,
    }, nombre)));
}

// ---------------------------------------------------------------------------------- bitácora
export function lineaTiempo(eventos, destacarDesde = null) {
  if (!eventos.length) return el('p', { class: 'vacio' }, 'Todavía no hay decisiones registradas.');
  return el('ol', { class: 'linea-tiempo' }, eventos.map((e) => el('li', { class: destacarDesde && e.id > destacarDesde ? 'nuevo' : '' },
    el('time', { datetime: e.creado_en }, fmtHora(e.creado_en)),
    el('span', null, insignia(e.agente)),
    el('span', null, e.resumen))));
}

// -------------------------------------------------------------------------------------- mapa
const COLORES = { donante: '#b45309', receptor: '#17663f', voluntario: '#1d4f91' };
let mapa = null;
let capa = null;
let ultimaFirma = null;

export function montarMapa(contenedor) {
  if (!window.L) {
    contenedor.textContent = 'No se pudo cargar el mapa (¿sin conexión?). El resto de la demo funciona igual.';
    return;
  }
  mapa = window.L.map(contenedor, { scrollWheelZoom: false }).setView([20.67, -103.35], 11);
  window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '© OpenStreetMap',
  }).addTo(mapa);
  capa = window.L.layerGroup().addTo(mapa);
  ultimaFirma = null;
}

export function ajustarMapa() {
  if (mapa) mapa.invalidateSize();
}

/** Dibuja donante, receptor (o el receptor al que se ofrece) y, si lo hay, voluntario con su ruta. */
export function pintarMapa(donacion) {
  if (!mapa) return;
  const L = window.L;
  const activa = donacion.recoleccion_activa;
  const oferta = [...donacion.ofertas].reverse().find((o) => o.estado === 'pendiente' || o.estado === 'aceptada');
  const firma = JSON.stringify([donacion.id, donacion.estado, activa && activa.id, oferta && oferta.id]);
  if (firma === ultimaFirma) return;
  const cambioDeDonacion = !ultimaFirma || JSON.parse(ultimaFirma)[0] !== donacion.id;
  ultimaFirma = firma;
  capa.clearLayers();

  const puntos = [];
  const marcar = (rol, nombre, lat, lon, etiqueta, radio = 9) => {
    const p = [lat, lon];
    puntos.push(p);
    L.circleMarker(p, { radius: radio, color: '#fff', weight: 2, fillColor: COLORES[rol], fillOpacity: 1 })
      .bindTooltip(`${etiqueta}: ${nombre}`, { permanent: false }).addTo(capa);
    return p;
  };

  const d = donacion.donante;
  const pd = marcar('donante', d.nombre, d.lat, d.lon, 'Donante');
  let pr = null;
  if (donacion.receptor) {
    pr = marcar('receptor', donacion.receptor.nombre, donacion.receptor.lat, donacion.receptor.lon, 'Receptor');
  }
  if (!pr && oferta) {  // todavía sin receptor confirmado: se muestra al que se le ofreció
    const [lat, lon] = coordenadasReceptor(oferta.receptor.id);
    pr = marcar('receptor', `${oferta.receptor.nombre} (oferta)`, lat, lon, 'Receptor');
  }
  if (activa && activa.ruta && activa.ruta.puntos) {
    const v = activa.ruta.puntos[0];
    const pv = marcar('voluntario', v.nombre, v.lat, v.lon, 'Voluntario', 7);
    L.polyline([pv, pd], { color: '#1d4f91', weight: 3, dashArray: '6 6' }).addTo(capa);
    if (pr) L.polyline([pd, pr], { color: '#17663f', weight: 4 }).addTo(capa);
  } else if (pr) {
    L.polyline([pd, pr], { color: '#6b7a71', weight: 3, dashArray: '4 6' }).addTo(capa);
  }
  if (cambioDeDonacion) mapa.fitBounds(L.latLngBounds(puntos).pad(0.3), { maxZoom: 14 });
}

// El ranking guarda el id del receptor ofertado pero no sus coordenadas; se leen del catálogo cargado al inicio.
let catalogoReceptores = [];
export function usarReceptores(lista) { catalogoReceptores = lista; }
function coordenadasReceptor(receptorId) {
  const r = catalogoReceptores.find((x) => x.id === receptorId);
  return r ? [r.lat, r.lon] : [20.67, -103.35];
}
