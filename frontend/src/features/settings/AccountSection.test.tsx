import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AccountSection } from "./AccountSection";
import { renderSettings, SETTINGS_ME } from "./test-helpers";

vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  changePassword: vi.fn(),
}));

function setup(me = {}) {
  return renderSettings(<AccountSection user={{ ...SETTINGS_ME, ...me }} />, me);
}

describe("AccountSection", () => {
  it("shows the email with a Verified chip", () => {
    setup();
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Verify email" })).toBeNull();
  });

  it("an unverified address says so and links to the verification page", () => {
    setup({ is_email_verified: false });
    expect(screen.getByText("Not verified")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verify email" })).toHaveAttribute(
      "href",
      "/verify-email",
    );
  });

  it("offers Change password to an account with a password, and opens the modal", async () => {
    const user = userEvent.setup();
    setup();
    expect(screen.queryByText("Signed in with Google")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("dialog", { name: "Change password" })).toBeInTheDocument();
  });

  it("a Google-only account is pointed at Forgot password instead", () => {
    setup({ has_usable_password: false, google_connected: true });
    expect(screen.getByText("Signed in with Google")).toBeInTheDocument();
    expect(screen.getByText(/use Forgot password/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set a password" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
    expect(screen.queryByRole("button", { name: "Change password" })).toBeNull();
  });

  it("shows the Google link only when there is one", () => {
    const { unmount } = setup({ google_connected: true });
    expect(screen.getByText("Google sign-in connected")).toBeInTheDocument();
    unmount();
    setup({ google_connected: false });
    expect(screen.queryByText("Google sign-in connected")).toBeNull();
  });
});
