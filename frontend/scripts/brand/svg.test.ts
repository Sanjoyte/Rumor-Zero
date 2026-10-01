// @vitest-environment node
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  BrandError,
  assertSafe,
  cropToArtwork,
  extractMark,
  findSafetyProblems,
  measureBounds,
  parseMaster,
  parseStyles,
  selectMark,
  tokenize,
} from "./svg.mjs";

const repoRoot = path.resolve(import.meta.dirname, "..", "..", "..");
const master = fs.readFileSync(path.join(repoRoot, "design", "logo.svg"), "utf8");

const wrap = (inner: string, attrs = 'viewBox="0 0 10 10"') =>
  `<svg xmlns="http://www.w3.org/2000/svg" ${attrs}>${inner}</svg>`;

describe("SVG safety check", () => {
  it("accepts the real master", () => {
    expect(findSafetyProblems(master)).toEqual([]);
  });

  it.each([
    ["<script>", wrap("<script>alert(1)</script>"), "<script> element"],
    ["<foreignObject>", wrap("<foreignObject><div/></foreignObject>"), "<foreignObject> element"],
    ["<text>", wrap('<text x="1" y="1">Hi</text>'), "<text> element"],
    ["an on* attribute", wrap('<path d="M0 0h1" onload="x()"/>'), "onload event attribute"],
    [
      "an uppercase on* attribute",
      wrap('<path d="M0 0h1" onClick="x()"/>'),
      "onClick event attribute",
    ],
    ["an external href", wrap('<use href="https://evil.example/a.svg#x"/>'), "external href"],
    [
      "an external xlink:href",
      wrap('<use xlink:href="//evil.example/a.svg#x"/>'),
      "external xlink:href",
    ],
    [
      "an embedded bitmap element",
      wrap('<image href="#a" width="1" height="1"/>'),
      "<image> element",
    ],
    ["a data: URI", wrap('<path d="M0 0" fill="url(data:image/png;base64,AAAA)"/>'), "data: URI"],
    [
      "a javascript: URL",
      wrap('<a href="javascript:alert(1)"><path d="M0 0"/></a>'),
      "javascript:",
    ],
    [
      "an external url() in a style block",
      wrap("<style>.a{fill:url(https://x.example/p)}</style>"),
      "external url() in <style>",
    ],
    ["an @import", wrap('<style>@import "https://x.example/a.css";</style>'), "@import in <style>"],
    ["a DOCTYPE", `<!DOCTYPE svg [<!ENTITY a "b">]>${wrap("")}`, "DOCTYPE/ENTITY"],
    ["a missing viewBox", wrap('<path d="M0 0h1"/>', ""), "no viewBox"],
    ["a different root element", "<html><body/></html>", "no <svg> root"],
  ])("rejects %s", (_name, svg, expected) => {
    expect(findSafetyProblems(svg).join("\n")).toContain(expected);
  });

  it("allows an internal #fragment href", () => {
    expect(findSafetyProblems(wrap('<use href="#a"/>'))).toEqual([]);
  });

  it("reports every problem at once, with line numbers, in one clear message", () => {
    const svg = wrap('<script>x</script>\n<text>y</text>\n<use href="http://x.example/a"/>');
    expect(() => assertSafe(svg, "evil.svg")).toThrow(BrandError);
    try {
      assertSafe(svg, "evil.svg");
    } catch (error) {
      const message = (error as Error).message;
      expect(message).toContain("evil.svg failed the safety check, so nothing was built");
      expect(message).toContain("<script> element (line 1)");
      expect(message).toContain("<text> element (line 2)");
      expect(message).toContain("external href");
    }
  });

  it("reports malformed markup instead of guessing", () => {
    expect(findSafetyProblems("<svg viewBox='0 0 1 1'><path d='M0'</svg>").join("")).toContain(
      "Malformed SVG",
    );
  });
});

describe("tokenizer", () => {
  it("keeps <style> content as one raw token and skips comments", () => {
    const tokens = tokenize(
      '<svg><!-- <script> --><style>.a > b { fill: red }</style><path d="M0 0"/></svg>',
    );
    expect(tokens.map((t) => `${t.type}:${t.name}`)).toEqual([
      "open:svg",
      "open:style",
      "text:style",
      "close:style",
      "open:path",
      "close:svg",
    ]);
    expect(tokens[2].text).toBe(".a > b { fill: red }");
  });

  it("reads single-quoted, double-quoted and unquoted attributes", () => {
    const [tag] = tokenize("<path d='M0 0' fill=\"red\" opacity=1 hidden/>");
    expect(tag.attrs).toEqual({ d: "M0 0", fill: "red", opacity: "1", hidden: "" });
    expect(tag.selfClosing).toBe(true);
  });
});

