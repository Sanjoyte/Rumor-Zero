import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComposerTrigger } from "./ComposerTrigger";
import { makeQuota, renderWithComposer, type SessionKind } from "./test-helpers";

const api = vi.hoisted(() => ({ createPost: vi.fn(), fetchFactQuota: vi.fn() }));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/home",
}));

beforeEach(() => {
  api.fetchFactQuota.mockReset();
  api.fetchFactQuota.mockResolvedValue(makeQuota());
});

async function renderTrigger(kind: SessionKind) {
  const view = renderWithComposer(<ComposerTrigger />, kind);
  if (kind !== "loading") {
    await waitFor(() => expect(document.querySelector(".animate-pulse")).toBeNull());
  }
  return view;
}

describe("ComposerTrigger", () => {
  it("is a skeleton of the same size while the session loads", async () => {
    await renderTrigger("loading");
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("opens the composer for a verified user", async () => {
    await renderTrigger("verified");
    const trigger = screen.getByRole("button", { name: /What do you want to say/ });
    expect(trigger).not.toHaveAttribute("aria-disabled");
    await userEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "New post" })).toBeInTheDocument();
  });

  it("is aria-disabled for an unverified user, with the reason, and gives the toast", async () => {
    await renderTrigger("unverified");
    const trigger = screen.getByRole("button", { name: /What do you want to say/ });
    expect(trigger).toHaveAttribute("aria-disabled", "true");
    expect(trigger).toHaveAccessibleDescription("Verify your email to post.");
    await userEvent.click(trigger);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(
      await screen.findByText(/Verify your email to post\. Check your inbox/),
    ).toBeInTheDocument();
  });

  it("stays focusable when disabled, so keyboard users hear why", async () => {
    await renderTrigger("unverified");
    const trigger = screen.getByRole("button", { name: /What do you want to say/ });
    await userEvent.tab();
    expect(trigger).toHaveFocus();
    expect(trigger).not.toBeDisabled();
  });

  it("asks a visitor to log in, and comes back to /home", async () => {
    await renderTrigger("anonymous");
    expect(screen.getByText("Log in to share an opinion or a fact.")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Log in to post" });
    expect(link).toHaveAttribute("href", "/login?next=%2Fhome");
    expect(screen.queryByRole("button")).toBeNull();
  });
});
