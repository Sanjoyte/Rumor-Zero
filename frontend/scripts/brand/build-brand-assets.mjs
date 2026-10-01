#!/usr/bin/env node
// Builds every derived logo asset from the single master, design/logo.svg (ARCHITECTURE 14).
//   npm run brand:build                       (from frontend/)
//   npm run brand:build -- --master <file>    (try another master; nothing is written if it is unsafe)
// The script only READS design/. It refuses to write inside the master's folder.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import sharp from "sharp";
import { contrastTable, formatContrastTable } from "./contrast.mjs";
import { buildIco } from "./ico.mjs";
import { readPngInfo } from "./png.mjs";
import {
  BrandError,
  cropToArtwork,
  extractMark,
  measureBounds,
  parseMaster,
  selectMark,
  serializeShapes,
} from "./svg.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_CONFIG = JSON.parse(
  fs.readFileSync(path.join(scriptDir, "brand.config.json"), "utf8"),
);

const fmt = (n) => String(Math.round(n * 100) / 100);

/** A square plate with the mark centred on it. `rounded` leaves the corners transparent. */
function markPlateSvg({ size, fraction, color, radius, mark }) {
  const side = size * fraction;
  const offset = (size - side) / 2;
  const vb = mark.viewBox;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">` +
    `<rect width="${size}" height="${size}" rx="${fmt(size * radius)}" fill="${color}"/>` +
    `<svg x="${fmt(offset)}" y="${fmt(offset)}" width="${fmt(side)}" height="${fmt(side)}" ` +
    `viewBox="${vb.x} ${vb.y} ${vb.w} ${vb.h}">${mark.body}</svg></svg>`
  );
}

/** A rectangular plate with the wordmark centred on it. */
function wordmarkPlateSvg({ width, height, wordmarkWidth, color, wordmark }) {
  const vb = wordmark.viewBox;
  const wmHeight = (wordmarkWidth * vb.h) / vb.w;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    `<rect width="${width}" height="${height}" fill="${color}"/>` +
    `<svg x="${fmt((width - wordmarkWidth) / 2)}" y="${fmt((height - wmHeight) / 2)}" ` +
    `width="${fmt(wordmarkWidth)}" height="${fmt(wmHeight)}" viewBox="${vb.x} ${vb.y} ${vb.w} ${vb.h}">` +
    `${wordmark.body}</svg></svg>`
  );
}

async function renderPng(svg, { opaqueColor } = {}) {
  let image = sharp(Buffer.from(svg));
  if (opaqueColor) image = image.flatten({ background: opaqueColor });
  return image.png({ compressionLevel: 9 }).toBuffer();
}

