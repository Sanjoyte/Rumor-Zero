import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { ApiError } from "@/lib/api/client";
import { ChangePasswordModal } from "./ChangePasswordModal";
import { SETTINGS_MESSAGES } from "./messages";
import { renderSettings } from "./test-helpers";

const api = vi.hoisted(() => ({ changePassword: vi.fn() }));
vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  ...api,
}));

let onClose: Mock<() => void>;
beforeEach(() => {
  api.changePassword.mockReset();
  onClose = vi.fn<() => void>();
});

function setup(open = true) {
  return renderSettings(<ChangePasswordModal open={open} onClose={onClose} />);
}

async function fill(
  user: ReturnType<typeof userEvent.setup>,
  current: string,
  next: string,
  confirm = next,
) {
  if (current) await user.type(screen.getByLabelText("Current password"), current);
  await user.type(screen.getByLabelText("New password"), next);
  await user.type(screen.getByLabelText("Confirm new password"), confirm);
}

const submit = () => screen.getByRole("button", { name: "Change password" });

describe("ChangePasswordModal", () => {
  it("has three password fields and says the other devices are signed out", () => {
    setup();
    expect(screen.getByRole("dialog", { name: "Change password" })).toBeInTheDocument();
    for (const label of ["Current password", "New password", "Confirm new password"]) {
      expect(screen.getByLabelText(label)).toHaveAttribute("type", "password");
    }
    expect(screen.getByText(/other devices are signed out/)).toBeInTheDocument();
  });

  it("changes the password, closes and tells you", async () => {
    const user = userEvent.setup();
    api.changePassword.mockResolvedValue(undefined);
    setup();
    await fill(user, "old-password-1", "a-new-long-password-2");
    await user.click(submit());

    expect(api.changePassword).toHaveBeenCalledWith("old-password-1", "a-new-long-password-2");
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(SETTINGS_MESSAGES.passwordChanged)).toBeInTheDocument();
  });

  it("submits with Enter", async () => {
    const user = userEvent.setup();
    api.changePassword.mockResolvedValue(undefined);
    setup();
    await fill(user, "old-password-1", "a-new-long-password-2");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(api.changePassword).toHaveBeenCalledTimes(1));
  });

  it("checks the confirmation, the length and the missing current password first", async () => {
    const user = userEvent.setup();
    setup();
    await fill(user, "", "short", "different");
    await user.click(submit());

    expect(api.changePassword).not.toHaveBeenCalled();
    expect(screen.getByText("Enter your current password.")).toBeInTheDocument();
    expect(screen.getByText("Use at least 8 characters.")).toBeInTheDocument();
    expect(screen.getByText("The two passwords don't match.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveFocus();
  });

  it("puts a wrong current password and a weak new one on their fields", async () => {
    const user = userEvent.setup();
    api.changePassword.mockRejectedValue(
      new ApiError({
        status: 400,
        code: "invalid",
        detail: "x",
        fieldErrors: {
          current_password: ["That password is not right."],
          new_password: ["This password is too common."],
        },
      }),
    );
    setup();
    await fill(user, "wrong-password", "password1234");
    await user.click(submit());

    expect(await screen.findByText("That password is not right.")).toBeInTheDocument();
    expect(screen.getByText("This password is too common.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveFocus();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("says a Google-only account has no password to change", async () => {
    const user = userEvent.setup();
    api.changePassword.mockRejectedValue(
      new ApiError({ status: 409, code: "password_not_set", detail: "x" }),
    );
    setup();
    await fill(user, "whatever-1", "a-new-long-password-2");
    await user.click(submit());
    expect(await screen.findByText(SETTINGS_MESSAGES.noPassword)).toBeInTheDocument();
  });

  it("answers a throttle with a banner", async () => {
    const user = userEvent.setup();
    api.changePassword.mockRejectedValue(
      new ApiError({ status: 429, code: "throttled", detail: "x" }),
    );
    setup();
    await fill(user, "old-password-1", "a-new-long-password-2");
    await user.click(submit());
    expect(await screen.findByText(SETTINGS_MESSAGES.rateLimited)).toBeInTheDocument();
  });

  it("can't be closed or repeated while the request runs", async () => {
    const user = userEvent.setup();
    let finish: () => void = () => {};
    api.changePassword.mockReturnValue(new Promise<void>((resolve) => (finish = resolve)));
    setup();
    await fill(user, "old-password-1", "a-new-long-password-2");
    await user.click(submit());

    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).not.toHaveBeenCalled();
    expect(api.changePassword).toHaveBeenCalledTimes(1);
    finish();
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("opens empty every time", async () => {
    const user = userEvent.setup();
    const view = setup();
    await user.type(screen.getByLabelText("Current password"), "left-behind");
    view.rerender(<ChangePasswordModal open={false} onClose={onClose} />);
    view.rerender(<ChangePasswordModal open onClose={onClose} />);
    expect(screen.getByLabelText("Current password")).toHaveValue("");
  });

  it("shows the strength of the new password", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByLabelText("New password"), "a-really-long-passphrase-1");
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });
});
