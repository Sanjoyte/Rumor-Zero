import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { render } from "@testing-library/react";
import { MESSAGES } from "./messages";
import { ME, allauthError, renderWithSession, testSession } from "./test-helpers";
import { VerifyEmailStatus } from "./VerifyEmailStatus";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/verify-email/key",
}));

const mocks = vi.hoisted(() => ({
  verify: vi.fn<(key: string) => Promise<void>>(),
  resend: vi.fn<() => Promise<void>>(),
}));
vi.mock("@/lib/auth/auth-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/auth-api")>()),
  verifyEmail: mocks.verify,
  resendVerificationEmail: mocks.resend,
}));

const KEY = "Mg:1vABcd:abc-DEF_123";
const PARAM = "Mg%3A1vABcd%3Aabc-DEF_123";
const expired = () =>
  allauthError(400, [{ code: "invalid_or_expired_key", param: "key", message: "Expired." }]);

beforeEach(() => {
  mocks.verify.mockReset();
  mocks.verify.mockResolvedValue(undefined);
  mocks.resend.mockReset();
  mocks.resend.mockResolvedValue(undefined);
});

describe("VerifyEmailStatus", () => {
  it("decodes the route parameter once and POSTs the key, once", async () => {
    const { session } = testSession();
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    await screen.findByRole("heading", { name: "Your email is verified" });
    expect(mocks.verify).toHaveBeenCalledTimes(1);
    expect(mocks.verify).toHaveBeenCalledWith(KEY);
  });

  it("sends one request even when React StrictMode runs the effect twice", async () => {
    const { session } = testSession();
    render(
      <StrictMode>
        <AuthProvider session={session}>
          <VerifyEmailStatus keyParam={PARAM} />
        </AuthProvider>
      </StrictMode>,
    );
    await screen.findByRole("heading", { name: "Your email is verified" });
    expect(mocks.verify).toHaveBeenCalledTimes(1);
  });

  it("shows Verifying… and waits for the session before it sends anything", async () => {
    const { session } = testSession(
      { refresh: vi.fn(() => new Promise<string>(() => {})) },
      { loggedIn: true },
    );
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(screen.getByRole("heading", { name: "Verifying…" })).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(mocks.verify).not.toHaveBeenCalled();
  });

  it("verifies for a visitor who isn't logged in: log in to start posting", async () => {
    const { session, api } = testSession();
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(await screen.findByRole("link", { name: /Log in to start posting/ })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(api.fetchMe).not.toHaveBeenCalled();
  });

  it("verifies for a signed-in user, reloads /me and offers Start posting", async () => {
    // The first /me (session restore) is unverified; the one after the verification isn't.
    const fetchMe = vi
      .fn()
      .mockResolvedValueOnce(ME)
      .mockResolvedValue({ ...ME, is_email_verified: true });
    const { session } = testSession({ fetchMe }, { loggedIn: true });
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(await screen.findByRole("link", { name: /Start posting/ })).toHaveAttribute(
      "href",
      "/home",
    );
    await waitFor(() => expect(session.getState().user?.is_email_verified).toBe(true));
    expect(fetchMe).toHaveBeenCalledTimes(2);
  });

  it("still verifies when reloading /me fails", async () => {
    const fetchMe = vi.fn().mockResolvedValueOnce(ME).mockRejectedValue(new Error("offline"));
    const { session } = testSession({ fetchMe }, { loggedIn: true });
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(await screen.findByRole("link", { name: /Start posting/ })).toBeInTheDocument();
  });

  it("shows the expired state with a login link to an anonymous visitor", async () => {
    mocks.verify.mockRejectedValue(expired());
    const { session } = testSession();
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Log in to send a new link" })).toHaveAttribute(
      "href",
      "/login?next=%2Fverify-email",
    );
  });

  it("offers a working inline resend to a signed-in user with an expired link", async () => {
    mocks.verify.mockRejectedValue(expired());
    const user = userEvent.setup();
    const { session } = testSession({}, { loggedIn: true });
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    await user.click(await screen.findByRole("button", { name: "Send a new link" }));
    expect(mocks.resend).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(MESSAGES.resendSent)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send a new link \(60s\)/ })).toBeDisabled();
  });

  it("says 'already verified' when the link was used and the user is verified", async () => {
    mocks.verify.mockRejectedValue(expired());
    const { session } = testSession(
      { fetchMe: vi.fn(async () => ({ ...ME, is_email_verified: true })) },
      { loggedIn: true },
    );
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(
      await screen.findByRole("heading", { name: "Your email is already verified" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /Start posting/ })).toHaveAttribute("href", "/home");
  });

  it.each(["", "a b", "a%2Fb", "%E0%A4%A", "ünï", "a".repeat(301)])(
    "refuses a malformed key (%j) without a request",
    async (param) => {
      const { session } = testSession();
      renderWithSession(<VerifyEmailStatus keyParam={param} />, session);
      expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeVisible();
      expect(mocks.verify).not.toHaveBeenCalled();
    },
  );

  it("doesn't call a network failure an expired link, and can try again", async () => {
    mocks.verify.mockRejectedValueOnce(
      new ApiError({ status: 0, code: "network_error", detail: "" }),
    );
    const user = userEvent.setup();
    const { session } = testSession();
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(await screen.findByText(MESSAGES.network)).toBeInTheDocument();
    expect(screen.queryByText("This link has expired")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Your email is verified" })).toBeVisible();
    expect(mocks.verify).toHaveBeenCalledTimes(2);
  });

  it("a rate-limited verify is reported, not 'expired'", async () => {
    mocks.verify.mockRejectedValue(new ApiError({ status: 429, code: "throttled", detail: "" }));
    const { session } = testSession();
    renderWithSession(<VerifyEmailStatus keyParam={PARAM} />, session);
    expect(await screen.findByText(MESSAGES.rateLimited)).toBeInTheDocument();
  });
});