function isInside(child, parent) {
  const rel = path.relative(path.resolve(parent), path.resolve(child));
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

/**
 * @param {object} options
 * @param {string} options.masterPath absolute path of the master SVG
 * @param {string} options.frontendDir absolute path of frontend/
 * @param {string} options.adminDir absolute folder for logo-admin.png
 * @param {string[]} [options.protectedDirs] folders that must never be written (default: the master's folder)
 * @param {object} [options.config]
 */
export async function buildAll({
  masterPath,
  frontendDir,
  adminDir,
  protectedDirs,
  config = DEFAULT_CONFIG,
}) {
  const protectedFolders = protectedDirs ?? [path.dirname(masterPath)];
  const written = [];

  const writeOut = (target, data) => {
    for (const folder of protectedFolders) {
      if (isInside(target, folder))
        throw new BrandError(`Refusing to write ${target}: it is inside ${folder}.`);
    }
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, data);
    written.push(target);
  };
  const app = (name) => path.join(frontendDir, "src", "app", name);
  const brand = (name) => path.join(frontendDir, "public", "brand", name);

  // 1. Read and check the master (nothing is written if this fails).
  const { viewBox, shapes } = parseMaster(
    fs.readFileSync(masterPath, "utf8"),
    path.basename(masterPath),
  );
  const markShape = selectMark(shapes, config.markSelector);
  const bounds = await measureBounds(shapes, viewBox);
  const markBounds = await measureBounds([markShape], viewBox);

  const wordmark = cropToArtwork(shapes, bounds, config.wordmarkPadding);
  const mark = extractMark(markShape, markBounds, config.markPadding);
  const wordmarkParts = { viewBox: wordmark.viewBox, body: serializeShapes(shapes, "") };
  const markParts = { viewBox: mark.viewBox, body: serializeShapes([markShape], "") };

  const cyan = markShape.attrs.fill.toLowerCase();
  const grey = shapes.map((s) => s.attrs.fill.toLowerCase()).find((f) => f !== cyan);
  if (!grey) throw new BrandError("The logo needs a second colour besides the mark's.");

  const color = config.plateColor;
  const radius = config.roundedRadius;
  const plates = config.plates;

  // 2. SVG assets.
  writeOut(brand("logo.svg"), wordmark.svg);
  writeOut(brand("mark.svg"), mark.svg);
  const iconSvg = markPlateSvg({
    size: 512,
    fraction: plates.icon.markFraction,
    color,
    radius,
    mark: markParts,
  });
  writeOut(app("icon.svg"), `${iconSvg}\n`);

  // 3. Mark plates.
  const markPng = (size, plate, rounded) =>
    renderPng(
      markPlateSvg({
        size,
        fraction: plate.markFraction,
        color,
        radius: rounded ? radius : 0,
        mark: markParts,
      }),
      rounded ? {} : { opaqueColor: color },
    );
  const faviconPngs = [];
  for (const size of config.faviconSizes)
    faviconPngs.push(await markPng(size, plates.favicon, true));
  writeOut(app("favicon.ico"), buildIco(faviconPngs));
  writeOut(brand("icon-192.png"), await markPng(192, plates.icon, true));
  writeOut(brand("icon-512.png"), await markPng(512, plates.icon, true));
  writeOut(
    brand("icon-maskable-512.png"),
    await markPng(plates.maskable.size, plates.maskable, false),
  );
  writeOut(app("apple-icon.png"), await markPng(plates.apple.size, plates.apple, false));

  // 4. Wordmark plates.
  const wordmarkPng = (width, height, wordmarkWidth) =>
    renderPng(wordmarkPlateSvg({ width, height, wordmarkWidth, color, wordmark: wordmarkParts }), {
      opaqueColor: color,
    });
  const share = await wordmarkPng(
    plates.share.width,
    plates.share.height,
    plates.share.width * plates.share.wordmarkWidthFraction,
  );
  writeOut(app("opengraph-image.png"), share);
  writeOut(app("twitter-image.png"), share);
  // No trailing newline: Next copies the file's text verbatim into og:image:alt.
  writeOut(app("opengraph-image.alt.txt"), config.altText);
  writeOut(app("twitter-image.alt.txt"), config.altText);
  writeOut(
    brand("email-logo.png"),
    await wordmarkPng(
      plates.email.width,
      plates.email.height,
      plates.email.width * plates.email.wordmarkWidthFraction,
    ),
  );
  writeOut(
    brand("google-oauth-logo.png"),
    await wordmarkPng(
      plates.google.width,
      plates.google.height,
      plates.google.width * plates.google.wordmarkWidthFraction,
    ),
  );

  const adminHeight = plates.admin.height;
  const adminWordmarkHeight = adminHeight * plates.admin.wordmarkHeightFraction;
  const adminWordmarkWidth = (adminWordmarkHeight * wordmark.viewBox.w) / wordmark.viewBox.h;
  const adminWidth = Math.round(adminWordmarkWidth + (adminHeight - adminWordmarkHeight));
  writeOut(
    path.join(adminDir, "logo-admin.png"),
    await wordmarkPng(adminWidth, adminHeight, adminWordmarkWidth),
  );

  // 5. The asset list that Logo, manifest.ts and the root metadata read.
  const sizeOf = (file) => {
    const { width, height } = readPngInfo(fs.readFileSync(file));
    return { width, height };
  };
  const rel = (file) => path.relative(frontendDir, file).split(path.sep).join("/");
  const png = (file, src, extra = {}) => ({
    file: rel(file),
    ...(src ? { src } : {}),
    ...sizeOf(file),
    ...extra,
  });
  const assets = {
    master: config.master,
    plateColor: color,
    logoColors: { grey, cyan },
    alt: config.altText,
    wordmark: {
      file: "public/brand/logo.svg",
      src: "/brand/logo.svg",
      width: wordmark.viewBox.w,
      height: wordmark.viewBox.h,
    },
    mark: {
      file: "public/brand/mark.svg",
      src: "/brand/mark.svg",
      width: mark.viewBox.w,
      height: mark.viewBox.h,
    },
    favicon: { file: "src/app/favicon.ico", sizes: config.faviconSizes },
    icon: { file: "src/app/icon.svg" },
    appleIcon: png(app("apple-icon.png")),
    icons: [
      { ...png(brand("icon-192.png"), "/brand/icon-192.png"), type: "image/png", purpose: "any" },
      { ...png(brand("icon-512.png"), "/brand/icon-512.png"), type: "image/png", purpose: "any" },
      {
        ...png(brand("icon-maskable-512.png"), "/brand/icon-maskable-512.png"),
        type: "image/png",
        purpose: "maskable",
      },
    ],
    share: png(app("opengraph-image.png")),
    twitter: png(app("twitter-image.png")),
    email: png(brand("email-logo.png"), "/brand/email-logo.png", { displayWidth: 160 }),
    google: png(brand("google-oauth-logo.png"), "/brand/google-oauth-logo.png"),
    admin: { file: config.adminFile, ...sizeOf(path.join(adminDir, "logo-admin.png")) },
  };
  writeOut(
    path.join(frontendDir, "src", "lib", "brand-assets.json"),
    `${JSON.stringify(assets, null, 2)}\n`,
  );

  const contrast = contrastTable({ grey, cyan }, config.contrastSurfaces);
  return { assets, contrast, written };
}

