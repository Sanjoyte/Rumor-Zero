import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Textarea } from "./Textarea";

describe("Textarea", () => {
  it("binds the label and accepts typing", async () => {
    render(<Textarea label="Bio" />);
    await userEvent.type(screen.getByLabelText("Bio"), "Hello");
    expect(screen.getByLabelText("Bio")).toHaveValue("Hello");
  });

  it("counts characters as you type (uncontrolled)", async () => {
    render(<Textarea label="Post" maxCount={500} />);
    expect(screen.getByText("0 / 500 characters")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Post"), "abcd");
    expect(screen.getByText("4 / 500 characters")).toBeInTheDocument();
  });

  it("follows the value when controlled, and turns red over the limit", () => {
    render(<Textarea label="Post" maxCount={3} value="abcdef" onChange={() => {}} />);
    expect(screen.getByText("6 / 3 characters")).toHaveClass("text-error");
    expect(screen.getByLabelText("Post")).toHaveAttribute("aria-invalid", "true");
  });

  it("links the counter to the field for assistive tech", () => {
    render(<Textarea label="Post" maxCount={500} />);
    expect(screen.getByLabelText("Post")).toHaveAccessibleDescription("0 / 500 characters");
  });

  it("has a bare composer look with a hidden label", () => {
    render(<Textarea label="Post text" variant="bare" />);
    expect(screen.getByText("Post text")).toHaveClass("sr-only");
    expect(screen.getByLabelText("Post text")).toHaveClass(
      "font-claim-headline",
      "border-none",
      "bg-transparent",
    );
  });

  it("shows an error in place of the border", () => {
    render(<Textarea label="Bio" error="Too long" />);
    expect(screen.getByLabelText("Bio")).toHaveClass("border-error");
    expect(screen.getByText("Too long")).toBeInTheDocument();
  });
});
