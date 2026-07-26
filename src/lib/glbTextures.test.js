import assert from 'node:assert/strict';
import test from 'node:test';
import { embeddedBaseColorImage, parseGlbChunks } from './glbTextures.js';

function glb(document, binary) {
  const json = Buffer.from(JSON.stringify(document));
  const jsonPadding = Buffer.alloc((4 - (json.length % 4)) % 4, 0x20);
  const binPadding = Buffer.alloc((4 - (binary.length % 4)) % 4);
  const jsonChunk = Buffer.concat([json, jsonPadding]);
  const binChunk = Buffer.concat([binary, binPadding]);
  const jsonHeader = Buffer.alloc(8);
  jsonHeader.writeUInt32LE(jsonChunk.length, 0);
  jsonHeader.writeUInt32LE(0x4e4f534a, 4);
  const binHeader = Buffer.alloc(8);
  binHeader.writeUInt32LE(binChunk.length, 0);
  binHeader.writeUInt32LE(0x004e4942, 4);
  const chunks = Buffer.concat([jsonHeader, jsonChunk, binHeader, binChunk]);
  const header = Buffer.alloc(12);
  header.write('glTF');
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + chunks.length, 8);
  const result = Buffer.concat([header, chunks]);
  return result.buffer.slice(result.byteOffset, result.byteOffset + result.byteLength);
}

test('extracts the embedded base-color image used by Paint GLBs', () => {
  const image = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
  const document = {
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: image.length }],
    images: [{ bufferView: 0, mimeType: 'image/png' }],
    textures: [{ source: 0 }],
    materials: [{ pbrMetallicRoughness: { baseColorTexture: { index: 0 } } }],
  };
  const result = embeddedBaseColorImage(glb(document, image));
  assert.equal(result.mimeType, 'image/png');
  assert.deepEqual(Buffer.from(result.bytes), image);
});

test('fails closed for malformed GLB chunks', () => {
  assert.deepEqual(parseGlbChunks(new ArrayBuffer(8)), {});
  const malformed = new ArrayBuffer(24);
  const view = new DataView(malformed);
  view.setUint32(0, 0x46546c67, true);
  view.setUint32(12, 1000, true);
  assert.deepEqual(parseGlbChunks(malformed), {});
});
