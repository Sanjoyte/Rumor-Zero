import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoadMore } from "./LoadMore";

describe("LoadMore", () => {
  it("shows a button that loads the next page", async () => {
    const onClick = vi.fn();
    render(<LoadMore hasMore onClick={onClick} />);
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and busy while loading", () => {
    render(<LoadMore hasMore loading onClick={() => {}} />);
    const button = screen.getByRole("button", { name: /Loading/ });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("shows the end note instead of a button when there is nothing more", () => {
    render(<LoadMore hasMore={false} onClick={() => {}} endLabel="You have reached the end." />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("You have reached the end.")).toBeInTheDocument();
  });
});
