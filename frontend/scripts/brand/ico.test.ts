// @vitest-environment node
import sharp from "sharp";
import { describe, expect, it } from "vitest";
import { buildIco, readIcoEntries } from "./ico.mjs";
import { isOpaquePng, readPngInfo } from "./png.mjs";

const square = (size: number, background = { r: 40, g: 48, b: 68, alpha: 1 }) =>
  sharp({ create: { width: size, height: size, channels: 4, background } })
    .png()
    .toBuffer();

describe("PNG-in-ICO writer", () => {
  it("writes a header, one directory entry per image and the PNG data", async () => {
    const pngs = await Promise.all([16, 32, 48].map((size) => square(size)));
    const ico = buildIco(pngs);

    expect([ico.readUInt16LE(0), ico.readUInt16LE(2), ico.readUInt16LE(4)]).toEqual([0, 1, 3]);
    const entries = readIcoEntries(ico);
    expect(entries.map((e) => `${e.width}x${e.height}`)).toEqual(["16x16", "32x32", "48x48"]);
    expect(entries.every((e) => e.planes === 1 && e.bitCount === 32)).toBe(true);

    let expectedOffset = 6 + 16 * 3;
    entries.forEach((entry, i) => {
      expect(entry.offset).toBe(expectedOffset);
      expect(entry.size).toBe(pngs[i].length);
      expect(ico.subarray(entry.offset, entry.offset + entry.size).equals(pngs[i])).toBe(true);
      expectedOffset += entry.size;
    });
    expect(ico.length).toBe(expectedOffset);
  });

  it("encodes 256 px as 0 in the directory and reads it back", async () => {
    const ico = buildIco([await square(256)]);
    expect(ico[0 + 6]).toBe(0);
    expect(readIcoEntries(ico)[0].width).toBe(256);
  });

  it("rejects empty input, non-square and oversized images", async () => {
    expect(() => buildIco([])).toThrow(/at least one/);
    const wide = await sharp({ create: { width: 32, height: 16, channels: 4, background: "#000" } })
      .png()
      .toBuffer();
    expect(() => buildIco([wide])).toThrow(/square/);
    expect(() => buildIco([Buffer.from("not a png at all, just text")])).toThrow(/Not a PNG/);
  });
});

describe("PNG header reader", () => {
  it("reads size, depth and colour type without decoding", async () => {
    const rgba = await square(20);
    expect(readPngInfo(rgba)).toMatchObject({ width: 20, height: 20, colorType: 6 });
    expect(isOpaquePng(rgba)).toBe(false);
    const rgb = await sharp(rgba).removeAlpha().png().toBuffer();
    expect(readPngInfo(rgb).colorType).toBe(2);
    expect(isOpaquePng(rgb)).toBe(true);
  });
});
