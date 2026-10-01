// WCAG 2.x contrast ratios for the logo colours against the Stitch surfaces (ARCHITECTURE 14).

function channels(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new Error(`Expected a #rrggbb colour, got "${hex}"`);
  return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255);
}

export function relativeLuminance(hex) {
  const [r, g, b] = channels(hex).map((v) =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a, b) {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * @param {{grey: string, cyan: string}} colors
 * @param {{name: string, hex: string}[]} surfaces
 * @returns {{surface: string, hex: string, grey: string, cyan: string}[]} ratios as "3.45"
 */
export function contrastTable(colors, surfaces) {
  return surfaces.map(({ name, hex }) => ({
    surface: name,
    hex,
    grey: contrastRatio(colors.grey, hex).toFixed(2),
    cyan: contrastRatio(colors.cyan, hex).toFixed(2),
  }));
}

export function formatContrastTable(rows) {
  const width = Math.max(...rows.map((r) => `${r.surface} ${r.hex}`.length));
  const lines = [
    `${"Contrast on".padEnd(width)}  grey letters  cyan "0"`,
    ...rows.map(
      (r) =>
        `${`${r.surface} ${r.hex}`.padEnd(width)}  ${`${r.grey} : 1`.padEnd(12)}  ${r.cyan} : 1`,
    ),
  ];
  return lines.join("\n");
}
