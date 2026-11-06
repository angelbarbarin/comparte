// Vista "Donar": chat del donante con el Agente Captador (canal web, plan B del costo de WhatsApp).
import { el, vaciar, llenar, Pintor, insignia, chipEstado, textoItems, fmtKg } from '../util.js';
import { pasosDe } from '../componentes.js';

const EJEMPLOS = [
  ['Pan del día y fruta', 'Tengo 25 kg de pan dulce del día y 10 kg de fruta madura, pueden pasar después de las 5 pm'],
  ['Pollo y leche (riesgo)', 'Tengo 12 kg de pollo y 8 litros de leche, vence mañana'],
  ['Falta la cantidad', 'Tengo pan dulce'],
  ['En cajas y charolas', '3 cajas de jitomate y 2 charolas de gelatina, caducan mañana'],
  ['Alimento no aceptado', 'Tengo 10 litros de cerveza'],
];
const MAX_BYTES_FOTO = 5 * 1024 * 1024;

export function crear(ctx) {
  const seccion = document.getElementById('vista-donar');
  const pintor = new Pintor();
  let donanteId = ctx.prefs.leer('donanteId', null);
  let conversacion = null;
  let foto = null; // { base64, tipo, nombre, url }
  let enviando = false;

  const selDonante = el('select', { id: 'donante', onchange: () => cambiarDonante(Number(selDonante.value)) });
  const mensajes = el('div', { class: 'chat-mensajes', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversación con el Agente Captador' });
  const entrada = el('input', { type: 'text', id: 'texto', placeholder: 'Describe lo que sobró: qué, cuánto y hasta cuándo…', autocomplete: 'off', maxlength: 2000, 'aria-label': 'Mensaje para el Agente Captador' });
  const archivo = el('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp,image/gif', hidden: true, onchange: elegirFoto });
  const botonEnviar = el('button', { class: 'boton primario', type: 'submit' }, 'Enviar');
  const vistaPrevia = el('div', { class: 'vista-previa', hidden: true });
  const panelDonacion = el('div');

  const formulario = el('form', { class: 'chat-form', onsubmit: enviar },
    el('button', { class: 'boton', type: 'button', title: 'Adjuntar una foto del excedente', onclick: () => archivo.click() }, '📎 Foto'),
    entrada, botonEnviar, archivo);

  const ejemplos = el('div', { class: 'ejemplos' },
    el('span', { class: 'sub' }, 'Ejemplos para la demo:'),
    EJEMPLOS.map(([titulo, texto]) => el('button', { class: 'chip', type: 'button', style: 'cursor:pointer', onclick: () => { entrada.value = texto; entrada.focus(); } }, titulo)));

  seccion.append(el('div', { class: 'rejilla-2' },
    el('div', null,
      el('div', { class: 'tarjeta' },
        el('h2', null, 'Habla con el Agente Captador'),
        el('p', { class: 'sub' }, 'Cuéntale tu excedente como se lo contarías a una persona. Se confirma antes de registrarlo.'),
        el('div', { class: 'fila', style: 'margin:.75rem 0' },
          el('div', { class: 'campo' }, el('label', { for: 'donante' }, 'Actuar como donante'), selDonante),
          el('button', { class: 'boton', type: 'button', onclick: () => nuevaConversacion(true) }, 'Nueva conversación')),
        el('div', { class: 'chat' }, mensajes, formulario),
        vistaPrevia, ejemplos)),
    el('div', null,
      el('div', { class: 'tarjeta' }, el('h2', null, 'Tu donación'), panelDonacion),
      el('div', { class: 'tarjeta' },
        el('h3', null, '¿Quién hace qué?'),
        el('ul', { class: 'sub', style: 'padding-left:1.1rem;margin:.5rem 0 0;display:grid;gap:.4rem' },
          el('li', null, insignia('captador'), ' entiende tu mensaje (y tu foto) y revisa la inocuidad.'),
          el('li', null, insignia('coordinador'), ' elige el receptor que más lo necesita y llega a tiempo.'),
          el('li', null, insignia('logistico'), ' busca voluntario y calcula la ruta.'),
          el('li', null, insignia('impacto'), ' mide kg, raciones, personas y CO2e evitados.'),
          el('li', null, insignia('orquestador'), ' los coordina y pide revisión humana si hay riesgo.'))))));

  // ----------------------------------------------------------------------------------- acciones
  function llenarDonantes() {
    llenar(selDonante, ...ctx.datos.donantes.map((d) => el('option', { value: d.id }, `${d.nombre} · ${d.municipio}`)));
    if (!ctx.datos.donantes.some((d) => d.id === donanteId)) donanteId = ctx.datos.donantes[0]?.id ?? null;
    selDonante.value = donanteId;
  }

  async function nuevaConversacion(forzar = false) {
    if (!donanteId) return;
    const clave = `conv_${donanteId}`;
    if (!forzar) {
      const guardada = ctx.prefs.leer(clave, null);
      if (guardada) {
        try { conversacion = await ctx.api.get(`/conversaciones/${guardada}`); pintar(); return; }
        catch { /* la base se reinició: se crea una nueva */ }
      }
    }
    conversacion = await ctx.api.post('/conversaciones', { donante_id: donanteId });
    ctx.prefs.guardar(clave, conversacion.id);
    pintor.olvidar();
    pintar();
  }

  async function cambiarDonante(id) {
    donanteId = id;
    ctx.prefs.guardar('donanteId', id);
    pintor.olvidar();
    await nuevaConversacion();
  }

  function elegirFoto() {
    const f = archivo.files[0];
    archivo.value = '';
    if (!f) return;
    if (f.size > MAX_BYTES_FOTO) { ctx.aviso('La foto pesa más de 5 MB. Elige una más pequeña.', 'error'); return; }
    const lector = new FileReader();
    lector.onload = () => {
      const url = String(lector.result);
      foto = { base64: url.split(',')[1], tipo: f.type, nombre: f.name, url };
      pintarFoto();
    };
    lector.readAsDataURL(f);
  }

  function pintarFoto() {
    vaciar(vistaPrevia);
    vistaPrevia.hidden = !foto;
    if (!foto) return;
    vistaPrevia.append(el('img', { src: foto.url, alt: 'Vista previa de la foto adjunta' }), el('span', null, foto.nombre),
      el('button', { class: 'boton chico', type: 'button', onclick: () => { foto = null; pintarFoto(); } }, 'Quitar'));
  }

  async function enviar(evento) {
    evento.preventDefault();
    const texto = entrada.value.trim();
    if (!texto || enviando || !conversacion) return;
    enviando = true;
    botonEnviar.disabled = true;
    try {
      const cuerpo = { texto };
      if (foto) { cuerpo.imagen_base64 = foto.base64; cuerpo.imagen_tipo = foto.tipo; }
      const r = await ctx.api.post(`/conversaciones/${conversacion.id}/mensajes`, cuerpo);
      entrada.value = '';
      foto = null;
      pintarFoto();
      conversacion = r.conversacion;
      pintar();
      if (r.donacion) ctx.aviso(`Donación #${r.donacion.id} registrada. Sigue su avance en “Seguimiento”.`, 'ok');
    } catch (error) {
      ctx.aviso(`No se pudo enviar el mensaje: ${error.message}`, 'error');
    } finally {
      enviando = false;
      botonEnviar.disabled = false;
      entrada.focus();
    }
  }

  // ------------------------------------------------------------------------------------ pintado
  function pintar() {
    if (!conversacion) return;
    pintor.pintar('chat', conversacion.mensajes, (lista) => {
      const abajo = mensajes.scrollHeight - mensajes.scrollTop - mensajes.clientHeight < 80;
      llenar(mensajes, ...lista.map((m) => {
        const mio = m.rol === 'donante';
        return el('div', { class: `msj ${mio ? 'mio' : ''}` },
          el('span', { class: 'quien' }, mio ? 'Tú' : insignia(m.rol)),
          el('div', { class: 'globo' }, m.imagen ? el('img', { src: m.imagen, alt: 'Foto enviada' }) : null, m.texto));
      }));
      if (abajo || lista.length <= 1) mensajes.scrollTop = mensajes.scrollHeight;
    });
  }

  async function pintarDonacion() {
    if (!conversacion || !conversacion.donacion_id) {
      pintor.pintar('donacion', null, () => {
        llenar(panelDonacion, el('p', { class: 'vacio' }, 'Cuando confirmes tu donación aquí verás su avance en tiempo real.'));
      });
      return;
    }
    const d = await ctx.api.get(`/donaciones/${conversacion.donacion_id}`);
    pintor.pintar('donacion', d, () => {
      llenar(panelDonacion, 
        el('div', { class: 'fila espacio' }, el('b', null, `Donación #${d.id}`), chipEstado(d.estado)),
        el('p', { class: 'sub', style: 'margin:.4rem 0' }, `${textoItems(d.items)} · ${fmtKg(d.total_kg)}`),
        pasosDe(d),
        d.receptor ? el('p', { style: 'margin-top:.6rem' }, 'Receptor: ', el('b', null, d.receptor.nombre)) : null,
        el('div', { style: 'margin-top:.75rem' },
          el('button', { class: 'boton', type: 'button', onclick: () => ctx.ir('seguimiento', d.id) }, 'Ver seguimiento completo')));
    });
  }

  return {
    async activar() {
      llenarDonantes();
      if (!conversacion || conversacion.donante.id !== donanteId) await nuevaConversacion();
      await this.refrescar();
    },
    async refrescar() {
      if (!conversacion) return;
      if (!enviando) {
        try { conversacion = await ctx.api.get(`/conversaciones/${conversacion.id}`); }
        catch { await nuevaConversacion(true); }
        pintar();
      }
      await pintarDonacion();
    },
    reiniciado() { conversacion = null; pintor.olvidar(); },
  };
}
