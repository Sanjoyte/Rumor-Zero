// Guard (AGENTS.md, ARCHITECTURE 14): the brand is shown only through <Logo/>.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(import.meta.dirname, "..");

/** The only files that may know where the brand files live. */
const BRAND_AWARE = new Set([
  "components/ui/Logo.tsx",
  "components/ui/Logo.test.tsx",
  "lib/brand-assets.json",
  "lib/brand-guard.test.ts",
  "app/manifest.ts",
  "app/manifest.test.ts",
  // `/p/[id]` must name the static share images itself: a page-level `openGraph` replaces the root
  // layout's, images included (Part 5; ARCHITECTURE §10).
  "features/posts/post-metadata.ts",
  "features/posts/post-metadata.test.ts",
]);

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) sourceFiles(full, out);
    else if (/\.(?:ts|tsx|css|mjs|js)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const files = sourceFiles(SRC).map((full) => ({
  rel: path.relative(SRC, full).split(path.sep).join("/"),
  text: fs.readFileSync(full, "utf8"),
}));

describe("brand guard", () => {
  it("scans real files", () => {
    expect(files.length).toBeGreaterThan(50);
    expect(files.some((f) => f.rel === "components/ui/Logo.tsx")).toBe(true);
  });

  it("nothing but Logo.tsx, brand-assets.json and manifest.ts refers to /brand/", () => {
    const offenders = files
      .filter((f) => !BRAND_AWARE.has(f.rel) && f.text.includes("/brand/"))
      .map((f) => f.rel);
    expect(offenders).toEqual([]);
  });

  it("nothing but those files imports brand-assets", () => {
    const offenders = files
      .filter((f) => !BRAND_AWARE.has(f.rel) && /brand-assets/.test(f.text))
      .map((f) => f.rel);
    expect(offenders).toEqual([]);
  });

  it("no UI file names a logo image directly", () => {
    const offenders = files
      .filter(
        (f) =>
          !BRAND_AWARE.has(f.rel) &&
          /(?:logo|mark|favicon|icon-\d+|opengraph-image)\.(?:svg|png|ico)/.test(f.text),
      )
      .map((f) => f.rel);
    expect(offenders).toEqual([]);
  });

  it("nothing re-creates the old text wordmark, taglines or emblem tiles", () => {
    // JSX text that is exactly the product name (the old styled wordmark), the old tagline, or a
    // brand emblem tile built from an icon (check/layers/diamond/lock) next to the name.
    const textWordmark = />\s*(?:Rumor Zero|RUMOR ZERO)\s*</;
    const oldTaglines =
      /Fact Social|Evidence-First Discourse Network|Cryptographic (?:Ledger|Access Control)/;
    const emblemTile =
      /<Icon[^>]*name="(?:check|layers|diamond|lock)"[^>]*\/>\s*<[^>]*>\s*(?:Rumor Zero|RUMOR ZERO)/;
    const offenders = files
      .filter((f) => !/\.test\.tsx?$/.test(f.rel) && f.rel.endsWith(".tsx"))
      .filter(
        (f) => textWordmark.test(f.text) || oldTaglines.test(f.text) || emblemTile.test(f.text),
      )
      .map((f) => f.rel);
    expect(offenders).toEqual([]);
  });

  it("the patterns do catch what they are meant to catch", () => {
    const textWordmark = />\s*(?:Rumor Zero|RUMOR ZERO)\s*</;
    expect(textWordmark.test('<span className="font-headline-sm">Rumor Zero</span>')).toBe(true);
    expect(textWordmark.test("<h1>RUMOR ZERO</h1>")).toBe(true);
    expect(textWordmark.test("<p>© 2026 Rumor Zero</p>")).toBe(false);
  });
});
