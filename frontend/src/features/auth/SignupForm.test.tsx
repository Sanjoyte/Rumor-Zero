import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import {
  resetTurnstileLoaderForTests,
  type TurnstileApi,
  type TurnstileRenderOptions,
} from "@/lib/turnstile";
import { SignupForm } from "./SignupForm";
import { allauthError, renderWithSession, testSession } from "./test-helpers";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
  usePathname: () => "/signup",
}));

const SITE_KEY = "1x00000000000000000000AA";
let widget: TurnstileRenderOptions | null = null;
let turnstile: TurnstileApi;
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  replace.mockClear();
  resetTurnstileLoaderForTests();
  widget = null;
  turnstile = {
    render: vi.fn((_el: HTMLElement, options: TurnstileRenderOptions) => {
      widget = options;
      return "widget-1";
    }),
    reset: vi.fn(),
    remove: vi.fn(),
  };
  window.turnstile = turnstile;
  // The live username check: everything is available.
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url) => {
    const name = new URL(String(url), "http://localhost").searchParams.get("u");
    return Response.json({ username: name, available: true, reason: null, message: "Available" });
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  delete window.turnstile;
  vi.unstubAllGlobals();
});

function solveTurnstile(token = "XXXX.DUMMY.TOKEN.XXXX") {
  act(() => widget?.callback?.(token));
}

async function fill({
  email = "ada@example.test",
  username = "ada",
  password = "correct-horse-battery-42",
} = {}) {
  const user = userEvent.setup();
  if (email) await user.type(screen.getByLabelText("Email address"), email);
  if (username) await user.type(screen.getByLabelText("Username"), username);
  if (password) await user.type(screen.getByLabelText("Password"), password);
  return user;
}

function submitButton() {
  return screen.getByRole("button", { name: "Create account" });
}

describe("SignupForm", () => {
  it("has the a2 fields, the Turnstile widget and the links", async () => {
    const { session } = testSession();
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    await waitFor(() => expect(widget?.sitekey).toBe(SITE_KEY));
    expect(screen.getByRole("link", { name: "Terms of Service" })).toHaveAttribute(
      "href",
      "/terms",
    );
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByText(/Turnstile bot defense/)).toBeNull();
    expect(screen.queryByText(/Complexity metric/)).toBeNull();
    expect(screen.queryByText(/Google/)).toBeNull();
  });

  it("keeps Create account disabled until Turnstile has a token", async () => {
    const { session } = testSession();
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    expect(submitButton()).toBeDisabled();
    solveTurnstile();
    expect(submitButton()).toBeEnabled();
    act(() => widget?.["expired-callback"]?.());
    expect(submitButton()).toBeDisabled();
  });

  it("validates before sending anything", async () => {
    const { session, api } = testSession();
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    solveTurnstile();
    const user = await fill({ email: "not-an-email", username: "a", password: "short" });
    await user.click(submitButton());
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getAllByText(/Usernames are 3–30 characters/).length).toBeGreaterThan(0);
    expect(screen.getByText("Use at least 8 characters.")).toBeInTheDocument();
    expect(api.signup).not.toHaveBeenCalled();
  });

  it("shows the live username check and the password strength", async () => {
    const { session } = testSession();
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await fill({ email: "", username: "Ada", password: "abc" });
    expect(await screen.findByText("Available: @ada")).toBeInTheDocument();
    expect(screen.getByText("Weak")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Password"), "defghijklmnop1!");
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });

  it("signs up with the normalised username and the token, then goes to /home", async () => {
    const { session, api } = testSession();
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    solveTurnstile("token-1");
    const user = await fill({ username: "  Ada_99 " });
    await user.click(submitButton());
    expect(api.signup).toHaveBeenCalledWith({
      email: "ada@example.test",
      username: "ada_99",
      password: "correct-horse-battery-42",
      turnstileToken: "token-1",
    });
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
  });

  it("shows the loading state while signing up", async () => {
    let finish!: (token: string) => void;
    const { session } = testSession({
      signup: vi.fn(() => new Promise<string>((r) => (finish = r))),
    });
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    solveTurnstile();
    const user = await fill();
    await user.click(submitButton());
    expect(submitButton()).toHaveAttribute("aria-busy", "true");
    finish("access-token");
    await waitFor(() => expect(replace).toHaveBeenCalled());
  });

  it.each([
    [
      "email",
      "email_taken",
      "A user is already registered with this email address.",
      "Email address",
    ],
    ["username", "username_taken", "A user is already registered with this username.", "Username"],
    ["username", "reserved_username", "This username is reserved.", "Username"],
    ["password", "password_too_common", "This password is too common.", "Password"],
  ])("puts the server's %s error (%s) on its field", async (param, code, message, label) => {
    const error = allauthError(400, [{ code, param, message }]);
    const { session } = testSession({ signup: vi.fn(async () => Promise.reject(error)) });
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    solveTurnstile();
    const user = await fill();
    await user.click(submitButton());
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByLabelText(label)).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("alert", { name: /banner/ })).toBeNull();
  });

  it("shows a failed bot check under the widget, resets it and waits for a new token", async () => {
    const error = allauthError(400, [
      {
        code: "turnstile_failed",
        param: "turnstile_token",
        message: "The bot check didn't pass. Try it again.",
      },
    ]);
    const { session } = testSession({ signup: vi.fn(async () => Promise.reject(error)) });
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    solveTurnstile();
    const user = await fill();
    await user.click(submitButton());

    const widgetArea = screen.getByTestId("turnstile").parentElement as HTMLElement;
    expect(await within(widgetArea).findByRole("alert")).toHaveTextContent(
      "The bot check didn't pass. Try it again.",
    );
    expect(turnstile.reset).toHaveBeenCalledWith("widget-1");
    expect(submitButton()).toBeDisabled();
    solveTurnstile("token-2");
    expect(submitButton()).toBeEnabled();
  });

  it.each([
    [allauthError(429), "Too many attempts. Try again in a few minutes."],
    [
      new ApiError({ status: 503, code: "backend_waking", detail: "waking" }),
      "The server is waking up. Try again in a minute.",
    ],
    [
      new ApiError({ status: 0, code: "network_error", detail: "offline" }),
      "Can't reach Rumor Zero. Check your connection and try again.",
    ],
  ])("shows a banner (and resets the widget) for %o", async (error, message) => {
    const { session } = testSession({ signup: vi.fn(async () => Promise.reject(error)) });
    renderWithSession(<SignupForm siteKey={SITE_KEY} />, session);
    await waitFor(() => expect(widget).not.toBeNull());
    solveTurnstile();
    const user = await fill();
    await user.click(submitButton());
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(turnstile.reset).toHaveBeenCalled();
  });

  it("is switched off without a site key", () => {
    const { session } = testSession();
    renderWithSession(<SignupForm siteKey="" />, session);
    expect(screen.getByText("Sign-up is unavailable right now.")).toBeInTheDocument();
    expect(screen.queryByTestId("turnstile")).toBeNull();
    expect(submitButton()).toBeDisabled();
  });
});
