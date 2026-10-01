// @vitest-environment node
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import config from "./brand.config.json";
import { contrastRatio, contrastTable, formatContrastTable } from "./contrast.mjs";

const repoRoot = path.resolve(import.meta.dirname, "..", "..", "..");
const architecture = fs.readFileSync(path.join(repoRoot, "docs", "ARCHITECTURE.md"), "utf8");
const globals = fs.readFileSync(
  path.join(import.meta.dirname, "..", "..", "src", "app", "globals.css"),
  "utf8",
);
const colors = { grey: "#898a8d", cyan: "#23b5d8" };

describe("contrast", () => {
  it("computes the WCAG ratio (white on black is 21:1)", () => {
    expect(contrastRatio("#ffffff", "#000000")).toBeCloseTo(21, 5);
    expect(contrastRatio("#777777", "#777777")).toBeCloseTo(1, 5);
  });

  it("matches the numbers recorded in the config", () => {
    const rows = contrastTable(colors, config.contrastSurfaces);
    expect(rows.map(({ surface, grey, cyan }) => ({ surface, grey, cyan }))).toEqual(
      config.expectedContrast,
    );
  });

  it("matches the table in ARCHITECTURE 14, row by row", () => {
    for (const { surface, grey, cyan } of contrastTable(colors, config.contrastSurfaces)) {
      const row = architecture
        .split("\n")
        .find((line) => line.includes(`\`${surface}\``) && line.includes(" : 1"));
      expect(row, `ARCHITECTURE 14 row for ${surface}`).toBeDefined();
      expect(row).toContain(`${grey} : 1`);
      expect(row).toContain(`${cyan} : 1`);
    }
  });

  it("uses the surface colours and the plate colour defined in globals.css", () => {
    for (const { name, hex } of config.contrastSurfaces) {
      expect(globals).toContain(`--color-${name}: ${hex};`);
    }
    expect(globals).toContain(`--color-inverse-surface: ${config.plateColor};`);
  });

  it("prints a table with every surface", () => {
    const text = formatContrastTable(contrastTable(colors, config.contrastSurfaces));
    expect(text).toContain("inverse-surface #283044");
    expect(text).toContain("3.81 : 1");
    expect(text).toContain("5.43 : 1");
    expect(text.split("\n")).toHaveLength(5);
  });
});
