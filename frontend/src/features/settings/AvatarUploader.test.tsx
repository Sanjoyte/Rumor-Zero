import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { AvatarUploader } from "./AvatarUploader";
import { PHOTO_MESSAGES } from "./messages";
import { PhotoPrepError } from "./photo-prep";
import type { UploadOptions } from "./settings-api";
import { renderSettings, SETTINGS_ME } from "./test-helpers";

const api = vi.hoisted(() => ({ uploadAvatar: vi.fn(), removeAvatar: vi.fn() }));
vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  ...api,
}));

const PHOTO_URL = "/api/v1/avatars/u-1/0123456789abcdef-256.webp";
const JPEG = new Blob(["prepared-jpeg"], { type: "image/jpeg" });
const prepare = vi.fn();

beforeEach(() => {
  api.uploadAvatar.mockReset();
  api.removeAvatar.mockReset();
  prepare.mockReset();
  prepare.mockResolvedValue({ blob: JPEG, side: 500 });
  let counter = 0;
  URL.createObjectURL = vi.fn(() => `blob:preview-${++counter}`);
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => vi.restoreAllMocks());

/** The uploader with the user the session holds, as the settings page gives it. */
function Connected() {
  const { user } = useAuth();
  return user ? <AvatarUploader user={user} prepare={prepare} /> : null;
}

async function setup(me: Partial<Me> = {}) {
  const view = renderSettings(<Connected />, me);
  await screen.findByRole("heading", { name: "Profile photo" });
  return view;
}

const input = () => screen.getByTestId("photo-input") as HTMLInputElement;
const choose = (type = "image/jpeg") =>
  fireEvent.change(input(), {
    target: { files: [new File(["original"], "holiday.jpg", { type })] },
  });
const preview = () => screen.queryByRole("img", { name: "Preview of your new photo" });

/** An upload that stays open until the test finishes it, with its progress callback. */
function openUpload() {
  const upload: {
    options?: UploadOptions;
    finish?: (me: Me) => void;
    fail?: (e: unknown) => void;
  } = {};
  api.uploadAvatar.mockImplementation(
    (_blob: Blob, options: UploadOptions) =>
      new Promise<Me>((resolve, reject) => {
        upload.options = options;
        upload.finish = resolve;
        upload.fail = reject;
        options.signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        );
      }),
  );
  return upload;
}

describe("AvatarUploader: the card", () => {
  it("explains the photo and offers Upload when there is none", async () => {
    await setup();
    expect(screen.getByText(/JPEG, PNG or WebP, at least 128 × 128 pixels/)).toBeInTheDocument();
    expect(screen.getByText(/remove location and camera data/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload photo" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Remove photo" })).toBeNull();
    // Initials, not a picture.
    expect(screen.getByRole("img", { name: "Ada L." }).tagName).toBe("SPAN");
  });

  it("shows the current photo with Change and Remove", async () => {
    await setup({ avatar_url: PHOTO_URL });
    const image = screen.getByRole("img", { name: "Ada L." });
    expect(image.tagName).toBe("IMG");
    expect(image).toHaveAttribute("src", PHOTO_URL);
    expect(screen.getByRole("button", { name: "Change photo" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Remove photo" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Upload photo" })).toBeNull();
  });

  it("opens the file picker for JPEG, PNG and WebP only", async () => {
    const user = userEvent.setup();
    await setup();
    const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    await user.click(screen.getByRole("button", { name: "Upload photo" }));
    expect(click).toHaveBeenCalledTimes(1);
    expect(input()).toHaveAttribute("accept", "image/jpeg,image/png,image/webp");
    expect(input()).toHaveAttribute("type", "file");
  });
});

