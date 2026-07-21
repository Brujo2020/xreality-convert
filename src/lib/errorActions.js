export function nextActionForError(message = '', mode = 'image3d') {
  const text = message.toLowerCase();
  if (/espacio insuficiente|gb libres/.test(text)) return 'Libera espacio local o cambia el destino antes de reintentar.';
  if (/modelo.*not found|no such model|pull/.test(text)) return 'Instala el modelo desde el panel de fuente y vuelve a generar.';
  if (/ollama|reconectando|not running|serve/.test(text)) return 'Comprueba servicios locales y espera a que Ollama aparezca como listo.';
  if (/servidor 3d|hunyuan|motor 3d|engine/.test(text)) return 'Inicializa el motor 3D y espera el estado Disponible.';
  if (/calidad|rechazado|crit/i.test(message)) return 'Cambia la referencia, usa más margen o baja el presupuesto de entrega.';
  if (/selecciona|referencia/.test(text) && mode === 'image3d') return 'Selecciona o arrastra una imagen PNG, JPG o WEBP.';
  if (/prompt|dirección|describe/.test(text)) return 'Escribe una descripción concreta y vuelve a ejecutar.';
  return 'Revisa la entrada activa y vuelve a intentar el flujo.';
}
