// Cliente mínimo de la API REST (/api). Los errores del servidor llegan como Error con el detalle en español.

async function llamar(metodo, ruta, cuerpo) {
  const respuesta = await fetch(`/api${ruta}`, {
    method: metodo,
    headers: cuerpo === undefined ? {} : { 'Content-Type': 'application/json' },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  let datos = null;
  try { datos = await respuesta.json(); } catch { /* respuesta sin cuerpo */ }
  if (!respuesta.ok) {
    const detalle = datos && datos.detail;
    const error = new Error(typeof detalle === 'string' ? detalle : 'Los datos enviados no son válidos');
    error.estado = respuesta.status;
    throw error;
  }
  return datos;
}

export const api = {
  get: (ruta) => llamar('GET', ruta),
  post: (ruta, cuerpo = {}) => llamar('POST', ruta, cuerpo),
};
