import { describe, expect, it } from "vitest";
import { MIN_SPAN, sparklinePath } from "./sparkline-path";

describe("sparklinePath", () => {
  it("is empty without points", () => {
    expect(sparklinePath([], 112, 24, 3)).toEqual({ d: "", last: null });
  });

  it("puts a single value in the middle", () => {
    const { d, last } = sparklinePath([70], 112, 24, 3);
    expect(d).toBe("M56 12");
    expect(last).toEqual({ x: 56, y: 12 });
  });

  it("scales the data to the box, higher up, first point at the left padding", () => {
    const { d, last } = sparklinePath([40, 60], 112, 24, 3);
    expect(d).toBe("M3 21 L109 3");
    expect(last).toEqual({ x: 109, y: 3 });
  });

  it("keeps a flat line flat and centred instead of zooming in", () => {
    const { d } = sparklinePath([50, 50, 50], 112, 24, 3);
    expect(d).toBe("M3 12 L56 12 L109 12");
  });

  it("does not zoom in on a span narrower than the minimum", () => {
    const { last } = sparklinePath([50, 52], 112, 24, 3);
    // 52 is 1 point above the middle (51) of a 10-point scale: 1/10 of the 18 px inner height
    expect(MIN_SPAN).toBe(10);
    expect(last?.y).toBeCloseTo(12 - 0.1 * 18, 1);
  });

  it("stays inside the padding", () => {
    const { d } = sparklinePath([0, 100, 20, 80], 112, 24, 3);
    const numbers = d.match(/[\d.]+/g)!.map(Number);
    for (const n of numbers) {
      expect(n).toBeGreaterThanOrEqual(3);
      expect(n).toBeLessThanOrEqual(109);
    }
  });

  it("rounds to two decimals", () => {
    const { d } = sparklinePath([10, 20, 15], 100, 24, 3);
    expect(d).not.toMatch(/\.\d{3}/);
  });
});