function contrastMatchesDocs(rows, expected) {
  return (
    rows.length === expected.length &&
    rows.every(
      (r, i) =>
        r.surface === expected[i].surface &&
        r.grey === expected[i].grey &&
        r.cyan === expected[i].cyan,
    )
  );
}

async function main() {
  const frontendDir = path.resolve(scriptDir, "..", "..");
  const repoRoot = path.resolve(frontendDir, "..");
  const args = process.argv.slice(2);
  const masterFlag = args.indexOf("--master");
  const masterPath = path.resolve(
    masterFlag === -1 ? path.join(repoRoot, DEFAULT_CONFIG.master) : (args[masterFlag + 1] ?? ""),
  );

  try {
    const { contrast, written } = await buildAll({
      masterPath,
      frontendDir,
      adminDir: path.join(repoRoot, "backend", "apps", "core", "static", "core", "brand"),
      protectedDirs: [path.join(repoRoot, "design"), path.dirname(masterPath)],
    });
    console.log(
      `brand:build read ${path.relative(repoRoot, masterPath)} and wrote ${written.length} files:`,
    );
    for (const file of written)
      console.log(`  ${path.relative(repoRoot, file).split(path.sep).join("/")}`);
    console.log(`\n${formatContrastTable(contrast)}`);
    console.log(
      contrastMatchesDocs(contrast, DEFAULT_CONFIG.expectedContrast)
        ? "\nThe contrast table matches ARCHITECTURE 14."
        : "\nThe contrast table DIFFERS from ARCHITECTURE 14: update that section (the logo colours changed).",
    );
  } catch (error) {
    if (error instanceof BrandError) {
      console.error(`\nbrand:build failed: ${error.message}`);
      process.exit(1);
    }
    throw error;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
