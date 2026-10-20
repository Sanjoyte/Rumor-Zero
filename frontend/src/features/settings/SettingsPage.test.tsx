import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccountExitContext } from "./account-exit";
import { SETTINGS_MESSAGES } from "./messages";
import { SettingsPage } from "./SettingsPage";
import { renderSettings } from "./test-helpers";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
  usePathname: () => "/settings",
}));

const api = vi.hoisted(() => ({ deleteAccount: vi.fn() }));
vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  ...api,
}));

const reputation = vi.hoisted(() => ({ fetchMyReputationEvents: vi.fn() }));
vi.mock("@/features/reputation/reputation-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/reputation/reputation-api")>()),
  ...reputation,
}));

const begin = vi.fn();

beforeEach(() => {
  replace.mockClear();
  begin.mockClear();
  api.deleteAccount.mockReset();
  reputation.fetchMyReputationEvents.mockReset();
  reputation.fetchMyReputationEvents.mockResolvedValue({ items: [], nextCursor: null });
});

async function setup(me = {}) {
  const view = renderSettings(
    <AccountExitContext.Provider value={{ begin }}>
      <SettingsPage />
    </AccountExitContext.Provider>,
    me,
  );
  await screen.findByRole("heading", { level: 1, name: "Settings" });
  return view;
}

describe("SettingsPage", () => {
  it("has the five sections and a nav that links to them", async () => {
    await setup();
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    const targets = within(nav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(targets).toEqual([
      "#section-profile",
      "#section-account",
      "#section-credibility",
      "#section-data",
    ]);
    for (const id of targets) expect(document.querySelector(id!)).not.toBeNull();
    for (const name of ["Profile", "Account", "Credibility", "Your data"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    expect(screen.getByLabelText("Display name")).toHaveValue("Ada L.");
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download your data/ })).toBeInTheDocument();
  });

  it("mounts the credibility panel open, with the public score from /me", async () => {
    await setup({ public_score: 62 });
    expect(await screen.findByText(/^Your score:/)).toBeInTheDocument();
    expect(reputation.fetchMyReputationEvents).toHaveBeenCalled();
  });

  it("deletes the account: ends the session, leaves quietly for /home and says so", async () => {
    const user = userEvent.setup();
    api.deleteAccount.mockResolvedValue(undefined);
    const view = await setup();
    await user.click(screen.getByRole("button", { name: "Delete account…" }));
    await user.type(await screen.findByLabelText("Your password"), "my-password-1");
    await user.click(screen.getByRole("button", { name: "Delete account" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
    expect(api.deleteAccount).toHaveBeenCalledWith({ password: "my-password-1" });
    expect(begin).toHaveBeenCalledTimes(1);
    expect(view.session.getState().status).toBe("anonymous");
    expect(await screen.findByText(SETTINGS_MESSAGES.accountDeleted)).toBeInTheDocument();
  });

  it("a failed deletion keeps you signed in on the page", async () => {
    const user = userEvent.setup();
    api.deleteAccount.mockRejectedValue(new Error("boom"));
    const view = await setup();
    await user.click(screen.getByRole("button", { name: "Delete account…" }));
    await user.type(await screen.findByLabelText("Your password"), "pw-123456");
    await user.click(screen.getByRole("button", { name: "Delete account" }));

    expect(await screen.findByText(SETTINGS_MESSAGES.generic)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(begin).not.toHaveBeenCalled();
    expect(view.session.getState().status).toBe("authenticated");
  });

  it("asks a Google-only account for its username", async () => {
    const user = userEvent.setup();
    await setup({ has_usable_password: false });
    await user.click(screen.getByRole("button", { name: "Delete account…" }));
    expect(await screen.findByLabelText("Type your username to confirm")).toBeInTheDocument();
  });

  it.each(["moderator", "senior_moderator"] as const)(
    "gives a %s the explanation instead of the button",
    async (role) => {
      await setup({ role });
      expect(screen.queryByRole("button", { name: "Delete account…" })).toBeNull();
      expect(screen.getByText(SETTINGS_MESSAGES.staffAccount)).toBeInTheDocument();
    },
  );
});