describe("AvatarUploader: choosing and previewing", () => {
  it("prepares the file, then shows the square preview with Use this photo and Cancel", async () => {
    let finishPrepare!: (value: unknown) => void;
    prepare.mockReturnValue(new Promise((resolve) => (finishPrepare = resolve)));
    await setup();
    choose();

    expect(await screen.findByText("Preparing your photo…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload photo" })).toBeDisabled();
    expect(prepare).toHaveBeenCalledTimes(1);
    expect(prepare.mock.calls[0][0].name).toBe("holiday.jpg");

    await act(async () => finishPrepare({ blob: JPEG, side: 500 }));
    const image = preview();
    expect(image).toHaveAttribute("src", "blob:preview-1");
    expect(image).toHaveAttribute("width", "96");
    expect(image).toHaveAttribute("height", "96");
    expect(image).toHaveClass("rounded-lg");
    expect(screen.getByRole("button", { name: "Use this photo" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload photo" })).toBeNull();
    expect(api.uploadAvatar).not.toHaveBeenCalled(); // nothing is sent until you say so
  });

  it("lets the same file be chosen again afterwards", async () => {
    const user = userEvent.setup();
    await setup();
    await user.upload(input(), new File(["original"], "holiday.jpg", { type: "image/jpeg" }));
    await screen.findByRole("button", { name: "Use this photo" });
    // A file input that still holds its file fires no `change` for the same file again.
    expect(input().files).toHaveLength(0);
    expect(input().value).toBe("");
  });

  it("Cancel drops the preview and the object URL and sends nothing", async () => {
    const user = userEvent.setup();
    await setup({ avatar_url: PHOTO_URL });
    choose();
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(preview()).toBeNull();
    expect(screen.getByRole("button", { name: "Change photo" })).toBeEnabled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview-1");
    expect(api.uploadAvatar).not.toHaveBeenCalled();
    expect(screen.getByRole("img", { name: "Ada L." })).toHaveAttribute("src", PHOTO_URL);
  });

  it("revokes the object URL when the card goes away", async () => {
    const view = await setup();
    choose();
    await screen.findByRole("button", { name: "Use this photo" });
    view.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview-1");
  });

  it.each([
    ["type", PHOTO_MESSAGES.type],
    ["too_big", PHOTO_MESSAGES.tooBig],
    ["unreadable", PHOTO_MESSAGES.unreadable],
    ["too_small", PHOTO_MESSAGES.tooSmall],
  ] as const)("a file that is %s says so and keeps the old photo", async (problem, text) => {
    prepare.mockRejectedValue(new PhotoPrepError(problem));
    await setup({ avatar_url: PHOTO_URL });
    choose();

    expect(await screen.findByRole("alert")).toHaveTextContent(text);
    expect(preview()).toBeNull();
    expect(screen.getByRole("img", { name: "Ada L." })).toHaveAttribute("src", PHOTO_URL);
    expect(screen.getByRole("button", { name: "Change photo" })).toBeEnabled();
    expect(api.uploadAvatar).not.toHaveBeenCalled();
  });

  it("an unexpected failure while preparing is the unreadable message, not a crash", async () => {
    prepare.mockRejectedValue(new Error("boom"));
    await setup();
    choose();
    expect(await screen.findByRole("alert")).toHaveTextContent(PHOTO_MESSAGES.unreadable);
  });

  it("the error goes away when you choose another file", async () => {
    prepare.mockRejectedValueOnce(new PhotoPrepError("type"));
    await setup();
    choose();
    await screen.findByRole("alert");
    choose();
    await screen.findByRole("button", { name: "Use this photo" });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("AvatarUploader: uploading", () => {
  it("sends the prepared photo, shows the real percentage, then Saving", async () => {
    const user = userEvent.setup();
    const upload = openUpload();
    await setup();
    choose();
    await user.click(await screen.findByRole("button", { name: "Use this photo" }));

    expect(api.uploadAvatar).toHaveBeenCalledTimes(1);
    expect(api.uploadAvatar.mock.calls[0][0]).toBe(JPEG); // the re-encoded blob, not the file
    expect(await screen.findByText("Uploading… 0%")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Use this photo" })).toBeNull();

    act(() => upload.options?.onProgress?.(0.42));
    expect(screen.getByText("Uploading… 42%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Photo upload progress" })).toHaveAttribute(
      "aria-valuenow",
      "42",
    );

    act(() => upload.options?.onProgress?.(1));
    expect(screen.getByText("Saving…")).toBeInTheDocument();
  });

  it("on success: a toast, the shell's user reloaded, and the card back to idle", async () => {
    const user = userEvent.setup();
    const upload = openUpload();
    const view = await setup();
    const saved = { ...SETTINGS_ME, avatar_url: PHOTO_URL };
    view.fetchMe.mockResolvedValue(saved);
    const loads = view.fetchMe.mock.calls.length;
    choose();
    await user.click(await screen.findByRole("button", { name: "Use this photo" }));
    await act(async () => upload.finish?.(saved));

    expect(await screen.findByText(PHOTO_MESSAGES.saved)).toBeInTheDocument();
    await waitFor(() => expect(view.fetchMe.mock.calls.length).toBeGreaterThan(loads));
    expect(preview()).toBeNull();
    expect(await screen.findByRole("button", { name: "Change photo" })).toBeEnabled();
    expect(screen.getByRole("img", { name: "Ada L." })).toHaveAttribute("src", PHOTO_URL);
  });

  it("a refusal shows the server's reason and keeps the preview to try again or cancel", async () => {
    const user = userEvent.setup();
    api.uploadAvatar.mockRejectedValue(
      new ApiError({ status: 400, code: "photo_unsupported", detail: "Nope." }),
    );
    await setup();
    choose();
    await user.click(await screen.findByRole("button", { name: "Use this photo" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(PHOTO_MESSAGES.serverUnsupported);
    expect(preview()).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use this photo" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("the five a day limit says when to try again", async () => {
    const user = userEvent.setup();
    api.uploadAvatar.mockRejectedValue(
      new ApiError({ status: 429, code: "throttled", detail: "Throttled.", retryAfter: 7200 }),
    );
    await setup();
    choose();
    await user.click(await screen.findByRole("button", { name: "Use this photo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You've changed your photo a few times today. Try again in about 2 hours.",
    );
  });

  it("Cancel during the upload aborts it, says so, and asks the server what it has", async () => {
    const user = userEvent.setup();
    const upload = openUpload();
    const view = await setup();
    choose();
    await user.click(await screen.findByRole("button", { name: "Use this photo" }));
    await screen.findByText("Uploading… 0%");
    const loads = view.fetchMe.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(upload.options?.signal?.aborted).toBe(true);
    expect(await screen.findByText(PHOTO_MESSAGES.cancelled)).toBeInTheDocument();
    await waitFor(() => expect(view.fetchMe.mock.calls.length).toBeGreaterThan(loads));
    expect(preview()).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Upload photo" })).toBeEnabled();
  });

  it("leaving the page mid-upload ends the request", async () => {
    const user = userEvent.setup();
    const upload = openUpload();
    const view = await setup();
    choose();
    await user.click(await screen.findByRole("button", { name: "Use this photo" }));
    await screen.findByText("Uploading… 0%");
    view.unmount();
    expect(upload.options?.signal?.aborted).toBe(true);
  });
});

describe("AvatarUploader: Remove photo", () => {
  it("takes the photo down without asking, tells you and reloads the user", async () => {
    const user = userEvent.setup();
    api.removeAvatar.mockResolvedValue(undefined);
    const view = await setup({ avatar_url: PHOTO_URL });
    view.fetchMe.mockResolvedValue({ ...SETTINGS_ME, avatar_url: null });
    const loads = view.fetchMe.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Remove photo" }));

    expect(api.removeAvatar).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(PHOTO_MESSAGES.removed)).toBeInTheDocument();
    await waitFor(() => expect(view.fetchMe.mock.calls.length).toBeGreaterThan(loads));
    // No confirmation dialog was involved.
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(await screen.findByRole("button", { name: "Upload photo" })).toBeEnabled();
    expect(screen.getByRole("img", { name: "Ada L." }).tagName).toBe("SPAN");
  });

  it("a failure keeps the photo and says why", async () => {
    const user = userEvent.setup();
    api.removeAvatar.mockRejectedValue(
      new ApiError({ status: 503, code: "backend_waking", detail: "Waking." }),
    );
    await setup({ avatar_url: PHOTO_URL });
    await user.click(screen.getByRole("button", { name: "Remove photo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The server is waking up");
    expect(screen.getByRole("img", { name: "Ada L." })).toHaveAttribute("src", PHOTO_URL);
    expect(screen.getByRole("button", { name: "Remove photo" })).toBeEnabled();
  });

  it("locks Upload while the removal is in flight", async () => {
    const user = userEvent.setup();
    let finish!: () => void;
    api.removeAvatar.mockReturnValue(new Promise<void>((resolve) => (finish = resolve)));
    await setup({ avatar_url: PHOTO_URL });
    await user.click(screen.getByRole("button", { name: "Remove photo" }));

    expect(screen.getByRole("button", { name: "Change photo" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove photo" })).toBeDisabled();
    await act(async () => finish());
  });
});

describe("AvatarUploader: when you can't upload", () => {
  it("blocked: says why and offers no Upload, but Remove still works", async () => {
    await setup({ avatar_url: PHOTO_URL, avatar_uploads_blocked: true });
    expect(screen.getByText(PHOTO_MESSAGES.blocked)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Upload photo|Change photo/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Remove photo" })).toBeEnabled();
  });

  it("blocked with no photo has no buttons at all", async () => {
    await setup({ avatar_uploads_blocked: true });
    expect(screen.getByText(PHOTO_MESSAGES.blocked)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("unverified: Upload is disabled and the hint says what to do", async () => {
    await setup({ is_email_verified: false });
    const upload = screen.getByRole("button", { name: "Upload photo" });
    expect(upload).toBeDisabled();
    const hint = screen.getByText(PHOTO_MESSAGES.unverified);
    expect(upload).toHaveAttribute("aria-describedby", hint.id);
  });

  it("unverified can still take a photo down", async () => {
    await setup({ is_email_verified: false, avatar_url: PHOTO_URL });
    expect(screen.getByRole("button", { name: "Change photo" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove photo" })).toBeEnabled();
  });

  it("a verified, unblocked account sees neither notice", async () => {
    await setup();
    expect(screen.queryByText(PHOTO_MESSAGES.blocked)).toBeNull();
    expect(screen.queryByText(PHOTO_MESSAGES.unverified)).toBeNull();
  });
});
