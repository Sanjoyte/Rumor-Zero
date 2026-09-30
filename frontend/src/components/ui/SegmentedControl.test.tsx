import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { SegmentedControl } from "./SegmentedControl";

type Kind = "opinion" | "fact";

const OPTIONS = [
  { value: "opinion" as const, label: "Opinion", icon: "format_quote" },
  { value: "fact" as const, label: "Fact", icon: "fact_check" },
];

function Harness({ start = null }: { start?: Kind | null }) {
  const [value, setValue] = useState<Kind | null>(start);
  return <SegmentedControl options={OPTIONS} value={value} onChange={setValue} label="Post type" />;
}

describe("SegmentedControl", () => {
  it("is a named radio group with nothing pre-selected", () => {
    render(<Harness />);
    expect(screen.getByRole("radiogroup", { name: "Post type" })).toBeInTheDocument();
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).toHaveAttribute("aria-checked", "false");
    }
  });

  it("keeps the first option reachable by Tab when nothing is selected", () => {
    render(<Harness />);
    expect(screen.getByRole("radio", { name: /Opinion/ })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: /Fact/ })).toHaveAttribute("tabindex", "-1");
  });

  it("selects on click and raises the selected segment", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("radio", { name: /Fact/ }));
    const fact = screen.getByRole("radio", { name: /Fact/ });
    expect(fact).toHaveAttribute("aria-checked", "true");
    expect(fact).toHaveClass("bg-surface-container-lowest", "shadow-sm");
    expect(screen.getByRole("radio", { name: /Opinion/ })).toHaveAttribute("aria-checked", "false");
  });

  it("moves the selection with the arrow keys, wrapping around", async () => {
    render(<Harness start="opinion" />);
    screen.getByRole("radio", { name: /Opinion/ }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: /Fact/ })).toHaveFocus();
    expect(screen.getByRole("radio", { name: /Fact/ })).toHaveAttribute("aria-checked", "true");
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: /Opinion/ })).toHaveAttribute("aria-checked", "true");
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("radio", { name: /Fact/ })).toHaveAttribute("aria-checked", "true");
  });

  it("uses the pill shape from Stitch", () => {
    render(<Harness />);
    expect(screen.getByRole("radiogroup")).toHaveClass("rounded-full", "bg-surface-container");
  });
});
