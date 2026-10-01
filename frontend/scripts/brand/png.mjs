// Minimal PNG header reader, so size checks need no extra dependency.

const SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

export const PNG_COLOR_TYPE = { greyscale: 0, rgb: 2, palette: 3, greyscaleAlpha: 4, rgba: 6 };

/** @param {Buffer} buffer @returns {{width: number, height: number, bitDepth: number, colorType: number}} */
export function readPngInfo(buffer) {
  if (buffer.length < 26 || !buffer.subarray(0, 8).equals(SIGNATURE)) {
    throw new Error("Not a PNG file");
  }
  if (buffer.toString("ascii", 12, 16) !== "IHDR") throw new Error("PNG is missing its IHDR chunk");
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
    bitDepth: buffer[24],
    colorType: buffer[25],
  };
}

/** True when the PNG has no alpha channel at all (colour type 0, 2 or 3 without tRNS is not checked). */
export function isOpaquePng(buffer) {
  const { colorType } = readPngInfo(buffer);
  return colorType === PNG_COLOR_TYPE.greyscale || colorType === PNG_COLOR_TYPE.rgb;
}
