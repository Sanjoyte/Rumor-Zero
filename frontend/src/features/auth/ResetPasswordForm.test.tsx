import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { MESSAGES } from "./messages";
import { ResetPasswordForm } from "./ResetPasswordForm";
import { allauthError, testSession } from "./test-helpers";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
  usePathname: () => "/reset-password/key",
}));

const mocks = vi.hoisted(() => ({
  check: vi.fn<(key: string) => Promise<void>>(),
  reset: vi.fn<(key: string, password: string) => Promise<string>>(),
}));
vi.mock("@/lib/auth/auth-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/auth-api")>()),
  checkResetKey: mocks.check,
  resetPassword: mocks.reset,
}));

const KEY = "0123456789abcdef0123456789abcdef-1abc-0fed1234";
const NEW_PASSWORD = "a-brand-new-passphrase-77";

function renderForm(keyParam = KEY, strict = false) {
  const { session, api } = testSession();
  const tree: ReactNode = (
    <AuthProvider session={session}>
      <ToastProvider>
        <ResetPasswordForm keyParam={keyParam} />
      </ToastProvider>
    </AuthProvider>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return { session, api };
}

async function fillAndSubmit(password = NEW_PASSWORD, confirm = password) {
  const user = userEvent.setup();
  await screen.findByLabelText("New password");
  if (password) await user.type(screen.getByLabelText("New password"), password);
  if (confirm) await user.type(screen.getByLabelText("Confirm new password"), confirm);
  await user.click(screen.getByRole("button", { name: /Reset password & log in/ }));
  return user;
}

beforeEach(() => {
  replace.mockClear();
  mocks.check.mockReset();
  mocks.check.mockResolvedValue(undefined);
  mocks.reset.mockReset();
  mocks.reset.mockResolvedValue("access-token");
});

describe("ResetPasswordForm: the key check", () => {
  it("shows a skeleton while the key is checked, then the form", async () => {
    let finish!: () => void;
    mocks.check.mockImplementation(() => new Promise<void>((resolve) => (finish = resolve)));
    renderForm();
    expect(screen.getByText("Checking your link…")).toBeInTheDocument();
    expect(screen.queryByLabelText("New password")).toBeNull();
    finish();
    expect(await screen.findByLabelText("New password")).toBeInTheDocument();
    expect(mocks.check).toHaveBeenCalledWith(KEY);
  });

  it("checks the key once, even in StrictMode", async () => {
    renderForm(KEY, true);
    await screen.findByLabelText("New password");
    expect(mocks.check).toHaveBeenCalledTimes(1);
  });

  it("decodes the route parameter once", async () => {
    renderForm("0123abcd%2D1abc%2D0fed");
    await screen.findByLabelText("New password");
    expect(mocks.check).toHaveBeenCalledWith("0123abcd-1abc-0fed");
  });

  it("shows the expired state before anyone types a password", async () => {
    mocks.check.mockRejectedValue(
      allauthError(400, [{ code: "invalid_password_reset", message: "Bad link." }]),
    );
    renderForm();
    expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Request a new link" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
    expect(screen.queryByLabelText("New password")).toBeNull();
  });

  it.each(["", "ABC-1-2", "a:b", "a b", "ünï", "%E0%A4%A", "a".repeat(201)])(
    "refuses a malformed key (%j) with no request",
    async (param) => {
      renderForm(param);
      expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeVisible();
      expect(mocks.check).not.toHaveBeenCalled();
    },
  );

  it("still shows the form when the check itself can't run (the submit decides)", async () => {
    mocks.check.mockRejectedValue(
      new ApiError({ status: 503, code: "backend_waking", detail: "" }),
    );
    renderForm();
    expect(await screen.findByLabelText("New password")).toBeInTheDocument();
  });
});

describe("ResetPasswordForm: the form", () => {
  it("shows a6's fields, the 8-character hint and the sign-out callout", async () => {
    renderForm();
    expect(await screen.findByRole("heading", { name: "Create new password" })).toBeVisible();
    expect(screen.getByText(/Use at least 8 characters/)).toBeInTheDocument();
    expect(screen.queryByText(/12 characters/)).toBeNull();
    expect(screen.getByText("This also signs you out on your other devices.")).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByText("Password strength")).toBeInTheDocument();
    // a6's jargon is gone.
    expect(screen.queryByText(/Audit Trail/)).toBeNull();
    expect(screen.queryByText(/Cryptographic/)).toBeNull();
  });

  it("has a show/hide toggle on both fields", async () => {
    renderForm();
    await screen.findByLabelText("New password");
    expect(screen.getAllByRole("button", { name: "Show password" })).toHaveLength(2);
  });

  it("rates the password as you type", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("New password"), "abc");
    expect(screen.getByText("Weak")).toBeInTheDocument();
    await user.type(screen.getByLabelText("New password"), "defghijklmnop1!");
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });

  it("rejects a short password in the browser", async () => {
    renderForm();
    await fillAndSubmit("short");
    expect(screen.getByText("Use at least 8 characters.")).toBeInTheDocument();
    expect(mocks.reset).not.toHaveBeenCalled();
  });

  it("rejects mismatching passwords on the confirm field", async () => {
    renderForm();
    await fillAndSubmit(NEW_PASSWORD, "something-else-entirely");
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm new password")).toHaveAttribute("aria-invalid", "true");
    expect(mocks.reset).not.toHaveBeenCalled();
  });

  it("shows the server's password errors on the password field and keeps the form", async () => {
    mocks.reset.mockRejectedValue(
      allauthError(400, [
        { code: "password_too_common", param: "password", message: "This password is too common." },
      ]),
    );
    renderForm();
    await fillAndSubmit("password1234");
    expect(await screen.findByText("This password is too common.")).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toHaveAttribute("aria-invalid", "true");
    expect(replace).not.toHaveBeenCalled();
  });

  it("switches to the expired state when the key died while the form was open", async () => {
    mocks.reset.mockRejectedValue(
      allauthError(400, [{ code: "invalid_password_reset", param: "key", message: "Bad link." }]),
    );
    renderForm();
    await fillAndSubmit();
    expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeVisible();
  });

  it.each([
    [429, "throttled", MESSAGES.rateLimited],
    [503, "backend_waking", MESSAGES.waking],
    [0, "network_error", MESSAGES.network],
  ])("reports a %i as a banner and keeps what was typed", async (status, code, message) => {
    mocks.reset.mockRejectedValue(new ApiError({ status, code, detail: "" }));
    renderForm();
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("New password")).toHaveValue(NEW_PASSWORD);
  });

  it("shows the loading state while resetting", async () => {
    let finish!: (token: string) => void;
    mocks.reset.mockImplementation(() => new Promise<string>((resolve) => (finish = resolve)));
    renderForm();
    await fillAndSubmit();
    expect(screen.getByRole("button", { name: /Reset password & log in/ })).toHaveAttribute(
      "aria-busy",
      "true",
    );
    finish("access-token");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
  });
});

describe("ResetPasswordForm: success", () => {
  it("logs in with the returned token, confirms with a toast and goes to /home", async () => {
    const { session, api } = renderForm();
    await fillAndSubmit();
    expect(mocks.reset).toHaveBeenCalledWith(KEY, NEW_PASSWORD);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home"));
    expect(api.fetchMe).toHaveBeenCalledWith("access-token");
    expect(session.getState().status).toBe("authenticated");
    expect(await screen.findByText(MESSAGES.passwordChanged)).toBeInTheDocument();
    expect(api.login).not.toHaveBeenCalled();
  });

  it("goes to /login with a different toast when only loading the account failed", async () => {
    const { session, api } = renderForm();
    api.fetchMe.mockRejectedValue(new ApiError({ status: 500, code: "http_500", detail: "" }));
    await fillAndSubmit();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(await screen.findByText(MESSAGES.passwordChangedLogIn)).toBeInTheDocument();
    expect(session.getState().status).not.toBe("authenticated");
  });
});
