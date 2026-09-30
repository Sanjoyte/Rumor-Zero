import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { TextField } from "./TextField";

describe("TextField", () => {
  it("binds the label to the input", async () => {
    render(<TextField label="Email" />);
    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    expect(screen.getByLabelText("Email")).toHaveValue("ada@example.com");
  });

  it("uses the filled Stitch look", () => {
    render(<TextField label="Email" />);
    expect(screen.getByLabelText("Email")).toHaveClass(
      "h-11",
      "rounded-lg",
      "bg-surface-container-low",
      "border-outline-variant/50",
    );
  });

  it("shows a hint and links it with aria-describedby", () => {
    render(<TextField label="Username" hint="3 to 30 characters" />);
    const input = screen.getByLabelText("Username");
    expect(input).toHaveAccessibleDescription("3 to 30 characters");
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("marks the field invalid and swaps the border when there is an error", () => {
    render(<TextField label="Email" error="Enter a valid email" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Enter a valid email/);
    expect(input).toHaveClass("border-error");
    expect(input).not.toHaveClass("border-outline-variant/50");
  });

  it("shows a confirmation in Verified teal with a dot, linked to the input", () => {
    render(<TextField label="Username" success="Available: @ada" />);
    const message = screen.getByText("Available: @ada");
    expect(message).toHaveClass("text-primary", "font-medium");
    expect(screen.getByLabelText("Username")).toHaveAccessibleDescription("Available: @ada");
  });

  it("prefers the error over a confirmation", () => {
    render(<TextField label="Username" success="Available" error="Already taken" />);
    expect(screen.queryByText("Available")).toBeNull();
    expect(screen.getByText("Already taken")).toBeInTheDocument();
  });

  it("can use monospace text for URLs and DOIs", () => {
    const { rerender } = render(<TextField label="Source" />);
    expect(screen.getByLabelText("Source")).toHaveClass("font-body-md", "text-body-md");
    rerender(<TextField label="Source" mono />);
    expect(screen.getByLabelText("Source")).toHaveClass("font-label-code", "text-label-code");
    expect(screen.getByLabelText("Source")).not.toHaveClass("font-body-md");
  });

  it("looks disabled when disabled", () => {
    render(<TextField label="Email" disabled />);
    expect(screen.getByLabelText("Email")).toHaveClass(
      "disabled:opacity-60",
      "disabled:cursor-not-allowed",
    );
  });

  it("can hide the label visually without losing the name", () => {
    render(<TextField label="Search" hideLabel />);
    expect(screen.getByText("Search")).toHaveClass("sr-only");
    expect(screen.getByRole("textbox", { name: "Search" })).toBeInTheDocument();
  });

  it("makes room for a leading icon and trailing content", () => {
    render(<TextField label="Username" leadingIcon="link" trailing={<span>ok</span>} />);
    const input = screen.getByLabelText("Username");
    expect(input).toHaveClass("pl-9", "pr-10");
    expect(screen.getByText("link")).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
  });
});
