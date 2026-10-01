// @vitest-environment node
// Checks the COMMITTED generated assets against the sizes in task.md / ARCHITECTURE 14.
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { describe, expect, it } from "vitest";
import config from "./brand.config.json";
import { readIcoEntries } from "./ico.mjs";
import { isOpaquePng, readPngInfo } from "./png.mjs";

const frontend = path.resolve(import.meta.dirname, "..", "..");
const repoRoot = path.dirname(frontend);
const read = (...parts: string[]) => fs.readFileSync(path.join(frontend, ...parts));
const pngInfo = (...parts: string[]) => readPngInfo(read(...parts));
const adminLogo = path.join(
  repoRoot,
  "backend",
  "apps",
  "core",
  "static",
  "core",
  "brand",
  "logo-admin.png",
);

describe("generated brand assets: exact sizes", () => {
  it("favicon.ico holds 16, 32 and 48", () => {
    const entries = readIcoEntries(read("src", "app", "favicon.ico"));
    expect(entries.map((e) => e.width)).toEqual([16, 32, 48]);
    expect(entries.map((e) => e.height)).toEqual([16, 32, 48]);
  });

  it("apple-icon is 180x180 and opaque", () => {
    const buffer = read("src", "app", "apple-icon.png");
    expect(readPngInfo(buffer)).toMatchObject({ width: 180, height: 180 });
    expect(isOpaquePng(buffer)).toBe(true);
  });

  it("the manifest icons are 192, 512 and a maskable 512", () => {
    expect(pngInfo("public", "brand", "icon-192.png")).toMatchObject({ width: 192, height: 192 });
    expect(pngInfo("public", "brand", "icon-512.png")).toMatchObject({ width: 512, height: 512 });
    expect(pngInfo("public", "brand", "icon-maskable-512.png")).toMatchObject({
      width: 512,
      height: 512,
    });
  });

  it("the maskable icon is a full-bleed plate with the mark inside the 80 % safe zone", async () => {
    const { data, info } = await sharp(read("public", "brand", "icon-maskable-512.png"))
      .removeAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });
    const hex = config.plateColor.slice(1);
    const plate = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
    const safeRadius = 0.4 * info.width;
    const centre = info.width / 2;

    let markPixels = 0;
    for (let y = 0; y < info.height; y += 1) {
      for (let x = 0; x < info.width; x += 1) {
        const at = (y * info.width + x) * info.channels;
        const isPlate = [0, 1, 2].every((c) => data[at + c] === plate[c]);
        if (x === 0 || y === 0 || x === info.width - 1 || y === info.height - 1) {
          expect(isPlate, `edge pixel ${x},${y} must be plate`).toBe(true);
        }
        if (isPlate) continue;
        markPixels += 1;
        const distance = Math.hypot(x + 0.5 - centre, y + 0.5 - centre);
        expect(distance, `mark pixel ${x},${y}`).toBeLessThanOrEqual(safeRadius);
      }
    }
    expect(markPixels).toBeGreaterThan(5000);
  });

  it("the rounded icons have transparent corners", async () => {
    const { data, info } = await sharp(read("public", "brand", "icon-192.png"))
      .raw()
      .toBuffer({ resolveWithObject: true });
    expect(info.channels).toBe(4);
    expect(data[3]).toBe(0); // top-left pixel alpha
    const middle = (Math.floor(info.height / 2) * info.width + 4) * 4;
    expect(data[middle + 3]).toBe(255);
  });

  it("the share images are 1200x630 (static, with alt text)", () => {
    expect(pngInfo("src", "app", "opengraph-image.png")).toMatchObject({
      width: 1200,
      height: 630,
    });
    expect(pngInfo("src", "app", "twitter-image.png")).toMatchObject({ width: 1200, height: 630 });
    expect(read("src", "app", "opengraph-image.alt.txt").toString()).toBe("Rumor Zero");
    expect(read("src", "app", "twitter-image.alt.txt").toString()).toBe("Rumor Zero");
  });

  it("the Google logo is 120x120 and under 1 MB", () => {
    const buffer = read("public", "brand", "google-oauth-logo.png");
    expect(readPngInfo(buffer)).toMatchObject({ width: 120, height: 120 });
    expect(buffer.length).toBeLessThan(1024 * 1024);
  });

  it("the email logo is 320 px wide and the admin logo is 64 px tall", () => {
    expect(pngInfo("public", "brand", "email-logo.png").width).toBe(320);
    expect(readPngInfo(fs.readFileSync(adminLogo)).height).toBe(64);
  });

  it("the wordmark and mark SVGs are text files with a viewBox and no style block", () => {
    for (const name of ["logo.svg", "mark.svg"]) {
      const svg = read("public", "brand", name).toString("utf8");
      expect(svg).toMatch(/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="[-\d. ]+">/);
      expect(svg).not.toMatch(/<style|<script|<text|<image|href=/);
      expect(svg).not.toContain("\r");
    }
    const icon = read("src", "app", "icon.svg").toString("utf8");
    expect(icon).toContain('viewBox="0 0 512 512"');
  });
});

describe("brand-assets.json", () => {
  const assets = JSON.parse(read("src", "lib", "brand-assets.json").toString("utf8"));

  it("has the documented shape", () => {
    expect(Object.keys(assets)).toEqual([
      "master",
      "plateColor",
      "logoColors",
      "alt",
      "wordmark",
      "mark",
      "favicon",
      "icon",
      "appleIcon",
      "icons",
      "share",
      "twitter",
      "email",
      "google",
      "admin",
    ]);
    expect(assets.master).toBe("design/logo.svg");
    expect(assets.plateColor).toBe(config.plateColor);
    expect(assets.logoColors).toEqual({ grey: "#898a8d", cyan: "#23b5d8" });
    expect(assets.alt).toBe("Rumor Zero");
    expect(assets.wordmark).toMatchObject({ src: "/brand/logo.svg" });
    expect(assets.mark).toMatchObject({ src: "/brand/mark.svg" });
    expect(assets.mark.width).toBe(assets.mark.height);
    expect(assets.wordmark.width / assets.wordmark.height).toBeGreaterThan(3);
    expect(assets.favicon.sizes).toEqual([16, 32, 48]);
    expect(assets.icons.map((i: { purpose: string }) => i.purpose)).toEqual([
      "any",
      "any",
      "maskable",
    ]);
    expect(assets.email.displayWidth).toBe(160);
  });

  it("describes files that exist, with the sizes their headers report", () => {
    const files: { file: string; width?: number; height?: number }[] = [
      assets.wordmark,
      assets.mark,
      assets.favicon,
      assets.icon,
      assets.appleIcon,
      ...assets.icons,
      assets.share,
      assets.twitter,
      assets.email,
      assets.google,
      assets.admin,
    ];
    for (const entry of files) {
      const full = path.join(
        repoRoot,
        entry.file.startsWith("backend/") ? entry.file : path.join("frontend", entry.file),
      );
      expect(fs.existsSync(full), entry.file).toBe(true);
      if (entry.file.endsWith(".png")) {
        expect(readPngInfo(fs.readFileSync(full)), entry.file).toMatchObject({
          width: entry.width,
          height: entry.height,
        });
      }
    }
  });

  it("serves every public asset from /brand/", () => {
    for (const entry of [
      assets.wordmark,
      assets.mark,
      ...assets.icons,
      assets.email,
      assets.google,
    ]) {
      expect(entry.src).toBe(`/${entry.file.replace(/^public\//, "")}`);
    }
  });
});
