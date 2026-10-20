import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const BANNED =
  /^(recharts|chart\.js|react-chartjs-2|d3(-.*)?|victory.*|@nivo\/.*|@visx\/.*|echarts.*|apexcharts|react-apexcharts|highcharts.*|plotly.*|react-plotly\.js|@mui\/x-charts|chartist|billboard\.js|uplot)$/;

describe("the charts are built by hand", () => {
  it("package.json lists no chart library", () => {
    const pkg = JSON.parse(readFileSync(path.resolve(process.cwd(), "package.json"), "utf8"));
    const names = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies });
    expect(names.filter((name) => BANNED.test(name))).toEqual([]);
  });

  it("the guard knows the usual suspects", () => {
    for (const name of [
      "recharts",
      "chart.js",
      "d3",
      "d3-scale",
      "victory",
      "@nivo/core",
      "echarts",
    ]) {
      expect(BANNED.test(name)).toBe(true);
    }
    expect(BANNED.test("next")).toBe(false);
  });
});