describe("stylesheet", () => {
  it("resolves class rules and merges repeated ones", () => {
    const rules = parseStyles(".cls-1, .cls-2 { stroke-width: 0px; } .cls-1 { fill: #23b5d8; }");
    expect(rules.get("cls-1")).toEqual({ "stroke-width": "0px", fill: "#23b5d8" });
    expect(rules.get("cls-2")).toEqual({ "stroke-width": "0px" });
  });

  it("fails on selectors it does not understand", () => {
    expect(() => parseStyles("svg path { fill: red }")).toThrow(/Unsupported CSS selector/);
  });
});

describe("the real master", () => {
  const parsed = parseMaster(master, "logo.svg");

  it("has 5 paths and the underline, with fills inlined and no class left", () => {
    expect(parsed.viewBox).toEqual({ x: 0, y: 0, w: 1000, h: 1000 });
    expect(parsed.shapes.map((s) => s.name)).toEqual([
      "path",
      "path",
      "path",
      "path",
      "path",
      "rect",
    ]);
    expect(parsed.shapes.map((s) => s.attrs.fill)).toEqual([
      "#898a8d",
      "#898a8d",
      "#898a8d",
      "#23b5d8",
      "#898a8d",
      "#23b5d8",
    ]);
    for (const shape of parsed.shapes) expect(shape.attrs).not.toHaveProperty("class");
  });

  it('finds the "0" with the configured selector, and only it', () => {
    const mark = selectMark(parsed.shapes, "path.cls-1");
    expect(mark.attrs.fill).toBe("#23b5d8");
    expect(mark.name).toBe("path");
  });

  it("fails when the selector matches nothing or more than one shape", () => {
    expect(() => selectMark(parsed.shapes, "path.cls-9")).toThrow(/matched 0 <path> elements/);
    expect(() => selectMark(parsed.shapes, "path.cls-2")).toThrow(/matched 4 <path> elements/);
    expect(() => selectMark(parsed.shapes, "rect.cls-1")).not.toThrow();
    expect(() => selectMark(parsed.shapes, "#zero")).toThrow(/must look like/);
  });

  it("measures the artwork to within 0.5 unit of ARCHITECTURE 14", async () => {
    const bounds = await measureBounds(parsed.shapes, parsed.viewBox);
    expect(bounds.x).toBeCloseTo(121.4, 0);
    expect(Math.abs(bounds.x - 121.4)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(bounds.x + bounds.w - 878.6)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(bounds.y - 413.0)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(bounds.y + bounds.h - 625.7)).toBeLessThanOrEqual(0.5);
  });

  it('measures the "0" to within 0.5 unit of ARCHITECTURE 14', async () => {
    const mark = selectMark(parsed.shapes, "path.cls-1");
    const bounds = await measureBounds([mark], parsed.viewBox);
    expect(Math.abs(bounds.x - 664.4)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(bounds.x + bounds.w - 779.2)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(bounds.y - 413.0)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(bounds.y + bounds.h - 584.9)).toBeLessThanOrEqual(0.5);
  });
});

describe("derived SVGs", () => {
  const shapes = [
    { name: "path", classes: ["a"], attrs: { d: "M0 0h10v10z", fill: "#111111" } },
    {
      name: "rect",
      classes: [],
      attrs: { x: "1", y: "2", width: "3", height: "4", fill: "#222222" },
    },
  ];

  it("crops the wordmark viewBox to the artwork plus padding on every side", () => {
    const { svg, viewBox } = cropToArtwork(shapes, { x: 100, y: 200, w: 300, h: 80 }, 12);
    expect(viewBox).toEqual({ x: 88, y: 188, w: 324, h: 104 });
    expect(svg).toContain('viewBox="88 188 324 104"');
    expect(svg).toContain('<path d="M0 0h10v10z" fill="#111111"/>');
    expect(svg).not.toMatch(/<style|class=/);
  });

  it("puts the mark in a square viewBox centred on it, with only that shape", () => {
    const { svg, viewBox } = extractMark(shapes[0], { x: 664, y: 413, w: 115, h: 172 }, 12);
    expect(viewBox.w).toBe(viewBox.h);
    expect(viewBox.w).toBe(196);
    expect(viewBox.x + viewBox.w / 2).toBeCloseTo(664 + 115 / 2, 5);
    expect(viewBox.y + viewBox.h / 2).toBeCloseTo(413 + 172 / 2, 5);
    expect(svg.match(/<(path|rect)/g)).toEqual(["<path"]);
  });

  it("produces SVGs that pass their own safety check", () => {
    const { svg } = cropToArtwork(shapes, { x: 0, y: 0, w: 10, h: 10 }, 1);
    expect(findSafetyProblems(svg)).toEqual([]);
  });
});
