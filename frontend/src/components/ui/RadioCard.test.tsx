import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { RadioCardGroup } from "./RadioCard";

const OPTIONS = [
  { value: "inaccurate", label: "False or inaccurate", description: "The claim is wrong." },
  { value: "misleading", label: "Missing context or misleading" },
  { value: "spam", label: "Spam or fake accounts" },
];

function Harness({ initial = null }: { initial?: string | null }) {
  const [value, setValue] = useState<string | null>(initial);
  return (
    <RadioCardGroup
      name="reason"
      legend="Why are you reporting this post?"
      options={OPTIONS}
      value={value}
      onChange={setValue}
    />
  );
}

describe("RadioCardGroup", () => {
  it("is a named group of radios", () => {
    render(<Harness />);
    expect(
      screen.getByRole("group", { name: "Why are you reporting this post?" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });

  it("starts with nothing chosen", () => {
    render(<Harness />);
    for (const radio of screen.getAllByRole("radio")) expect(radio).not.toBeChecked();
  });

  it("selects one card at a time, by clicking the card text", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByText("Missing context or misleading"));
    expect(screen.getByRole("radio", { name: /Missing context/ })).toBeChecked();
    await userEvent.click(screen.getByText("Spam or fake accounts"));
    expect(screen.getByRole("radio", { name: /Spam/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /Missing context/ })).not.toBeChecked();
  });

  it("shows the option description inside the card", () => {
    render(<Harness />);
    expect(screen.getByRole("radio", { name: /False or inaccurate/ })).toHaveAccessibleName(
      /The claim is wrong/,
    );
  });

  it("highlights the checked card with a blue border", () => {
    render(<Harness initial="spam" />);
    const card = screen.getByRole("radio", { name: /Spam/ }).closest("label");
    expect(card).toHaveClass("has-checked:border-secondary", "has-checked:bg-secondary/5");
  });
});
