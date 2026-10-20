import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import type { AuthApi } from "@/lib/auth/auth-api";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { AuthSession } from "@/lib/auth/session";
import AppLayout from "./layout";

const resendMock = vi.hoisted(() => vi.fn<() => Promise<void>>());
const quotaMock = vi.hoisted(() => vi.fn());
const unreadMock = vi.hoisted(() => vi.fn());
vi.mock("@/features/notifications/notifications-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/notifications/notifications-api")>()),
  fetchUnreadCount: unreadMock,
}));
vi.mock("@/features/posts/posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/posts/posts-api")>()),
  fetchFactQuota: quotaMock,
}));
vi.mock("@/lib/auth/auth-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/auth-api")>()),
  resendVerificationEmail: resendMock,
}));

let pathname = "/settings";
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
}));

const ME = {
  id: "u-1",
  username: "ada",
  display_name: "Ada Lovelace",
  email: "ada@example.test",
  is_email_verified: true,
  role: "user" as const,
  has_usable_password: true,
  google_connected: false,
  avatar_url: null,
};

function sessionWith(kind: "loading" | "anonymous" | "authenticated", api: Partial<AuthApi> = {}) {
  let token: string | null = null;
  return new AuthSession({
    api: {
      login: vi.fn(),
      signup: vi.fn(),
      refresh: vi.fn(() =>
        kind === "loading" ? new Promise<string>(() => {}) : Promise.resolve("t"),
      ),
      logout: vi.fn(async () => undefined),
      fetchMe: vi.fn(async () => ME),
      ...api,
    },
    lock: (task) => task(),
    store: { get: () => token, set: (value) => (token = value) },
    hasHint: () => kind !== "anonymous",
  });
}

