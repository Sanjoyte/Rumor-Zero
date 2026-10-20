import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DeleteAccountModal } from "./DeleteAccountModal";
import { SETTINGS_MESSAGES } from "./messages";
import { renderSettings } from "./test-helpers";

const api = vi.hoisted(() => ({ deleteAccount: vi.fn() }));
vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  ...api,
}));

let onClose: Mock<() => void>;
let onDeleted: Mock<() => void>;
beforeEach(() => {
  api.deleteAccount.mockReset();
  onClose = vi.fn<() => void>();
  onDeleted = vi.fn<() => void>();
});

function setup(hasPassword = true) {
  return renderSettings(
    <DeleteAccountModal
      open
      username="ada"
      hasPassword={hasPassword}
      onClose={onClose}
      onDeleted={onDeleted}
    />,
  );
}

const deleteButton = () => screen.getByRole("button", { name: "Delete account" });

describe("DeleteAccountModal", () => {
  it("says what goes and what stays, and that it can't be undone", () => {
    setup();
    expect(screen.getByRole("dialog", { name: "Delete your account?" })).toBeInTheDocument();
    expect(screen.getByText(/can't be undone/)).toBeInTheDocument();
    expect(screen.getByText("What goes")).toBeInTheDocument();
    expect(screen.getByText(/Moderation records keep a copy of removed posts/)).toBeInTheDocument();
    expect(api.deleteAccount).not.toHaveBeenCalled();
  });

  it("stays off until the password is typed, then deletes with it", async () => {
    const user = userEvent.setup();
    api.deleteAccount.mockResolvedValue(undefined);
    setup();
    expect(deleteButton()).toBeDisabled();
    await user.type(screen.getByLabelText("Your password"), "my-password-1");
    await user.click(deleteButton());

    expect(api.deleteAccount).toHaveBeenCalledWith({ password: "my-password-1" });
    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
  });

  it("confirms an account without a password by its username", async () => {
    const user = userEvent.setup();
    api.deleteAccount.mockResolvedValue(undefined);
    setup(false);
    const input = screen.getByLabelText("Type your username to confirm");
    expect(screen.queryByLabelText("Your password")).toBeNull();
    await user.type(input, "ad");
    expect(deleteButton()).toBeDisabled();
    await user.type(input, "a ");
    expect(deleteButton()).toBeEnabled(); // the server trims and lowercases too
    await user.click(deleteButton());
    expect(api.deleteAccount).toHaveBeenCalledWith({ username: "ada " });
    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
  });

  it("puts a wrong password on the field and deletes nothing", async () => {
    const user = userEvent.setup();
    api.deleteAccount.mockRejectedValue(
      new ApiError({
        status: 400,
        code: "invalid",
        detail: "x",
        fieldErrors: { password: ["That password is not right."] },
      }),
    );
    setup();
    await user.type(screen.getByLabelText("Your password"), "wrong");
    await user.click(deleteButton());
    expect(await screen.findByText("That password is not right.")).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it.each([
    [403, "staff_account", SETTINGS_MESSAGES.staffAccount],
    [429, "throttled", SETTINGS_MESSAGES.rateLimited],
    [0, "network_error", SETTINGS_MESSAGES.network],
  ])("answers a %s with a banner", async (status, code, message) => {
    const user = userEvent.setup();
    api.deleteAccount.mockRejectedValue(new ApiError({ status, code, detail: "x" }));
    setup();
    await user.type(screen.getByLabelText("Your password"), "pw-123456");
    await user.click(deleteButton());
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("can't be closed while the request runs", async () => {
    const user = userEvent.setup();
    let finish: () => void = () => {};
    api.deleteAccount.mockReturnValue(new Promise<void>((resolve) => (finish = resolve)));
    setup();
    await user.type(screen.getByLabelText("Your password"), "pw-123456");
    await user.click(deleteButton());
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).not.toHaveBeenCalled();
    finish();
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("Cancel closes it", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.deleteAccount).not.toHaveBeenCalled();
  });
});
