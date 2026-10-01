#!/usr/bin/env node
// Design-token lint: fails on anything that steps outside the Stitch design system
// (DESIGN.md, AGENTS.md). Dependency-free; run with: npm run lint:tokens

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

/**
 * Files that may break the rules on purpose. The generated asset list holds the logo's own colours
 * for non-CSS contexts (Part 0D); manifest.ts reads them from it, so it needs no entry itself.
 */
export const ALLOWLIST = ["src/lib/brand-assets.json"];

const PALETTE = [
  "slate",
  "gray",
  "zinc",
  "neutral",
  "stone",
  "red",
  "orange",
  "amber",
  "yellow",
  "lime",
  "green",
  "emerald",
  "teal",
  "cyan",
  "sky",
  "blue",
  "indigo",
  "violet",
  "purple",
  "fuchsia",
  "pink",
  "rose",
].join("|");

const COLOR_UTILITIES =
  "bg|text|border(?:-[xytblrse])?|ring|ring-offset|fill|stroke|divide|outline|decoration|from|via|to|placeholder|accent|caret|shadow|inset-shadow|drop-shadow";

// A utility sits at the start of a token: after whitespace, a quote, a backtick or a variant colon.
const START = String.raw`(?<![\w-])`;
const VARIANTS = String.raw`(?:(?:[a-z0-9-]+|\[[^\]\s]+\]):)*`;
const END = String.raw`(?![\w-])`;
const SANCTIONED_ICON_SIZES = new Set([
  "0.75rem",
  "0.875rem",
  "1rem",
  "1.125rem",
  "1.25rem",
  "1.5rem",
  "2rem",
]);

/** Removes comments so prose such as "rounded corners" is not mistaken for a class. */
function stripComments(text, isCss) {
  const blank = (m) => m.replace(/[^\n]/g, " ");
  let out = text.replace(/\/\*[\s\S]*?\*\//g, blank);
  if (!isCss) {
    // Line comments, but not the // in a URL. \x5c is a backslash.
    out = out.replace(
      /(^|[^:"'`\x5c])\/\/[^\n]*/g,
      (m, before) => before + blank(m.slice(before.length)),
    );
  }
  return out;
}

/** Drops the @theme block, the one place raw colour values live. */
function stripThemeBlock(css) {
  const start = css.search(/@theme\b/);
  if (start === -1) return css;
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") {
      depth -= 1;
      if (depth === 0) return css.slice(0, start) + css.slice(i + 1);
    }
  }
  return css;
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

const utility = (body) => new RegExp(START + VARIANTS + "(" + body + ")" + END, "g");

/**
 * @param {string} source
 * @param {string} file
 * @returns {{file: string, line: number, rule: string, match: string}[]}
 */
export function lintSource(source, file) {
  const isCss = file.endsWith(".css");
  let text = stripComments(source, isCss);
  if (isCss) text = stripThemeBlock(text);
  const found = [];

  const scan = (regex, rule, accept) => {
    for (const m of text.matchAll(regex)) {
      const token = m[1] ?? m[0];
      if (accept?.(token, m)) continue;
      found.push({ file, line: lineOf(text, m.index), rule, match: token });
    }
  };

  scan(
    /(?<![\w&-])(#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4}))(?![\w-])/g,
    "raw hex colour",
  );

  scan(
    utility(String.raw`(?:${COLOR_UTILITIES})-(?:${PALETTE})(?:-\d{2,3})?(?:/\d+)?`),
    "Tailwind default palette colour",
  );
  scan(
    utility(String.raw`(?:${COLOR_UTILITIES})-(?:white|black)(?:/\d+)?`),
    "Tailwind default white/black",
  );
  scan(
    new RegExp(
      START +
        VARIANTS +
        String.raw`((?:${COLOR_UTILITIES})-\[\s*(?:#|rgba?\(|hsla?\(|oklch\(|oklab\(|lab\(|lch\(|color:|color-mix\()[^\]]*\])`,
      "g",
    ),
    "arbitrary colour value",
  );

  // Only rounded-lg and rounded-full exist in this design.
  scan(
    new RegExp(
      START + VARIANTS + String.raw`(rounded(?:-[a-z0-9]+)*(?:-\[[^\]]*\])?)(?![\w\[-])`,
      "g",
    ),
    "radius other than rounded-lg / rounded-full",
    (token) => token === "rounded-lg" || token === "rounded-full",
  );

  // shadow-sm is the only shadow.
  scan(
    new RegExp(
      START +
        VARIANTS +
        String.raw`((?:drop-|inset-|text-)?shadow(?:-[\w./\[\]#(),%-]+)?)(?![\w\[-])`,
      "g",
    ),
    "shadow other than shadow-sm",
    (token) => token === "shadow-sm" || token === "shadow-none",
  );

  // Generic type sizes and families; arbitrary sizes only from the icon scale.
  scan(utility(String.raw`text-(?:xs|sm|base|lg|xl|[2-9]xl)`), "generic Tailwind text size");
  scan(utility(String.raw`font-(?:sans|serif|mono)`), "generic font family");
  scan(
    new RegExp(START + VARIANTS + String.raw`(text-\[(\d+(?:\.\d+)?(?:px|rem|em))\])`, "g"),
    "arbitrary text size outside the icon scale",
    (_token, m) => SANCTIONED_ICON_SIZES.has(m[2]),
  );

  scan(/\b(dangerouslySetInnerHTML)\b/g, "dangerouslySetInnerHTML (user content is plain text)");

  return found.sort((a, b) => a.line - b.line);
}

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(?:ts|tsx|js|jsx|mjs|css|json)$/.test(entry.name)) out.push(full);
  }
  return out;
}

/** @param {string} root directory that contains src/ */
export function lintDirectory(root, allowlist = ALLOWLIST) {
  const violations = [];
  for (const full of walk(path.join(root, "src"))) {
    const rel = path.relative(root, full).split(path.sep).join("/");
    if (allowlist.includes(rel)) continue;
    violations.push(...lintSource(fs.readFileSync(full, "utf8"), rel));
  }
  return violations;
}

const invokedDirectly = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (invokedDirectly) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const violations = lintDirectory(root);
  if (violations.length === 0) {
    console.log("lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)");
  } else {
    for (const v of violations) console.error(`${v.file}:${v.line}  ${v.rule}: ${v.match}`);
    console.error(`\nlint:tokens found ${violations.length} problem(s).`);
    process.exit(1);
  }
}
