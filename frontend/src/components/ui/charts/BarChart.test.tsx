import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BarChart, niceMax } from "./BarChart";

const SERIES = [
  { key: "reposts", label: "Reposts", tone: "secondary" as const },
  { key: "likes", label: "Likes", tone: "outline" as const },
];

function days(n: number, counts: (i: number) => Record<string, number>) {
  return Array.from({ length: n }, (_, i) => ({
    date: `2026-10-${String(i + 1).padStart(2, "0")}`,
    counts: counts(i),
  }));
}

function setup(data = days(14, () => ({})), extra: Partial<Parameters<typeof BarChart>[0]> = {}) {
  return render(
    <BarChart
      days={data}
      series={SERIES}
      tableOnly={[{ key: "comments", label: "Comments" }]}
      summary="Spread"
      caption="First 14 days after posting (UTC)"
      emptyNote="No reposts or likes yet."
      {...extra}
    />,
  );
}

describe("niceMax", () => {
  it.each([
    [0, 1],
    [1, 1],
    [1.5, 2],
    [3, 5],
    [7, 10],
    [11, 20],
    [60, 100],
    [100, 100],
  ])("%s rounds up to %s", (value, expected) => {
    expect(niceMax(value)).toBe(expected);
  });
});

describe("BarChart", () => {
  it("is an image named by its summary with a sibling table", () => {
    setup();
    const image = screen.getByRole("img", { name: "Spread" });
    const table = screen.getByRole("table", { name: "First 14 days after posting (UTC)" });
    expect(image).not.toContainElement(table);
  });

  it("has a row per day and a column per series, comments included", () => {
    setup(days(14, (i) => ({ reposts: i === 0 ? 2 : 0, likes: 1, comments: 4 })));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(15);
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Day", "Reposts", "Likes", "Comments"]);
    const first = within(table).getAllByRole("row")[1];
    expect(
      within(first)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["2", "1", "4"]);
  });

  it("says so when there is nothing to draw and draws no bars", () => {
    const { container } = setup();
    expect(screen.getByText("No reposts or likes yet.")).toBeInTheDocument();
    expect(container.querySelectorAll('[style*="height"]')).toHaveLength(0);
  });

  it("does not draw a day's zero bars, but draws the others to scale", () => {
    const { container } = setup(days(14, (i) => ({ likes: i === 2 ? 5 : 0 })));
    expect(screen.queryByText("No reposts or likes yet.")).not.toBeInTheDocument();
    const bars = container.querySelectorAll('[style*="height"]');
    expect(bars).toHaveLength(1);
    expect((bars[0] as HTMLElement).style.height).toBe("100%"); // 5 of a nice maximum of 5
  });

  it("keeps a tiny bar visible", () => {
    const { container } = setup(
      days(14, (i) => ({ likes: i === 0 ? 1 : 0, reposts: i === 1 ? 100 : 0 })),
    );
    const heights = [...container.querySelectorAll<HTMLElement>('[style*="height"]')].map(
      (el) => el.style.height,
    );
    expect(heights).toEqual(["3%", "100%"]);
  });

  it("labels the first, middle and last day and the legend", () => {
    setup();
    const graphic = within(screen.getByRole("img", { name: "Spread" }));
    const labels = graphic.getAllByText(/^Oct \d+$/).map((el) => el.textContent);
    expect(labels).toEqual(["Oct 1", "Oct 7", "Oct 14"]);
    expect(graphic.getByText("Reposts")).toBeInTheDocument();
    expect(graphic.getByText("Likes")).toBeInTheDocument();
  });

  it("marks the verdict day with a dot and a legend word", () => {
    const { container } = setup(undefined, { markerDate: "2026-10-03", markerLabel: "Verdict" });
    expect(screen.getByText("Verdict")).toBeInTheDocument();
    expect(container.querySelectorAll(".mt-0\\.5.rounded-full")).toHaveLength(1);
  });

  it("has no marker without a marker date", () => {
    setup(undefined, { markerLabel: "Verdict" });
    expect(screen.queryByText("Verdict")).not.toBeInTheDocument();
  });

  it("has no animation", () => {
    const { container } = setup(days(14, () => ({ likes: 2 })));
    expect(container.innerHTML).not.toMatch(/animate-|transition/);
  });
});
