// Reads the master logo SVG: safety check, shape extraction, bounds and the two derived SVGs.
// Dependency-free except for sharp (used only to measure the artwork). No XML library: the master
// is our own outlined artwork, so a small tokenizer is enough and anything it does not understand
// fails loudly instead of being guessed at.

import sharp from "sharp";

export class BrandError extends Error {
  constructor(message, problems = []) {
    super(message);
    this.name = "BrandError";
    this.problems = problems;
  }
}

const FORBIDDEN_ELEMENTS = new Set([
  "script",
  "foreignobject",
  "text",
  "tspan",
  "textpath",
  "image",
  "iframe",
  "embed",
  "object",
  "audio",
  "video",
]);

const SHAPE_ELEMENTS = new Set([
  "path",
  "rect",
  "circle",
  "ellipse",
  "polygon",
  "polyline",
  "line",
]);

/** Attributes copied from a shape into the derived SVGs, in this order. */
const SHAPE_ATTRIBUTES = [
  "d",
  "x",
  "y",
  "width",
  "height",
  "rx",
  "ry",
  "cx",
  "cy",
  "r",
  "points",
  "x1",
  "y1",
  "x2",
  "y2",
  "transform",
  "fill",
  "fill-rule",
  "fill-opacity",
  "opacity",
];

const TAG =
  /<(\/?)([A-Za-z][\w:.-]*)((?:\s+[^\s=/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>"']+))?)*)\s*(\/?)>/y;
const ATTRIBUTE = /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+)))?/g;
const SKIPPED = [/<!--[\s\S]*?-->/y, /<\?[\s\S]*?\?>/y, /<!\[CDATA\[[\s\S]*?\]\]>/y];
const RAW_TEXT_ELEMENTS = new Set(["style", "script"]);

function lineOf(source, index) {
  let line = 1;
  for (let i = 0; i < index; i += 1) if (source.charCodeAt(i) === 10) line += 1;
  return line;
}

function parseAttributes(raw) {
  const attrs = {};
  for (const m of raw.matchAll(ATTRIBUTE)) attrs[m[1]] = m[2] ?? m[3] ?? m[4] ?? "";
  return attrs;
}

/**
 * Splits an SVG into tag tokens. `<style>` and `<script>` content comes back as one raw text token.
 * @returns {{type: "open"|"close"|"text"|"doctype", name: string, attrs: Record<string,string>,
 *            selfClosing: boolean, text: string, index: number, line: number}[]}
 */
export function tokenize(svg) {
  const tokens = [];
  let pos = 0;
  while (pos < svg.length) {
    const lt = svg.indexOf("<", pos);
    if (lt === -1) break;
    pos = lt;

    const skip = SKIPPED.find((re) => {
      re.lastIndex = pos;
      return re.test(svg);
    });
    if (skip) {
      pos = skip.lastIndex;
      continue;
    }

    if (/^<!(?:DOCTYPE|ENTITY)/i.test(svg.slice(pos, pos + 10))) {
      tokens.push({
        type: "doctype",
        name: "doctype",
        attrs: {},
        selfClosing: false,
        text: "",
        index: pos,
        line: lineOf(svg, pos),
      });
      const end = svg.indexOf(">", pos);
      pos = end === -1 ? svg.length : end + 1;
      continue;
    }

    TAG.lastIndex = pos;
    const m = TAG.exec(svg);
    if (!m) {
      throw new BrandError(
        `Malformed SVG near line ${lineOf(svg, pos)}: "${svg.slice(pos, pos + 30)}"`,
      );
    }
    const [whole, slash, rawName, rawAttrs, selfSlash] = m;
    const name = rawName.toLowerCase();
    const token = {
      type: slash ? "close" : "open",
      name,
      attrs: slash ? {} : parseAttributes(rawAttrs),
      selfClosing: Boolean(selfSlash),
      text: "",
      index: pos,
      line: lineOf(svg, pos),
    };
    tokens.push(token);
    pos += whole.length;

    if (token.type === "open" && !token.selfClosing && RAW_TEXT_ELEMENTS.has(name)) {
      const close = svg.toLowerCase().indexOf(`</${name}`, pos);
      const end = close === -1 ? svg.length : close;
      tokens.push({
        type: "text",
        name,
        attrs: {},
        selfClosing: false,
        text: svg.slice(pos, end),
        index: pos,
        line: lineOf(svg, pos),
      });
      pos = end;
    }
  }
  return tokens;
}

/**
 * Lists every reason the master is unsafe or unusable. An empty array means it passed.
 * Forbidden: script, foreignObject, text, embedded bitmaps, on* attributes, external references,
 * DOCTYPE/ENTITY, and a missing viewBox.
 */