function renderLayout(session: AuthSession) {
  render(
    <AuthProvider session={session}>
      <ToastProvider>
        <AppLayout>
          <p>Secret settings</p>
        </AppLayout>
      </ToastProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  quotaMock.mockReset();
  quotaMock.mockResolvedValue({
    limit: 10,
    used: 3,
    remaining: 7,
    window_hours: 24,
    next_slot_at: null,
  });
  resendMock.mockReset();
  resendMock.mockResolvedValue(undefined);
  unreadMock.mockReset();
  unreadMock.mockResolvedValue(0);
  pathname = "/settings";
  window.history.pushState({}, "", "/settings?tab=email");
  replace.mockClear();
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

describe("(app) layout guard", () => {
  it("shows a placeholder on a protected page while the session loads", () => {
    renderLayout(sessionWith("loading"));
    expect(screen.queryByText("Secret settings")).toBeNull();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("sends anonymous visitors to /login with the page to come back to", async () => {
    renderLayout(sessionWith("anonymous"));
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/login?next=%2Fsettings%3Ftab%3Demail"),
    );
    expect(screen.queryByText("Secret settings")).toBeNull();
  });

  it("shows the page to a logged-in user", async () => {
    renderLayout(sessionWith("authenticated"));
    expect(await screen.findByText("Secret settings")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("leaves public pages alone when logged out", async () => {
    pathname = "/home";
    renderLayout(sessionWith("anonymous"));
    expect(await screen.findByText("Secret settings")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("complementary")).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("(app) layout unread badge", () => {
  beforeEach(() => {
    pathname = "/home";
  });

  it("polls the unread count for a signed-in user and shows it on the rail and the phone tab", async () => {
    unreadMock.mockResolvedValue(4);
    renderLayout(sessionWith("authenticated"));
    const sidebar = await screen.findByRole("complementary");
    expect(
      await within(sidebar).findByRole("link", { name: "Notifications, 4 unread" }),
    ).toBeInTheDocument();
    const [, bottomNav] = screen.getAllByRole("navigation", { name: "Main" });
    expect(
      within(bottomNav).getByRole("link", { name: "Notifications, 4 unread" }),
    ).toBeInTheDocument();
    expect(unreadMock).toHaveBeenCalledWith(expect.any(AbortSignal));
  });

  it("shows no badge when nothing is unread", async () => {
    renderLayout(sessionWith("authenticated"));
    const sidebar = await screen.findByRole("complementary");
    await waitFor(() => expect(unreadMock).toHaveBeenCalled());
    expect(within(sidebar).getByRole("link", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.queryByTestId("unread-badge")).toBeNull();
  });

  it("does not ask a visitor for a count", async () => {
    renderLayout(sessionWith("anonymous"));
    await screen.findByText("Secret settings");
    await waitFor(() => expect(screen.getByRole("complementary")).toBeInTheDocument());
    expect(unreadMock).not.toHaveBeenCalled();
  });
});

describe("(app) layout logout", () => {
  async function openMenuAndLogOut() {
    const sidebar = await screen.findByRole("complementary");
    await within(sidebar).findByText("Ada Lovelace");
    await userEvent.click(screen.getAllByRole("button", { name: "Log out", hidden: true })[0]);
  }

  it("goes to /login (not back to this page) after logging out", async () => {
    const session = sessionWith("authenticated");
    renderLayout(session);
    await openMenuAndLogOut();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(replace).toHaveBeenCalledTimes(1);
    expect(session.getState().status).toBe("anonymous");
  });

  it("shows an error toast and stays logged in when logging out fails", async () => {
    const session = sessionWith("authenticated", {
      logout: vi.fn(async () =>
        Promise.reject(new ApiError({ status: 0, code: "network_error", detail: "offline" })),
      ),
    });
    renderLayout(session);
    await openMenuAndLogOut();
    expect(
      await screen.findByText("Couldn't log out. Check your connection and try again."),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(session.getState().status).toBe("authenticated");
  });
});

describe("(app) layout, unverified email", () => {
  const unverified = { ...ME, is_email_verified: false };
  const sessionUnverified = () =>
    sessionWith("authenticated", { fetchMe: vi.fn(async () => unverified) });

  it("explains why New post does nothing, with a toast", async () => {
    pathname = "/home";
    renderLayout(sessionUnverified());
    const sidebar = await screen.findByRole("complementary");
    await within(sidebar).findByText("Ada Lovelace");
    await userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
    expect(
      await screen.findByText(
        "Verify your email to post. Check your inbox, or resend the link from the banner.",
      ),
    ).toBeInTheDocument();
  });

  it("resends from the banner, answers with a toast and starts the countdown", async () => {
    pathname = "/home";
    renderLayout(sessionUnverified());
    await userEvent.click(await screen.findByRole("button", { name: "Resend link" }));
    expect(resendMock).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText("We sent a new verification link. Check your inbox."),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Resend link \(60s\)/ })).toBeDisabled();
  });

  it("shows a throttled resend as a toast", async () => {
    pathname = "/home";
    resendMock.mockRejectedValue(
      new ApiError({ status: 429, code: "verification_email_throttled", detail: "Wait." }),
    );
    renderLayout(sessionUnverified());
    await userEvent.click(await screen.findByRole("button", { name: "Resend link" }));
    expect(
      await screen.findByText("We sent one recently. Wait a little before asking again."),
    ).toBeInTheDocument();
  });

  it("shows neither the banner nor a blocked New post to a verified user", async () => {
    pathname = "/home";
    renderLayout(sessionWith("authenticated"));
    const sidebar = await screen.findByRole("complementary");
    await within(sidebar).findByText("Ada Lovelace");
    expect(screen.queryByRole("button", { name: /Resend/ })).toBeNull();
    expect(within(sidebar).getByRole("button", { name: "New post" })).not.toHaveAttribute(
      "aria-disabled",
    );
  });
});

describe("(app) layout, the composer (Part 4)", () => {
  async function renderSignedIn() {
    pathname = "/home";
    renderLayout(sessionWith("authenticated"));
    const sidebar = await screen.findByRole("complementary");
    await within(sidebar).findByText("Ada Lovelace");
    return sidebar;
  }

  it("opens the composer from the rail's New post button", async () => {
    const sidebar = await renderSignedIn();
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
    expect(screen.getByRole("dialog", { name: "New post" })).toBeInTheDocument();
    expect(await screen.findByText(/fact posts left/)).toBeInTheDocument();
  });

  it("opens the same composer from the phone's New post tab", async () => {
    await renderSignedIn();
    const buttons = screen.getAllByRole("button", { name: "New post" });
    expect(buttons).toHaveLength(2); // the rail and the bottom tab
    await userEvent.click(buttons[1]);
    expect(screen.getByRole("dialog", { name: "New post" })).toBeInTheDocument();
  });

  it("keeps what you typed when the composer is closed and opened again", async () => {
    const sidebar = await renderSignedIn();
    const open = () => userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
    await open();
    await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), "Unfinished");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await open();
    expect(screen.getByRole("textbox", { name: "Post text" })).toHaveValue("Unfinished");
  });

  it("does not open it for an unverified user (the toast explains)", async () => {
    pathname = "/home";
    renderLayout(
      sessionWith("authenticated", {
        fetchMe: vi.fn(async () => ({ ...ME, is_email_verified: false })),
      }),
    );
    const sidebar = await screen.findByRole("complementary");
    await within(sidebar).findByText("Ada Lovelace");
    await userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(quotaMock).not.toHaveBeenCalled();
  });
});
