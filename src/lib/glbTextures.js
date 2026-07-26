const GLB_MAGIC = 0x46546c67;
const JSON_CHUNK = 0x4e4f534a;
const BIN_CHUNK = 0x004e4942;

export function parseGlbChunks(arrayBuffer) {
  if (!(arrayBuffer instanceof ArrayBuffer) || arrayBuffer.byteLength < 20) return {};
  const view = new DataView(arrayBuffer);
  if (view.getUint32(0, true) !== GLB_MAGIC) return {};

  let offset = 12;
  let json = null;
  let bin = null;
  while (offset + 8 <= arrayBuffer.byteLength) {
    const length = view.getUint32(offset, true);
    const type = view.getUint32(offset + 4, true);
    offset += 8;
    if (length < 0 || offset + length > arrayBuffer.byteLength) return {};
    const chunk = arrayBuffer.slice(offset, offset + length);
    offset += length;
    if (type === JSON_CHUNK) {
      try {
        json = JSON.parse(new TextDecoder().decode(chunk).replace(/\0+$/g, '').trim());
      } catch {
        return {};
      }
    } else if (type === BIN_CHUNK) {
      bin = chunk;
    }
  }
  return { json, bin };
}

export function embeddedBaseColorImage(arrayBuffer) {
  const { json, bin } = parseGlbChunks(arrayBuffer);
  const baseTextureIndex = json?.materials?.find(
    (material) => material?.pbrMetallicRoughness?.baseColorTexture
  )?.pbrMetallicRoughness?.baseColorTexture?.index;
  const texture = json?.textures?.[baseTextureIndex];
  const imageIndex = texture?.extensions?.KHR_texture_basisu?.source ?? texture?.source;
  const image = json?.images?.[imageIndex];
  const view = json?.bufferViews?.[image?.bufferView];
  const start = view?.byteOffset || 0;
  if (!bin || !image || !view || !Number.isInteger(view.byteLength) || view.byteLength <= 0) return null;
  if (start < 0 || start + view.byteLength > bin.byteLength) return null;
  return {
    bytes: bin.slice(start, start + view.byteLength),
    mimeType: image.mimeType || 'image/png',
  };
}
