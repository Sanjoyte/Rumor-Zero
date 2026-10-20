import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { SETTINGS_MESSAGES } from "./messages";
import { MAX_BIO, ProfileForm } from "./ProfileForm";
import { renderSettings, SETTINGS_ME } from "./test-helpers";

const api = vi.hoisted(() => ({ updateProfile: vi.fn() }));
vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  ...api,
}));

const availability = vi.hoisted(() => ({ value: vi.fn() }));
vi.mock("@/features/auth/useUsernameAvailability", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/auth/useUsernameAvailability")>()),
  useUsernameAvailability: availability.value,
}));

const IDLE = { status: "idle", username: "", message: null };

beforeEach(() => {
  api.updateProfile.mockReset();
  availability.value.mockReset();
  availability.value.mockReturnValue(IDLE);
});

/** The form with the user the session holds, as the settings page gives it. */
function Connected() {
  const { user } = useAuth();
  return user ? <ProfileForm user={user} /> : null;
}

async function setup(me = {}) {
  const view = renderSettings(<Connected />, me);
  await screen.findByLabelText("Display name");
  return view;
}

const field = (name: string) => screen.getByLabelText(name);
const saveBar = () => screen.queryByRole("group", { name: "Unsaved changes" });

describe("ProfileForm", () => {
  it("shows the saved profile and no save bar", async () => {
    await setup();
    expect(field("Display name")).toHaveValue("Ada L.");
    expect(field("Username")).toHaveValue("ada");
    expect(field("Bio")).toHaveValue("Hi");
    expect(saveBar()).toBeNull();
  });

  it("shows the save bar once something differs, and Cancel puts everything back", async () => {
    const user = userEvent.setup();
    await setup();
    await user.type(field("Display name"), "x");
    expect(saveBar()).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(field("Display name")).toHaveValue("Ada L.");
    expect(saveBar()).toBeNull();
  });

  it("sends only what changed, tells you, and reloads the shell's user", async () => {
    const user = userEvent.setup();
    const saved = { ...SETTINGS_ME, display_name: "Ada Lovelace" };
    api.updateProfile.mockResolvedValue(saved);
    const view = await setup();
    view.fetchMe.mockResolvedValue(saved);
    const loads = view.fetchMe.mock.calls.length;

    await user.clear(field("Display name"));
    await user.type(field("Display name"), "  Ada Lovelace  ");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(api.updateProfile).toHaveBeenCalledWith({ display_name: "Ada Lovelace" });
    expect(await screen.findByText(SETTINGS_MESSAGES.profileSaved)).toBeInTheDocument();
    await waitFor(() => expect(view.fetchMe.mock.calls.length).toBeGreaterThan(loads));
    expect(field("Display name")).toHaveValue("Ada Lovelace");
    expect(saveBar()).toBeNull();
  });

  it("sends the username as the server stores it and the bio with its newlines normalised", async () => {
    const user = userEvent.setup();
    api.updateProfile.mockResolvedValue(SETTINGS_ME);
    await setup();
    await user.clear(field("Username"));
    await user.type(field("Username"), "New_Name ");
    fireEvent.change(field("Bio"), { target: { value: "  one\r\ntwo  " } });
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(api.updateProfile).toHaveBeenCalledWith({ username: "new_name", bio: "one\ntwo" });
  });

  it("refuses a bad username, a long name and a long bio without asking the server", async () => {
    const user = userEvent.setup();
    await setup();
    await user.clear(field("Username"));
    await user.type(field("Username"), "no");
    fireEvent.change(field("Display name"), { target: { value: "n".repeat(51) } });
    fireEvent.change(field("Bio"), { target: { value: "b".repeat(MAX_BIO + 1) } });
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(api.updateProfile).not.toHaveBeenCalled();
    expect(screen.getByText(/Usernames are 3–30 characters/)).toBeInTheDocument();
    expect(screen.getByText("Display names are at most 50 characters.")).toBeInTheDocument();
    expect(screen.getByText("Bios are at most 280 characters.")).toBeInTheDocument();
    expect(field("Display name")).toHaveFocus();
  });

  it("counts a bio of exactly 280 characters as fine", async () => {
    const user = userEvent.setup();
    api.updateProfile.mockResolvedValue(SETTINGS_ME);
    await setup();
    fireEvent.change(field("Bio"), { target: { value: "é".repeat(MAX_BIO) } });
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(api.updateProfile).toHaveBeenCalled();
  });

  it("puts the server's field errors on their fields and focuses the first", async () => {
    const user = userEvent.setup();
    api.updateProfile.mockRejectedValue(
      new ApiError({
        status: 400,
        code: "invalid",
        detail: "x",
        fieldErrors: { username: ["That username is taken."], bio: ["Bios are plain text."] },
      }),
    );
    await setup();
    await user.clear(field("Username"));
    await user.type(field("Username"), "taken_one");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("That username is taken.")).toBeInTheDocument();
    expect(screen.getByText("Bios are plain text.")).toBeInTheDocument();
    expect(field("Username")).toHaveFocus();
    expect(field("Username")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText(SETTINGS_MESSAGES.profileSaved)).toBeNull();
  });

  it.each([
    [429, "throttled", SETTINGS_MESSAGES.rateLimited],
    [503, "backend_waking", SETTINGS_MESSAGES.waking],
    [0, "network_error", SETTINGS_MESSAGES.network],
    [500, "http_500", SETTINGS_MESSAGES.generic],
  ])("answers a %s with a banner", async (status, code, message) => {
    const user = userEvent.setup();
    api.updateProfile.mockRejectedValue(new ApiError({ status, code, detail: "x" }));
    await setup();
    await user.type(field("Display name"), "x");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(saveBar()).toBeInTheDocument(); // the edit is kept
  });

  it("blocks saving while the typed username is taken, and says so", async () => {
    const user = userEvent.setup();
    availability.value.mockReturnValue({
      status: "taken",
      username: "ada_2",
      message: "That username is taken.",
    });
    await setup();
    await user.type(field("Username"), "_2");
    expect(screen.getByText("That username is taken.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("shows when a free name was typed", async () => {
    availability.value.mockReturnValue({ status: "available", username: "ada_2", message: null });
    const user = userEvent.setup();
    await setup();
    await user.type(field("Username"), "_2");
    expect(screen.getByText("Available: @ada_2")).toBeInTheDocument();
  });

  it("does not check your own name", async () => {
    await setup();
    expect(availability.value).toHaveBeenLastCalledWith("");
  });

  it("locks the form for an unverified account and says how to unlock it", async () => {
    const user = userEvent.setup();
    await setup({ is_email_verified: false });
    expect(screen.getByText(SETTINGS_MESSAGES.unverified)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /resend the link/ })).toHaveAttribute(
      "href",
      "/verify-email",
    );
    expect(field("Display name")).toBeDisabled();
    expect(field("Bio")).toBeDisabled();
    await user.type(field("Display name"), "x"); // ignored by a disabled input
    expect(saveBar()).toBeNull();
  });

  it("takes the saved profile again when it changes elsewhere", async () => {
    const view = await setup();
    view.fetchMe.mockResolvedValue({
      ...SETTINGS_ME,
      display_name: "From another tab",
      bio: "Other",
    });
    await act(() => view.session.reloadMe());
    expect(field("Display name")).toHaveValue("From another tab");
    expect(field("Bio")).toHaveValue("Other");
  });
});
