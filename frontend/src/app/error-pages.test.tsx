import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ErrorPage from "./error";
import NotFound from "./not-found";

describe("not-found", () => {
  it("shows the logo, a heading and a way home", () => {
    render(<NotFound />);
    expect(screen.getByRole("img", { name: "Rumor Zero" })).toHaveAttribute("height", "48");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the home page" })).toHaveAttribute("href", "/");
  });
});

describe("error", () => {
  it("shows the logo and retries without showing the error", async () => {
    const reset = vi.fn();
    render(<ErrorPage error={new Error("database password is hunter2")} reset={reset} />);
    expect(screen.getByRole("img", { name: "Rumor Zero" })).toBeInTheDocument();
    expect(screen.queryByText(/hunter2/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
