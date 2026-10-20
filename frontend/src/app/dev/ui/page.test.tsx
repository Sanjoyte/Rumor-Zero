import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import DevUiPage from "./page";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("/dev/ui", () => {
  it("renders the gallery outside production", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<ToastProvider>{DevUiPage()}</ToastProvider>);
    expect(screen.getByRole("heading", { level: 1, name: "UI gallery" })).toBeInTheDocument();
    for (const name of [
      "Button",
      "TextField, PasswordField, Textarea",
      "Tabs, SegmentedControl, FilterChips",
      "StatusBadge, CategoryChip, VerdictStripe",
      "Stitch b1: PostCard",
      "Stitch b1: pinned emergencies",
      "Stitch b2 and d1: modals",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });

  it("shows every row of the badge table, worded FALSE", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<ToastProvider>{DevUiPage()}</ToastProvider>);
    const badges = document.getElementById("badges") as HTMLElement;
    for (const label of [
      "OPINION",
      "CHECKING FACTS…",
      "VERIFIED 94%",
      "VERIFIED · REVIEWED",
      "FALSE 88%",
      "FALSE · REVIEWED",
      "UNDER REVIEW",
      "REMOVED",
      "EMERGENCY",
    ]) {
      expect(within(badges).getByText(label)).toBeInTheDocument();
    }
    expect(document.body.textContent).not.toMatch(/debunk/i);
  });

  it("shows the emergency card with its violet stripe in the Stitch b1 section", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<ToastProvider>{DevUiPage()}</ToastProvider>);
    const cards = document.getElementById("stitch-post-cards") as HTMLElement;
    expect(cards.querySelector("[data-tone='tertiary']")).not.toBeNull();
    expect(within(cards).getAllByText("EMERGENCY").length).toBeGreaterThan(0);
  });

  it("shows the pinned emergencies open and folded (Part 11C)", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<ToastProvider>{DevUiPage()}</ToastProvider>);
    const pinned = document.getElementById("stitch-pinned") as HTMLElement;
    const open = within(pinned).getByRole("region", { name: "Emergency posts" });
    expect(within(open).getAllByRole("article")).toHaveLength(2);
    expect(within(open).getByRole("button", { name: "Show all (3)" })).toBeInTheDocument();
    expect(
      within(pinned).getByRole("region", { name: "2 emergency posts pinned" }),
    ).toBeInTheDocument();
  });

  it("answers 404 in a production build", () => {
    vi.stubEnv("NODE_ENV", "production");
    let thrown: unknown;
    try {
      DevUiPage();
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeDefined();
    expect(String((thrown as { digest?: string }).digest)).toContain("404");
  });
});
