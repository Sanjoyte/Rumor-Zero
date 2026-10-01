// Writes a PNG-in-ICO file (supported by every browser since IE 11 / Vista).
import { readPngInfo } from "./png.mjs";

const HEADER_SIZE = 6;
const ENTRY_SIZE = 16;

/**
 * @param {Buffer[]} pngs square PNGs of at most 256 px, in the order they should appear
 * @returns {Buffer}
 */
export function buildIco(pngs) {
  if (pngs.length === 0) throw new Error("An ICO needs at least one image");
  const infos = pngs.map((png) => readPngInfo(png));
  for (const { width, height } of infos) {
    if (width !== height || width > 256)
      throw new Error(`ICO images must be square and <= 256 px, got ${width}x${height}`);
  }

  const header = Buffer.alloc(HEADER_SIZE);
  header.writeUInt16LE(0, 0); // reserved
  header.writeUInt16LE(1, 2); // type: icon
  header.writeUInt16LE(pngs.length, 4);

  let offset = HEADER_SIZE + ENTRY_SIZE * pngs.length;
  const entries = pngs.map((png, i) => {
    const entry = Buffer.alloc(ENTRY_SIZE);
    const { width, height } = infos[i];
    entry[0] = width === 256 ? 0 : width;
    entry[1] = height === 256 ? 0 : height;
    entry[2] = 0; // palette colours
    entry[3] = 0; // reserved
    entry.writeUInt16LE(1, 4); // colour planes
    entry.writeUInt16LE(32, 6); // bits per pixel
    entry.writeUInt32LE(png.length, 8);
    entry.writeUInt32LE(offset, 12);
    offset += png.length;
    return entry;
  });

  return Buffer.concat([header, ...entries, ...pngs]);
}

/** Reads the directory of an ICO file (used by tests). */
export function readIcoEntries(buffer) {
  if (buffer.readUInt16LE(0) !== 0 || buffer.readUInt16LE(2) !== 1)
    throw new Error("Not an ICO file");
  const count = buffer.readUInt16LE(4);
  return Array.from({ length: count }, (_, i) => {
    const at = HEADER_SIZE + i * ENTRY_SIZE;
    return {
      width: buffer[at] || 256,
      height: buffer[at + 1] || 256,
      planes: buffer.readUInt16LE(at + 4),
      bitCount: buffer.readUInt16LE(at + 6),
      size: buffer.readUInt32LE(at + 8),
      offset: buffer.readUInt32LE(at + 12),
    };
  });
}
