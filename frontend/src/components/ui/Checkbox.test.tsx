import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Checkbox } from "./Checkbox";

describe("Checkbox", () => {
  it("is named by its label and toggles", async () => {
    const onChange = vi.fn();
    render(<Checkbox label="Email me about replies" onChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: "Email me about replies" });
    expect(box).not.toBeChecked();
    await userEvent.click(box);
    expect(box).toBeChecked();
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("links the description to the input", () => {
    render(<Checkbox label="Newsletter" description="One email a month" />);
    expect(screen.getByRole("checkbox")).toHaveAccessibleDescription("One email a month");
  });

  it("uses the Protocol Blue checked colour", () => {
    render(<Checkbox label="Agree" />);
    expect(screen.getByRole("checkbox")).toHaveClass("text-secondary", "rounded-lg");
  });

  it("can be disabled", () => {
    render(<Checkbox label="Locked" disabled />);
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });
});
