import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const APP = import.meta.dirname;

function pageFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return pageFiles(full);
    return entry.name === "page.tsx" ? [full] : [];
  });
}

/** The landing page keeps the root default "Rumor Zero" on purpose (the smoke test pins it). */
const DEFAULT_TITLE = [path.join(APP, "(marketing)", "page.tsx")];

describe("page titles (ARCHITECTURE §10: '<Page> · Rumor Zero' on every route)", () => {
  const pages = pageFiles(APP);

  it("finds the routes", () => {
    expect(pages.length).toBeGreaterThan(15);
  });

  it.each(pages.map((file) => [path.relative(APP, file), file]))(
    "%s sets a title",
    (_name, file) => {
      if (DEFAULT_TITLE.includes(file)) return;
      const source = fs.readFileSync(file, "utf8");
      expect(source).toMatch(/title\s*:|generateMetadata/);
    },
  );

  it("the root layout supplies the title template and the default", () => {
    const layout = fs.readFileSync(path.join(APP, "layout.tsx"), "utf8");
    expect(layout).toContain('template: "%s · Rumor Zero"');
    expect(layout).toContain('default: "Rumor Zero"');
  });
});
