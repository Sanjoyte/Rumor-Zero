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
  resendMock.mockReset();
  resendMock.mockResolvedValue(undefined);
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
