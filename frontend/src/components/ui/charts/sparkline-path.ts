export interface SparklineGeometry {
  /** The SVG path data of the line (empty for no points). */
  d: string;
  /** Where the last point sits, for the end dot. */
  last: { x: number; y: number } | null;
}

/** The least span, in score points, a sparkline is scaled to: a flat line must not zoom in on noise. */
export const MIN_SPAN = 10;

const round = (n: number) => Math.round(n * 100) / 100;

/**
 * Turn values into a line inside `width` x `height` with `pad` on every side. The scale follows the
 * data but never shows less than `MIN_SPAN` points (a flat line stays flat, centred), and a single
 * value sits in the middle. Higher is up.
 */
export function sparklinePath(
  values: number[],
  width: number,
  height: number,
  pad: number,
): SparklineGeometry {
  if (values.length === 0) return { d: "", last: null };
  let low = Math.min(...values);
  let high = Math.max(...values);
  if (high - low < MIN_SPAN) {
    const middle = (high + low) / 2;
    low = middle - MIN_SPAN / 2;
    high = middle + MIN_SPAN / 2;
  }
  const innerW = width - 2 * pad;
  const innerH = height - 2 * pad;
  const points = values.map((value, index) => ({
    x: round(pad + (values.length === 1 ? innerW / 2 : (index / (values.length - 1)) * innerW)),
    y: round(pad + ((high - value) / (high - low)) * innerH),
  }));
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
  return { d, last: points[points.length - 1] };
}
