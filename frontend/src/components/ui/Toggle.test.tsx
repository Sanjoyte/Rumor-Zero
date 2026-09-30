import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Toggle } from "./Toggle";

function Harness({ tone }: { tone?: "secondary" | "tertiary" }) {
  const [on, setOn] = useState(false);
  return <Toggle label="Toggle Emergency Mode" checked={on} onCheckedChange={setOn} tone={tone} />;
}

describe("Toggle", () => {
  it("is a named switch that starts off", () => {
    render(<Harness />);
    const toggle = screen.getByRole("switch", { name: "Toggle Emergency Mode" });
    expect(toggle).not.toBeChecked();
  });

  it("switches on and off when clicked", async () => {
    render(<Harness />);
    const toggle = screen.getByRole("switch");
    await userEvent.click(toggle);
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    expect(toggle).not.toBeChecked();
  });

  it("toggles from the keyboard with Space", async () => {
    render(<Harness />);
    await userEvent.tab();
    expect(screen.getByRole("switch")).toHaveFocus();
    await userEvent.keyboard(" ");
    expect(screen.getByRole("switch")).toBeChecked();
  });

  it("toggles when the track is clicked, because the whole track is the label", async () => {
    const { container } = render(<Harness />);
    const track = container.querySelector("label > span") as HTMLElement;
    await userEvent.click(track);
    expect(screen.getByRole("switch")).toBeChecked();
  });

  it("uses violet for the emergency tone and blue by default", () => {
    const { container, rerender } = render(<Harness />);
    expect(container.querySelector("label > span")).toHaveClass("peer-checked:bg-secondary");
    rerender(<Harness tone="tertiary" />);
    expect(container.querySelector("label > span")).toHaveClass("peer-checked:bg-tertiary");
  });

  it("does not toggle when disabled", async () => {
    const { container } = render(
      <Toggle label="Locked" checked={false} onCheckedChange={() => {}} disabled />,
    );
    await userEvent.click(container.querySelector("label > span") as HTMLElement);
    expect(screen.getByRole("switch")).not.toBeChecked();
    expect(screen.getByRole("switch")).toBeDisabled();
  });
});
