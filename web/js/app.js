// Arranque de la interfaz: carga los catálogos, enruta entre vistas (#donar, #seguimiento/12...) y
// refresca la vista activa cada pocos segundos.
import { api } from './api.js';
import { el, vaciar } from './util.js';
import { crear as crearDonar } from './vistas/donar.js';
import { crear as crearSeguimiento } from './vistas/seguimiento.js';
import { crear as crearReceptor } from './vistas/receptor.js';
import { crear as crearVoluntario } from './vistas/voluntario.js';
import { crear as crearImpacto } from './vistas/impacto.js';
import { crear as crearAdmin } from './vistas/admin.js';

const INTERVALO_MS = 3000;

const prefs = {
  leer(clave, defecto) {
    try { const v = localStorage.getItem(`comparte.${clave}`); return v === null ? defecto : JSON.parse(v); }
    catch { return defecto; }
  },
  guardar(clave, valor) { try { localStorage.setItem(`comparte.${clave}`, JSON.stringify(valor)); } catch { /* modo privado */ } },
  borrar(prefijo) {
    try { Object.keys(localStorage).filter((k) => k.startsWith(`comparte.${prefijo}`)).forEach((k) => localStorage.removeItem(k)); } catch { /* modo privado */ }
  },
};

const ctx = {
  api, prefs,
  datos: { donantes: [], receptores: [], voluntarios: [] },
  estado: { hora: new Date().toISOString(), motor_lenguaje: '…', pesos_asignacion: {} },
  desfaseMs: 0,
  ahora: () => new Date(Date.now() + ctx.desfaseMs),
  aviso(texto, tipo = '') {
    const nodo = el('div', { class: `aviso ${tipo}` }, texto);
    document.getElementById('avisos').append(nodo);
    setTimeout(() => nodo.remove(), tipo === 'error' ? 7000 : 4000);
  },
  ir(vista, param) { location.hash = param ? `#${vista}/${param}` : `#${vista}`; },
  async recargarEstado() {
    ctx.estado = await api.get('/estado');
    ctx.desfaseMs = new Date(ctx.estado.hora) - Date.now();
    pintarEstado();
  },
  async recargarCatalogos() {
    [ctx.datos.donantes, ctx.datos.receptores, ctx.datos.voluntarios] = await Promise.all([
      api.get('/donantes'), api.get('/receptores'), api.get('/voluntarios')]);
  },
  async reiniciado() {
    prefs.borrar('conv_');
    await ctx.recargarCatalogos();
    await ctx.recargarEstado();
    vistas.donar.reiniciado();
    activar(vistaActual, parametroActual);
  },
};

const vistas = {
  donar: crearDonar(ctx), seguimiento: crearSeguimiento(ctx), receptor: crearReceptor(ctx),
  voluntario: crearVoluntario(ctx), impacto: crearImpacto(ctx), admin: crearAdmin(ctx),
};
let vistaActual = null;
let parametroActual = null;
let ocupado = false;

function pintarEstado() {
  const hora = ctx.ahora().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
  vaciar(document.getElementById('estado-app')).append(
    el('span', { class: 'pastilla' }, 'Motor de lenguaje: ', el('b', null, ctx.estado.motor_lenguaje)),
    el('span', { class: `pastilla ${ctx.estado.reloj_de_demo ? 'demo' : ''}` }, ctx.estado.reloj_de_demo ? 'Hora de demo: ' : 'Hora: ', el('b', null, hora)),
    el('span', { class: 'pastilla demo' }, 'Datos de demostración'));
}

async function activar(nombre, parametro) {
  if (!vistas[nombre]) nombre = 'donar';
  if (vistaActual && vistaActual !== nombre && vistas[vistaActual].desactivar) vistas[vistaActual].desactivar();
  vistaActual = nombre;
  parametroActual = parametro;
  for (const seccion of document.querySelectorAll('.vista')) seccion.hidden = seccion.id !== `vista-${nombre}`;
  for (const enlace of document.querySelectorAll('.pestanas a')) {
    if (enlace.dataset.vista === nombre) enlace.setAttribute('aria-current', 'page'); else enlace.removeAttribute('aria-current');
  }
  try { await vistas[nombre].activar(parametro); }
  catch (error) { ctx.aviso(`No se pudo cargar la vista: ${error.message}`, 'error'); }
}

function enrutar() {
  const [nombre, parametro] = (location.hash || '#donar').slice(1).split('/');
  activar(nombre, parametro);
}

async function refrescar() {
  if (ocupado || document.hidden || !vistaActual) return;
  ocupado = true;
  try {
    await ctx.recargarEstado();
    await vistas[vistaActual].refrescar();
  } catch (error) {
    console.warn('No se pudo refrescar', error);
  } finally {
    ocupado = false;
  }
}

async function iniciar() {
  try {
    await Promise.all([ctx.recargarEstado(), ctx.recargarCatalogos()]);
  } catch (error) {
    document.getElementById('contenido').append(el('div', { class: 'tarjeta' },
      el('h2', null, 'No pude conectar con la API'),
      el('p', null, 'Arranca el servidor con: python -m comparte servir. Detalle: ', error.message)));
    return;
  }
  window.addEventListener('hashchange', enrutar);
  window.addEventListener('comparte:refrescar', refrescar);
  enrutar();
  setInterval(refrescar, INTERVALO_MS);
  setInterval(pintarEstado, 15000);
}

iniciar();
