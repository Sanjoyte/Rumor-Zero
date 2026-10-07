import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { ForgotPasswordForm } from "./ForgotPasswordForm";
import { allauthError } from "./test-helpers";
import { MESSAGES } from "./messages";

const requestMock = vi.hoisted(() => vi.fn<(email: string) => Promise<void>>());
vi.mock("@/lib/auth/auth-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/auth-api")>()),
  requestPasswordReset: requestMock,
}));

beforeEach(() => {
  requestMock.mockReset();
  requestMock.mockResolvedValue(undefined);
});

async function submit(email: string) {
  const user = userEvent.setup();
  if (email) await user.type(screen.getByLabelText("Email address"), email);
  await user.click(screen.getByRole("button", { name: /Send reset link/ }));
  return user;
}

describe("ForgotPasswordForm", () => {
  it("starts idle, with a way back to log in", () => {
    render(<ForgotPasswordForm />);
    expect(screen.getByRole("heading", { name: "Reset your password" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to log in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByText(/If an account exists/)).toBeNull();
    // a5's jargon and enumeration notice are gone.
    expect(screen.queryByText(/Secured Node/)).toBeNull();
    expect(screen.queryByText(/Protocol standard/)).toBeNull();
    expect(screen.queryByText(/enumeration/)).toBeNull();
  });

  it("sends the trimmed address and shows the sent state, which replaces the form", async () => {
    render(<ForgotPasswordForm />);
    await submit("  ada@example.test ");
    expect(requestMock).toHaveBeenCalledWith("ada@example.test");
    expect(await screen.findByText(/If an account exists for/)).toHaveTextContent(
      "If an account exists for ada@example.test, we've sent a link to reset your password. It expires in 24 hours.",
    );
    expect(screen.queryByLabelText("Email address")).toBeNull();
    expect(screen.queryByRole("button", { name: /Send reset link/ })).toBeNull();
  });

  it("shows the same sent text whatever the address (nothing depends on the server's answer)", async () => {
    const texts: string[] = [];
    for (const address of ["exists@example.test", "ghost@example.test"]) {
      const { unmount } = render(<ForgotPasswordForm />);
      await submit(address);
      const sent = await screen.findByText(/If an account exists for/);
      texts.push((sent.textContent ?? "").replace(address, "ADDRESS"));
      unmount();
    }
    expect(texts[0]).toBe(texts[1]);
  });

  it("goes back to the idle form to use a different address", async () => {
    render(<ForgotPasswordForm />);
    const user = await submit("ada@example.test");
    await user.click(await screen.findByRole("button", { name: "Use a different email" }));
    expect(screen.getByLabelText("Email address")).toHaveValue("ada@example.test");
  });

  it.each([
    ["", "Enter your email address."],
    ["not-an-email", "Enter a valid email address."],
  ])("checks %j in the browser first", async (value, message) => {
    render(<ForgotPasswordForm />);
    await submit(value);
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(requestMock).not.toHaveBeenCalled();
  });

  it("shows the server's malformed-email error on the field", async () => {
    requestMock.mockRejectedValue(
      allauthError(400, [
        { code: "invalid", param: "email", message: "Enter a valid email address." },
      ]),
    );
    render(<ForgotPasswordForm />);
    await submit("a@b");
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.queryByText(/If an account exists/)).toBeNull();
  });

  it.each([
    [429, "throttled", MESSAGES.rateLimited],
    [503, "backend_waking", MESSAGES.waking],
    [0, "network_error", MESSAGES.network],
    [500, "http_500", MESSAGES.generic],
  ])("reports a %i as a banner and keeps the form", async (status, code, message) => {
    requestMock.mockRejectedValue(new ApiError({ status, code, detail: "" }));
    render(<ForgotPasswordForm />);
    await submit("ada@example.test");
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("Email address")).toHaveValue("ada@example.test");
    expect(screen.queryByText(/If an account exists/)).toBeNull();
  });

  it("shows the loading state while sending", async () => {
    let finish!: () => void;
    requestMock.mockImplementation(() => new Promise<void>((resolve) => (finish = resolve)));
    render(<ForgotPasswordForm />);
    await submit("ada@example.test");
    expect(screen.getByRole("button", { name: /Send reset link/ })).toHaveAttribute(
      "aria-busy",
      "true",
    );
    finish();
    expect(await screen.findByText(/If an account exists/)).toBeInTheDocument();
  });
});
