import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows the glyph, title, text and action", () => {
    render(
      <EmptyState
        icon="verified"
        title="You are all caught up"
        action={<button type="button">Refresh</button>}
      >
        No new posts from people you follow.
      </EmptyState>,
    );
    expect(screen.getByRole("heading", { name: "You are all caught up" })).toBeInTheDocument();
    expect(screen.getByText("No new posts from people you follow.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
  });

  it("tints the glyph teal only for the success tone", () => {
    const { rerender } = render(<EmptyState icon="search_off" title="No results" />);
    expect(screen.getByText("search_off").parentElement).toHaveClass("text-outline");
    rerender(<EmptyState icon="verified" title="Done" tone="success" />);
    expect(screen.getByText("verified").parentElement).toHaveClass("text-primary");
  });
});
