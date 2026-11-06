// Utilidades de la interfaz: creación segura de nodos, formato en español y catálogos de etiquetas.
// Nunca se usa innerHTML con datos: todo texto (incluidos los mensajes de los donantes) entra como nodo de texto.

export function el(tag, props, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [clave, valor] of Object.entries(props || {})) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (clave === 'class') nodo.className = valor;
    else if (clave === 'dataset') Object.assign(nodo.dataset, valor);
    else if (clave.startsWith('on') && typeof valor === 'function') nodo.addEventListener(clave.slice(2).toLowerCase(), valor);
    else if (valor === true) nodo.setAttribute(clave, '');
    else nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return nodo;
}

export function vaciar(nodo) {
  while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
  return nodo;
}

/** Vacía ``nodo`` y le agrega ``hijos``, ignorando null/false (el append nativo escribiría "null"). */
export function llenar(nodo, ...hijos) {
  vaciar(nodo);
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return nodo;
}

/** Repinta solo cuando los datos cambian, para no borrar lo que la persona está escribiendo. */
export class Pintor {
  constructor() { this.firmas = new Map(); }
  pintar(clave, datos, fn) {
    const firma = JSON.stringify(datos);
    if (this.firmas.get(clave) === firma) return false;
    this.firmas.set(clave, firma);
    fn(datos);
    return true;
  }
  olvidar() { this.firmas.clear(); }
}

// ----------------------------------------------------------------------------- catálogos de etiquetas
export const AGENTES = {
  captador: 'Agente Captador', coordinador: 'Agente Coordinador', logistico: 'Agente Logístico',
  impacto: 'Agente de Impacto', orquestador: 'Orquestador', humano: 'Persona', sistema: 'Sistema', donante: 'Donante',
};

export function insignia(agente) {
  return el('span', { class: `insignia ${agente}` }, AGENTES[agente] || agente);
}

export const ESTADOS = {
  registrada: ['Registrada', 'info'],
  pendiente_validacion: ['En revisión humana', 'alerta'],
  rechazada: ['Rechazada', 'error'],
  ofrecida: ['Ofrecida a un receptor', 'info'],
  sin_receptor: ['Sin receptor', 'error'],
  asignada: ['Receptor aceptó', 'info'],
  sin_voluntario: ['Sin voluntario', 'error'],
  en_recoleccion: ['Voluntario va por ella', 'info'],
  en_camino: ['En camino al receptor', 'info'],
  entregada: ['Entregada · falta confirmar', 'alerta'],
  completada: ['Completada', 'ok'],
  caducada: ['Caducada', 'error'],
};

export function chipEstado(estado) {
  const [texto, tono] = ESTADOS[estado] || [estado, ''];
  return el('span', { class: `chip ${tono}` }, texto);
}

export const CATEGORIAS = {
  pan: 'Pan y tortilla', fruta: 'Fruta', verdura: 'Verdura', abarrotes: 'Abarrotes y bebidas',
  lacteos: 'Lácteos', proteina: 'Proteína', preparado: 'Comida preparada', otro: 'Otros',
};

// ----------------------------------------------------------------------------------------- formato
export const fmtNum = (n, decimales = 0) => Number(n).toLocaleString('es-MX', { maximumFractionDigits: decimales });
export const fmtKg = (n) => `${fmtNum(n, 1)} kg`;

export function fmtHora(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
}

/** 'hoy 20:00', 'mañana 08:30' o 'vie 13 nov 20:00', relativo a la hora de la aplicación. */
export function fmtMomento(iso, ahora) {
  if (!iso) return '—';
  const m = new Date(iso);
  const base = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate());
  const dia = new Date(m.getFullYear(), m.getMonth(), m.getDate());
  const dias = Math.round((dia - base) / 86400000);
  if (dias === 0) return `hoy ${fmtHora(iso)}`;
  if (dias === 1) return `mañana ${fmtHora(iso)}`;
  const fecha = m.toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short' }).replace(/\./g, '');
  return `${fecha} ${fmtHora(iso)}`;
}

export function textoItems(items) {
  return items.map((i) => `${fmtNum(i.cantidad, 1)} ${i.unidad} ${i.nombre}`).join(', ');
}

export function cuentaRegresiva(venceIso, ahora) {
  const seg = Math.floor((new Date(venceIso) - ahora) / 1000);
  if (seg <= 0) return 'venció';
  return `${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, '0')} min`;
}
