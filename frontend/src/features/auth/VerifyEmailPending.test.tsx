import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { MESSAGES } from "./messages";
import { ME, renderWithSession, testSession } from "./test-helpers";
import { VerifyEmailPending } from "./VerifyEmailPending";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/verify-email",
}));

const resendMock = vi.hoisted(() => vi.fn<() => Promise<void>>());
vi.mock("@/lib/auth/auth-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/auth-api")>()),
  resendVerificationEmail: resendMock,
}));

beforeEach(() => {
  push.mockClear();
  resendMock.mockReset();
  resendMock.mockResolvedValue(undefined);
  window.history.pushState({}, "", "/verify-email");
});

afterEach(() => {
  vi.useRealTimers();
  window.history.pushState({}, "", "/");
});

describe("VerifyEmailPending", () => {
  it("shows a placeholder while the session is restored", () => {
    const { session } = testSession(
      { refresh: vi.fn(() => new Promise<string>(() => {})) },
      { loggedIn: true },
    );
    renderWithSession(<VerifyEmailPending />, session);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Resend/ })).toBeNull();
  });

  it("tells a signed-in, unverified user where the link went, and what is limited", async () => {
    const { session } = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailPending />, session);
    expect(await screen.findByRole("heading", { name: "Verify your email" })).toBeInTheDocument();
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    expect(screen.getByText("Read-only for now")).toBeInTheDocument();
    expect(screen.getByText(/spam or junk folder/)).toBeInTheDocument();
    expect(screen.getByText(/expire 24 hours after they're sent/)).toBeInTheDocument();
    // a4's dev-only pieces are gone.
    expect(screen.queryByText(/Simulate/)).toBeNull();
    expect(screen.queryByText(/Pending Verification State/)).toBeNull();
  });

  it("starts the resend countdown at 60 s and enables Resend when it ends", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { session } = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailPending />, session);
    const button = await screen.findByRole("button", { name: /Resend email/ });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Resend email (60s)");

    for (let i = 0; i < 60; i += 1) act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByRole("button", { name: "Resend email" })).toBeEnabled();
    expect(resendMock).not.toHaveBeenCalled();
  });

  it("resends, announces it, and starts the countdown again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { session } = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailPending />, session);
    await screen.findByRole("button", { name: /Resend email/ });
    for (let i = 0; i < 60; i += 1) act(() => vi.advanceTimersByTime(1000));

    await user.click(screen.getByRole("button", { name: "Resend email" }));

    expect(resendMock).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(MESSAGES.resendSent)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Resend email/ })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(MESSAGES.resendSent);
  });

  it("explains a throttled resend", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    resendMock.mockRejectedValue(
      new ApiError({ status: 429, code: "verification_email_throttled", detail: "Wait." }),
    );
    const { session } = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailPending />, session);
    await screen.findByRole("button", { name: /Resend email/ });
    for (let i = 0; i < 60; i += 1) act(() => vi.advanceTimersByTime(1000));
    await user.click(screen.getByRole("button", { name: "Resend email" }));
    expect(await screen.findByText(MESSAGES.resendThrottled)).toBeInTheDocument();
  });

  it("continues browsing to /home, or to a safe ?next=", async () => {
    const user = userEvent.setup();
    const { session } = testSession({}, { loggedIn: true });
    const { unmount } = renderWithSession(<VerifyEmailPending />, session);
    await user.click(await screen.findByRole("link", { name: /Continue browsing read-only/ }));
    expect(push).toHaveBeenLastCalledWith("/home");
    unmount();

    window.history.pushState({}, "", "/verify-email?next=%2Fsettings");
    const second = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailPending />, second.session);
    await user.click(await screen.findByRole("link", { name: /Continue browsing read-only/ }));
    expect(push).toHaveBeenLastCalledWith("/settings");
  });

  it.each(["//evil.com", "/reset-password/abc", "https://evil.com"])(
    "ignores an unsafe ?next= (%s)",
    async (next) => {
      window.history.pushState({}, "", `/verify-email?next=${encodeURIComponent(next)}`);
      const user = userEvent.setup();
      const { session } = testSession({}, { loggedIn: true });
      renderWithSession(<VerifyEmailPending />, session);
      await user.click(await screen.findByRole("link", { name: /Continue browsing read-only/ }));
      expect(push).toHaveBeenLastCalledWith("/home");
    },
  );

  it("welcomes a verified user and offers to start posting", async () => {
    const { session } = testSession(
      { fetchMe: vi.fn(async () => ({ ...ME, is_email_verified: true })) },
      { loggedIn: true },
    );
    renderWithSession(<VerifyEmailPending />, session);
    expect(await screen.findByRole("heading", { name: "Your email is verified" })).toBeVisible();
    expect(screen.getByRole("link", { name: /Start posting/ })).toHaveAttribute("href", "/home");
    expect(screen.queryByRole("button", { name: /Resend/ })).toBeNull();
  });

  it("switches to the verified view when another tab verifies the address", async () => {
    const { session, api } = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailPending />, session);
    await screen.findByRole("button", { name: /Resend email/ });
    api.fetchMe.mockResolvedValue({ ...ME, is_email_verified: true });
    await act(async () => {
      await session.reloadMe();
    });
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Your email is verified" })).toBeVisible(),
    );
  });

  it("is not a redirect: an anonymous visitor gets check-your-inbox and a login link", async () => {
    const { session } = testSession();
    renderWithSession(<VerifyEmailPending />, session);
    expect(await screen.findByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in to resend" })).toHaveAttribute(
      "href",
      "/login?next=%2Fverify-email",
    );
    expect(screen.queryByRole("button", { name: /Resend/ })).toBeNull();
  });
});