export function findSafetyProblems(svg) {
  const problems = [];
  let tokens;
  try {
    tokens = tokenize(svg);
  } catch (error) {
    return [error.message];
  }

  const root = tokens.find((t) => t.type === "open");
  if (!root || root.name !== "svg") problems.push("the file has no <svg> root element");
  else if (!root.attrs.viewBox || !/\S/.test(root.attrs.viewBox)) {
    problems.push("the <svg> root has no viewBox");
  }

  for (const t of tokens) {
    const where = `line ${t.line}`;
    if (t.type === "doctype") problems.push(`DOCTYPE/ENTITY declaration (${where})`);
    if (t.type === "text" && t.name === "style") {
      if (/@import/i.test(t.text)) problems.push(`@import in <style> (${where})`);
      if (/url\(\s*(?!['"]?#)/i.test(t.text)) problems.push(`external url() in <style> (${where})`);
    }
    if (t.type !== "open") continue;
    if (FORBIDDEN_ELEMENTS.has(t.name)) {
      const label = t.name === "foreignobject" ? "<foreignObject>" : `<${t.name}>`;
      problems.push(`${label} element (${where})`);
    }
    for (const [attr, value] of Object.entries(t.attrs)) {
      if (/^on[a-z]/i.test(attr))
        problems.push(`${attr} event attribute on <${t.name}> (${where})`);
      if (/^(?:xlink:)?href$/i.test(attr) && !value.trim().startsWith("#")) {
        problems.push(`external ${attr}="${value.slice(0, 40)}" on <${t.name}> (${where})`);
      }
      if (/data:/i.test(value)) problems.push(`data: URI in ${attr} on <${t.name}> (${where})`);
      if (/javascript:/i.test(value))
        problems.push(`javascript: in ${attr} on <${t.name}> (${where})`);
      if (/url\(\s*(?!['"]?#)/i.test(value)) {
        problems.push(`external url() in ${attr} on <${t.name}> (${where})`);
      }
    }
  }
  return problems;
}

/** Throws a BrandError listing every problem, or returns the tokens when the master is safe. */
export function assertSafe(svg, label = "the logo master") {
  const problems = findSafetyProblems(svg);
  if (problems.length > 0) {
    throw new BrandError(
      `${label} failed the safety check, so nothing was built:\n  - ${problems.join("\n  - ")}`,
      problems,
    );
  }
  return tokenize(svg);
}

/** Only `.class` selectors are supported; anything else makes the build fail. */
export function parseStyles(css) {
  const rules = new Map();
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, selectorList, body] of clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const declarations = {};
    for (const part of body.split(";")) {
      const colon = part.indexOf(":");
      if (colon === -1) continue;
      declarations[part.slice(0, colon).trim()] = part.slice(colon + 1).trim();
    }
    for (const rawSelector of selectorList.split(",")) {
      const selector = rawSelector.trim();
      if (!/^\.[\w-]+$/.test(selector)) {
        throw new BrandError(
          `Unsupported CSS selector "${selector}" in the logo's <style>; use plain classes.`,
        );
      }
      const name = selector.slice(1);
      rules.set(name, { ...(rules.get(name) ?? {}), ...declarations });
    }
  }
  return rules;
}

export function parseViewBox(value) {
  const parts = value
    .trim()
    .split(/[\s,]+/)
    .map(Number);
  if (
    parts.length !== 4 ||
    parts.some((n) => !Number.isFinite(n)) ||
    parts[2] <= 0 ||
    parts[3] <= 0
  ) {
    throw new BrandError(`Invalid viewBox "${value}".`);
  }
  const [x, y, w, h] = parts;
  return { x, y, w, h };
}

/**
 * Safety-checks the master and returns its shapes with the stylesheet resolved into attributes.
 * Groups are flattened, so a group carrying its own styling or transform is rejected.
 * @returns {{viewBox: {x,y,w,h}, shapes: {name: string, classes: string[], attrs: Record<string,string>}[]}}
 */
export function parseMaster(svg, label = "the logo master") {
  const tokens = assertSafe(svg, label);
  const root = tokens.find((t) => t.type === "open");
  const viewBox = parseViewBox(root.attrs.viewBox);

  const styles = parseStyles(
    tokens
      .filter((t) => t.type === "text" && t.name === "style")
      .map((t) => t.text)
      .join("\n"),
  );

  const shapes = [];
  let defsDepth = 0;
  for (const t of tokens) {
    if (t.name === "defs") {
      if (t.type === "open" && !t.selfClosing) defsDepth += 1;
      if (t.type === "close") defsDepth -= 1;
      continue;
    }
    if (t.type !== "open" || defsDepth > 0) continue;

    if (t.name === "g") {
      const styled = Object.keys(t.attrs).filter(
        (a) => !["id", "data-name", "class"].includes(a) && !a.startsWith("xmlns"),
      );
      if (styled.length > 0 || t.attrs.class) {
        throw new BrandError(
          `<g> with ${styled.concat(t.attrs.class ? ["class"] : []).join(", ")} on line ${t.line} is not supported; ungroup or inline it.`,
        );
      }
      continue;
    }
    if (!SHAPE_ELEMENTS.has(t.name)) continue;

    if (t.attrs.style) {
      throw new BrandError(
        `A style="" attribute on line ${t.line} is not supported; use a class or a fill attribute.`,
      );
    }
    const classes = (t.attrs.class ?? "").split(/\s+/).filter(Boolean);
    const resolved = {};
    for (const c of classes) Object.assign(resolved, styles.get(c));

    const attrs = {};
    for (const key of SHAPE_ATTRIBUTES) {
      const value = t.attrs[key] ?? resolved[key];
      if (value !== undefined) attrs[key] = value;
    }
    if (attrs.fill === undefined) {
      throw new BrandError(`Shape <${t.name}> on line ${t.line} has no fill (class or attribute).`);
    }
    shapes.push({ name: t.name, classes, attrs });
  }

  if (shapes.length === 0) throw new BrandError(`${label} contains no shapes.`);
  return { viewBox, shapes };
}

/** `tag.class` only. Exactly one shape must match, otherwise the build fails. */
export function selectMark(shapes, selector) {
  const m = /^([a-z]+)\.([\w-]+)$/.exec(selector);
  if (!m) throw new BrandError(`markSelector "${selector}" must look like "path.cls-1".`);
  const [, tag, cls] = m;
  const matches = shapes.filter((s) => s.name === tag && s.classes.includes(cls));
  if (matches.length !== 1) {
    throw new BrandError(
      `markSelector "${selector}" matched ${matches.length} <${tag}> elements; it must match exactly one ` +
        `(the "0"). The master was probably re-exported with new class names: update ` +
        `scripts/brand/brand.config.json.`,
    );
  }
  return matches[0];
}

const fmt = (n) => String(Math.round(n * 100) / 100);

export function serializeShape(shape) {
  const attrs = Object.entries(shape.attrs)
    .map(([k, v]) => `${k}="${v}"`)
    .join(" ");
  return `<${shape.name} ${attrs}/>`;
}

export function serializeShapes(shapes, indent = "  ") {
  return shapes.map((s) => indent + serializeShape(s)).join("\n");
}

/**
 * Bounding box of the shapes in viewBox units, measured from a 4x render (0.25 unit precision).
 * Measuring pixels handles curve extrema without a path parser.
 */
export async function measureBounds(shapes, viewBox, scale = 4) {
  const width = Math.round(viewBox.w * scale);
  const height = Math.round(viewBox.h * scale);
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}">${serializeShapes(shapes, "")}</svg>`;
  const { data, info } = await sharp(Buffer.from(svg))
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  let minX = info.width;
  let minY = info.height;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < info.height; y += 1) {
    for (let x = 0; x < info.width; x += 1) {
      if (data[(y * info.width + x) * info.channels + 3] < 8) continue;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  if (maxX < 0) throw new BrandError("The logo renders as fully transparent.");
  return {
    x: viewBox.x + minX / scale,
    y: viewBox.y + minY / scale,
    w: (maxX + 1 - minX) / scale,
    h: (maxY + 1 - minY) / scale,
  };
}

function svgDocument(viewBox, body) {
  const vb = `${fmt(viewBox.x)} ${fmt(viewBox.y)} ${fmt(viewBox.w)} ${fmt(viewBox.h)}`;
  return {
    viewBox: { x: +fmt(viewBox.x), y: +fmt(viewBox.y), w: +fmt(viewBox.w), h: +fmt(viewBox.h) },
    svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}">\n${body}\n</svg>\n`,
  };
}

/** The full wordmark with its viewBox cropped to the artwork plus `padding` on every side. */
export function cropToArtwork(shapes, bounds, padding) {
  return svgDocument(
    {
      x: bounds.x - padding,
      y: bounds.y - padding,
      w: bounds.w + 2 * padding,
      h: bounds.h + 2 * padding,
    },
    serializeShapes(shapes),
  );
}

/** The "0" alone in a square viewBox centred on its bounds, `padding` clear on the longer side. */
export function extractMark(markShape, markBounds, padding) {
  const side = Math.max(markBounds.w, markBounds.h) + 2 * padding;
  const cx = markBounds.x + markBounds.w / 2;
  const cy = markBounds.y + markBounds.h / 2;
  return svgDocument(
    { x: cx - side / 2, y: cy - side / 2, w: side, h: side },
    serializeShapes([markShape]),
  );
}

/** Distinct fills of the master, in document order (the grey letters and the cyan "0"). */
export function distinctFills(shapes) {
  return [...new Set(shapes.map((s) => s.attrs.fill.toLowerCase()))];
}
