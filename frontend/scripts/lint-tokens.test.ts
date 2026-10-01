import path from "node:path";
import { describe, expect, it } from "vitest";
import { lintDirectory, lintSource } from "./lint-tokens.mjs";

const rulesFor = (source: string, file = "src/x.tsx") =>
  lintSource(source, file).map((v) => `${v.rule}: ${v.match}`);

describe("lint-tokens: things it must reject", () => {
  it.each([
    ['<div className="bg-blue-500" />', "Tailwind default palette colour: bg-blue-500"],
    ['<div className="hover:text-slate-700" />', "Tailwind default palette colour: text-slate-700"],
    [
      '<div className="md:border-red-200/50" />',
      "Tailwind default palette colour: border-red-200/50",
    ],
    [
      '<div className="has-checked:bg-emerald-50" />',
      "Tailwind default palette colour: bg-emerald-50",
    ],
    ['<div className="bg-white" />', "Tailwind default white/black: bg-white"],
    ['<div className="text-black/80" />', "Tailwind default white/black: text-black/80"],
    ['<div className="bg-[#23b5d8]" />', "arbitrary colour value: bg-[#23b5d8]"],
    ['<div className="text-[rgb(1,2,3)]" />', "arbitrary colour value: text-[rgb(1,2,3)]"],
    ['const c = "#898a8d";', "raw hex colour: #898a8d"],
    ['<div className="rounded" />', "radius other than rounded-lg / rounded-full: rounded"],
    ['<div className="rounded-md" />', "radius other than rounded-lg / rounded-full: rounded-md"],
    ['<div className="rounded-xl" />', "radius other than rounded-lg / rounded-full: rounded-xl"],
    [
      '<div className="rounded-t-lg" />',
      "radius other than rounded-lg / rounded-full: rounded-t-lg",
    ],
    [
      '<div className="rounded-[6px]" />',
      "radius other than rounded-lg / rounded-full: rounded-[6px]",
    ],
    ['<div className="shadow-md" />', "shadow other than shadow-sm: shadow-md"],
    ['<div className="shadow" />', "shadow other than shadow-sm: shadow"],
    ['<div className="hover:shadow-lg" />', "shadow other than shadow-sm: shadow-lg"],
    ['<div className="text-sm" />', "generic Tailwind text size: text-sm"],
    ['<div className="md:text-2xl" />', "generic Tailwind text size: text-2xl"],
    ['<div className="font-sans" />', "generic font family: font-sans"],
    [
      '<div className="text-[13.5px]" />',
      "arbitrary text size outside the icon scale: text-[13.5px]",
    ],
    [
      "<div dangerouslySetInnerHTML={{ __html: x }} />",
      "dangerouslySetInnerHTML (user content is plain text): dangerouslySetInnerHTML",
    ],
  ])("%s", (source, expected) => {
    expect(rulesFor(source)).toContain(expected);
  });

  it("reports the line number", () => {
    const [violation] = lintSource('const a = 1;\nconst b = "bg-blue-500";\n', "src/x.ts");
    expect(violation.line).toBe(2);
    expect(violation.file).toBe("src/x.ts");
  });

  it("rejects raw hex in CSS outside the @theme block", () => {
    const css = "@theme { --color-primary: #006b5f; }\n.x { color: #ff0000; }";
    expect(rulesFor(css, "src/app/globals.css")).toEqual(["raw hex colour: #ff0000"]);
  });
});

describe("lint-tokens: things it must allow", () => {
  it.each([
    '<div className="bg-surface-container-low text-on-surface border-outline-variant/30" />',
    '<div className="bg-primary/10 text-primary hover:bg-on-secondary-container" />',
    '<div className="rounded-lg rounded-full shadow-sm shadow-none" />',
    '<div className="font-claim-headline text-claim-headline font-label-code text-label-badge" />',
    '<div className="text-[0.75rem] text-[0.875rem] text-[1rem] text-[1.125rem] text-[1.25rem] text-[1.5rem] text-[2rem]" />',
    '<div className="text-inverse-on-surface bg-inverse-surface/40 backdrop:bg-inverse-surface/40" />',
    '<div className="focus:ring-secondary/20 peer-checked:bg-tertiary after:rounded-full" />',
    '<div className="px-space-md max-w-modal z-[60] w-[calc(100%-2.5rem)]" />',
    '<div className="text-error bg-error-container text-on-verdict-review" />',
    "<div className=\"after:content-['']\" />",
  ])("%s", (source) => {
    expect(rulesFor(source)).toEqual([]);
  });

  it("ignores words in comments", () => {
    expect(rulesFor("// rounded corners and a shadow, as in #abc\nconst x = 1;")).toEqual([]);
    expect(rulesFor("/* text-sm bg-blue-500 */ const x = 1;")).toEqual([]);
  });

  it("does not treat a URL as a comment", () => {
    expect(rulesFor('const u = "https://example.com"; const c = "bg-blue-500";')).toHaveLength(1);
  });

  it("does not flag CSS custom properties or box-shadow declarations", () => {
    const css = ".a { box-shadow: 0 1px 2px rgb(0 0 0 / 0.05); --shadow-sm: 0 0 #000; }";
    expect(rulesFor(css.replace("#000", "currentColor"), "src/app/globals.css")).toEqual([]);
  });

  it("allows raw hex inside the @theme block of the stylesheet", () => {
    expect(rulesFor("@theme { --color-surface: #faf8ff; }", "src/app/globals.css")).toEqual([]);
  });
});

describe("lint-tokens: the real source tree", () => {
  it("is clean", () => {
    const root = path.resolve(import.meta.dirname, "..");
    expect(lintDirectory(root)).toEqual([]);
  });

  it("scans JSON, so the generated brand colours are only allowed through the allowlist", () => {
    const root = path.resolve(import.meta.dirname, "..");
    const files = lintDirectory(root, []).map((v) => v.file);
    expect(new Set(files)).toEqual(new Set(["src/lib/brand-assets.json"]));
  });

  it("skips allowlisted files", () => {
    const root = path.resolve(import.meta.dirname, "..");
    const all = lintDirectory(root, ["src/lib/brand-assets.json"]);
    expect(all).toEqual([]);
  });
});
