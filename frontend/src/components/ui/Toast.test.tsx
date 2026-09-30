import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TOAST_DURATION_MS, Toast, ToastProvider, useToast } from "./Toast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.show("Post published")}>
      Show
    </button>
  );
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>,
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Toast", () => {
  it("is the dark inverse-surface pill", () => {
    render(<Toast message="Copied" />);
    expect(screen.getByText("Copied").parentElement).toHaveClass(
      "bg-inverse-surface",
      "text-inverse-on-surface",
      "rounded-lg",
    );
  });
});

describe("ToastProvider", () => {
  it("shows a toast in a polite live region", async () => {
    renderWithProvider();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("Post published");
  });

  it("clears the toast after four seconds", () => {
    vi.useFakeTimers();
    renderWithProvider();
    act(() => screen.getByRole("button", { name: "Show" }).click());
    expect(screen.getByText("Post published")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(TOAST_DURATION_MS - 1));
    expect(screen.getByText("Post published")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByText("Post published")).toBeNull();
  });

  it("can be dismissed early", async () => {
    renderWithProvider();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Post published")).toBeNull();
  });

  it("stacks several toasts", async () => {
    renderWithProvider();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getAllByText("Post published")).toHaveLength(2);
  });

  it("throws a helpful error outside the provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Trigger />)).toThrow(/ToastProvider/);
    spy.mockRestore();
  });
});
