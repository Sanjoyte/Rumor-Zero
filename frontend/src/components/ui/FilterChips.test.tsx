import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { FilterChips } from "./FilterChips";

const CHIPS = [
  { id: "all", label: "All", count: 9 },
  { id: "verified", label: "Verified", dot: "primary" as const },
  { id: "false", label: "False", dot: "error" as const },
];

function Harness({ multiple }: { multiple?: boolean }) {
  const [selected, setSelected] = useState<string[]>(["all"]);
  return (
    <FilterChips
      chips={CHIPS}
      selected={selected}
      onChange={setSelected}
      multiple={multiple}
      label="Status"
    />
  );
}

const pressed = (name: string | RegExp) =>
  screen.getByRole("button", { name }).getAttribute("aria-pressed");

describe("FilterChips", () => {
  it("renders pressed and unpressed chips in a named group", () => {
    render(<Harness />);
    expect(screen.getByRole("group", { name: "Status" })).toBeInTheDocument();
    expect(pressed(/All/)).toBe("true");
    expect(pressed("Verified")).toBe("false");
  });

  it("shows the dark selected style", () => {
    render(<Harness />);
    expect(screen.getByRole("button", { name: /All/ })).toHaveClass(
      "bg-inverse-surface",
      "text-inverse-on-surface",
    );
  });

  it("replaces the choice in single mode", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Verified" }));
    expect(pressed("Verified")).toBe("true");
    expect(pressed(/All/)).toBe("false");
  });

  it("keeps several chips in multiple mode, and unpresses on a second click", async () => {
    render(<Harness multiple />);
    await userEvent.click(screen.getByRole("button", { name: "Verified" }));
    expect(pressed(/All/)).toBe("true");
    expect(pressed("Verified")).toBe("true");
    await userEvent.click(screen.getByRole("button", { name: "Verified" }));
    expect(pressed("Verified")).toBe("false");
  });

  it("shows the count", () => {
    render(<Harness />);
    expect(screen.getByText("9")).toBeInTheDocument();
  });
});
