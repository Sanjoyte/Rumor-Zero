import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { LoginForm } from "./LoginForm";
import { allauthError, renderWithSession, testSession } from "./test-helpers";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
  usePathname: () => "/login",
}));

beforeEach(() => {
  replace.mockClear();
  window.history.pushState({}, "", "/login");
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

async function fillAndSubmit(email = "ada@example.test", password = "correct-horse") {
  const user = userEvent.setup();
  if (email) await user.type(screen.getByLabelText("Email address"), email);
  if (password) await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: /Log in/ }));
  return user;
}

describe("LoginForm", () => {
  it("has the a3 fields and link, and none of the dropped extras", () => {
    const { session } = testSession();
    renderWithSession(<LoginForm />, session);
    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByRole("link", { name: "Sign up" })).toHaveAttribute("href", "/signup");
    expect(screen.queryByText(/Remember me/)).toBeNull();
    expect(screen.queryByText(/Attempt/)).toBeNull();
    expect(screen.queryByText(/Google/)).toBeNull();
  });

  it("validates before sending anything", async () => {
    const { session, api } = testSession();
    renderWithSession(<LoginForm />, session);
    await fillAndSubmit("", "");
    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toHaveAttribute("aria-invalid", "true");
    expect(api.login).not.toHaveBeenCalled();
  });

  it("logs in and goes to /home", async () => {
    const { session, api } = testSession();
    renderWithSession(<LoginForm />, session);
    await fillAndSubmit(" ada@example.test ", "correct-horse");
    expect(api.login).toHaveBeenCalledWith("ada@example.test", "correct-horse");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
  });

  it.each([
    ["/login?next=%2Fsettings%3Ftab%3Demail", "/settings?tab=email"],
    ["/login?next=%2F%2Fevil.com", "/home"],
    ["/login?next=%2Fapi%2Fauth%2Flogout%2F", "/home"],
  ])("from %s it goes to %s", async (address, target) => {
    window.history.pushState({}, "", address);
    const { session } = testSession();
    renderWithSession(<LoginForm />, session);
    await fillAndSubmit();
    await waitFor(() => expect(replace).toHaveBeenCalledWith(target));
  });

  it("sends a visitor who is already logged in straight on", async () => {
    const { session } = testSession({}, { loggedIn: true });
    renderWithSession(<LoginForm />, session);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
  });

  it("shows the loading state while logging in", async () => {
    let finish!: (token: string) => void;
    const { session } = testSession({
      login: vi.fn(() => new Promise<string>((r) => (finish = r))),
    });
    renderWithSession(<LoginForm />, session);
    await fillAndSubmit();
    const button = screen.getByRole("button", { name: /Log in/ });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    finish("access-token");
    await waitFor(() => expect(replace).toHaveBeenCalled());
  });

  it.each([
    [
      allauthError(400, [
        {
          code: "email_password_mismatch",
          param: "password",
          message: "The email address and/or password you specified are not correct.",
        },
      ]),
      "That email and password don't match.",
    ],
    [
      allauthError(400, [
        { code: "too_many_login_attempts", message: "Too many failed login attempts." },
      ]),
      "Too many attempts. Try again in a few minutes.",
    ],
    [allauthError(429), "Too many attempts. Try again in a few minutes."],
    [
      new ApiError({ status: 503, code: "backend_waking", detail: "waking" }),
      "The server is waking up. Try again in a minute.",
    ],
    [
      allauthError(403, [{ code: "csrf_failed", message: "Reload the page and try again." }]),
      "Something went wrong. Reload the page and try again.",
    ],
    [
      new ApiError({ status: 0, code: "network_error", detail: "offline" }),
      "Can't reach Rumor Zero. Check your connection and try again.",
    ],
  ])("shows a dismissible banner for %o", async (error, message) => {
    const { session } = testSession({ login: vi.fn(async () => Promise.reject(error)) });
    renderWithSession(<LoginForm />, session);
    const user = await fillAndSubmit();
    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent(message);
    expect(screen.getByRole("button", { name: /Log in/ })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  it("puts a server email error on the email field", async () => {
    const error = allauthError(400, [
      { code: "invalid", param: "email", message: "Enter a valid email address." },
    ]);
    const { session } = testSession({ login: vi.fn(async () => Promise.reject(error)) });
    renderWithSession(<LoginForm />, session);
    await fillAndSubmit("ada@localhost", "pw-123456");
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toHaveAttribute("aria-invalid", "true");
  });
});
