import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { makePost } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { AppealModal, type AppealedPost, type AppealResult } from "./AppealModal";
import { APPEAL_MESSAGES } from "./messages";

const api = vi.hoisted(() => ({ appealPost: vi.fn() }));
vi.mock("./appeals-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./appeals-api")>()),
  ...api,
}));

const FALSE_POST: AppealedPost = {
  id: "p1",
  content: "Rain is nice",
  post_type: "fact",
  status: "verified_false",
  removal_reason: "",
};
const REMOVED_POST: AppealedPost = {
  ...FALSE_POST,
  post_type: "opinion",
  status: "removed",
  removal_reason: "Personal attack",
};
const FILED = makePost({ status: "under_review", appeal_status: "open", can_appeal: false });

let onClose: Mock<() => void>;
let onDone: Mock<(result: AppealResult) => void>;

beforeEach(() => {
  api.appealPost.mockReset();
  api.appealPost.mockResolvedValue(FILED);
  onClose = vi.fn<() => void>();
  onDone = vi.fn<(result: AppealResult) => void>();
});

function renderModal(post: AppealedPost = FALSE_POST, open = true) {
  return render(<AppealModal open={open} post={post} onClose={onClose} onDone={onDone} />);
}

const send = () => screen.getByRole("button", { name: "Send request" });
const box = () => screen.getByRole("textbox", { name: "Why should we look again?" });

describe("AppealModal", () => {
  it("shows nothing while it is closed", () => {
    renderModal(FALSE_POST, false);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByText("Send request")).not.toBeInTheDocument();
  });

  it("quotes a FALSE post, says what is appealed and what happens next", () => {
    renderModal();
    expect(screen.getByRole("dialog", { name: "Request another look" })).toBeInTheDocument();
    expect(screen.getByText(/Rain is nice/)).toHaveTextContent("“Rain is nice”");
    expect(screen.getByText("Your post is labelled FALSE.")).toBeInTheDocument();
    expect(screen.queryByText(/Reason given/)).not.toBeInTheDocument();
    expect(screen.getByText("What happens next")).toBeInTheDocument();
    expect(screen.getByText(/shows UNDER REVIEW meanwhile/)).toBeInTheDocument();
    expect(screen.getByText(/once for each post/)).toBeInTheDocument();
    expect(screen.getByText("Optional.")).toBeInTheDocument();
  });

  it("says a moderator removed a removed post, with the reason given", () => {
    renderModal(REMOVED_POST);
    expect(screen.getByText(/A moderator removed your post\./)).toBeInTheDocument();
    expect(screen.getByText("Reason given: Personal attack")).toBeInTheDocument();
    expect(screen.getByText(/The post stays hidden meanwhile/)).toBeInTheDocument();
    expect(screen.queryByText(/UNDER REVIEW/)).not.toBeInTheDocument();
  });

  it("gives no reason line for a removal that had none", () => {
    renderModal({ ...REMOVED_POST, removal_reason: "   " });
    expect(screen.queryByText(/Reason given/)).not.toBeInTheDocument();
  });

  it("quotes a fact in the claim face and an opinion in italics, clamped to three lines", () => {
    const { unmount } = renderModal();
    const fact = screen.getByText(/Rain is nice/);
    expect(fact).toHaveClass("font-claim-headline", "line-clamp-3");
    expect(fact).not.toHaveClass("italic");
    unmount();
    renderModal(REMOVED_POST);
    expect(screen.getByText(/Rain is nice/)).toHaveClass("font-claim-opinion", "italic");
  });

  it("puts the focus in the box when it opens", () => {
    renderModal();
    expect(box()).toHaveFocus();
  });

  it("uses the plain words, never admin jargon", () => {
    renderModal();
    expect(document.body.textContent).not.toMatch(/adjudicat|protocol|verdict appeal/i);
  });

  describe("checks before it sends", () => {
    it("refuses more than 500 characters, counted as code points, and sends nothing", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(box());
      await user.paste("😀".repeat(501));
      await user.click(send());
      expect(await screen.findByText(APPEAL_MESSAGES.reasonTooLong)).toBeInTheDocument();
      expect(box()).toHaveFocus();
      expect(api.appealPost).not.toHaveBeenCalled();
      await user.clear(box());
      await user.click(box());
      await user.paste("😀".repeat(500));
      await user.click(send());
      await waitFor(() => expect(api.appealPost).toHaveBeenCalledTimes(1));
    });

    it("counts as you type, and clears the error when you type", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.type(box(), "abc");
      expect(screen.getByText("3 / 500 characters")).toBeInTheDocument();
    });
  });

  describe("sending", () => {
    it("sends the trimmed reason and hands the post that came back to the parent", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.type(box(), "  The source was updated.  ");
      await user.click(send());
      await waitFor(() => expect(onDone).toHaveBeenCalledWith({ kind: "sent", post: FILED }));
      expect(api.appealPost).toHaveBeenCalledWith("p1", { reason: "The source was updated." });
    });

    it("sends an empty reason when none was typed", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(send());
      await waitFor(() => expect(onDone).toHaveBeenCalled());
      expect(api.appealPost).toHaveBeenCalledWith("p1", { reason: "" });
    });

    it("locks while sending: busy button, locked box, no Cancel, no Escape, no second request", async () => {
      const user = userEvent.setup();
      let finish!: () => void;
      api.appealPost.mockImplementation(
        () => new Promise((resolve) => (finish = () => resolve(FILED))),
      );
      renderModal();
      await user.type(box(), "x");
      await user.click(send());
      await waitFor(() => expect(send()).toHaveAttribute("aria-busy", "true"));
      expect(box().closest("fieldset")).toBeDisabled();
      expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
      await user.click(screen.getByRole("button", { name: "Close" }));
      expect(onClose).not.toHaveBeenCalled();
      await user.click(send());
      expect(api.appealPost).toHaveBeenCalledTimes(1);
      finish();
      await waitFor(() => expect(onDone).toHaveBeenCalledWith({ kind: "sent", post: FILED }));
      expect(send()).not.toHaveAttribute("aria-busy", "true");
    });

    it("sends once when the button is clicked twice in the same tick", async () => {
      renderModal();
      const button = send();
      act(() => {
        button.click();
        button.click();
      });
      await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
      expect(api.appealPost).toHaveBeenCalledTimes(1);
    });

    it("closes from Cancel and from Escape when nothing is being sent", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(screen.getByRole("button", { name: "Cancel" }));
      expect(onClose).toHaveBeenCalledTimes(1);
      await user.keyboard("{Escape}");
      expect(onClose).toHaveBeenCalledTimes(2);
      expect(api.appealPost).not.toHaveBeenCalled();
    });
  });

  describe("when the server says no", () => {
    async function submitWith(error: ApiError) {
      const user = userEvent.setup();
      api.appealPost.mockRejectedValue(error);
      renderModal();
      await user.type(box(), "words kept");
      await user.click(send());
      return user;
    }

    it.each([
      ["409 already_appealed", { status: 409, code: "already_appealed" }, "already"],
      ["409 not_appealable", { status: 409, code: "not_appealable" }, "not_appealable"],
      ["404", { status: 404, code: "not_found" }, "gone"],
    ] as const)("treats %s as the end of the flow: the parent says so", async (_, init, kind) => {
      await submitWith(new ApiError({ ...init, detail: "" }));
      await waitFor(() => expect(onDone).toHaveBeenCalledWith({ kind }));
    });

    it("asks to verify the email, in a warning, and keeps the words", async () => {
      await submitWith(new ApiError({ status: 403, code: "email_unverified", detail: "" }));
      const notice = await screen.findByText(APPEAL_MESSAGES.verifyInModal);
      const card = notice.closest(".rounded-lg");
      expect(card).toHaveClass("border-verdict-review/30");
      expect(card).not.toHaveAttribute("role", "alert");
      expect(onDone).not.toHaveBeenCalled();
      expect(box()).toHaveValue("words kept");
    });

    it("says when it is too many, with the wait", async () => {
      await submitWith(
        new ApiError({ status: 429, code: "throttled", detail: "", retryAfter: 4 * 3600 }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "You've asked for another look too often today. Try again in about 4 hours.",
      );
      expect(onDone).not.toHaveBeenCalled();
    });

    it("puts a server field error on the box and focuses it once the form unlocks", async () => {
      await submitWith(
        new ApiError({
          status: 400,
          code: "validation_error",
          detail: "",
          fieldErrors: { reason: ["Keep it to 500 characters."] },
        }),
      );
      expect(await screen.findByText("Keep it to 500 characters.")).toBeInTheDocument();
      await waitFor(() => expect(box()).toHaveFocus());
    });

    it.each([
      [
        "a signed-out session",
        { status: 401, code: "not_authenticated" },
        APPEAL_MESSAGES.signedOut,
      ],
      ["no connection", { status: 0, code: "network_error" }, APPEAL_MESSAGES.network],
      ["a sleeping server", { status: 503, code: "backend_waking" }, APPEAL_MESSAGES.waking],
      ["anything else", { status: 500, code: "server_error" }, APPEAL_MESSAGES.failed],
      ["someone else's post", { status: 403, code: "not_author" }, APPEAL_MESSAGES.notAuthor],
    ])("shows a message for %s and keeps the words", async (_, init, message) => {
      await submitWith(new ApiError({ ...init, detail: "" }));
      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(onDone).not.toHaveBeenCalled();
      expect(box()).toHaveValue("words kept");
    });

    it("can be tried again after a failure", async () => {
      const user = await submitWith(new ApiError({ status: 0, code: "network_error", detail: "" }));
      expect(await screen.findByText(APPEAL_MESSAGES.network)).toBeInTheDocument();
      api.appealPost.mockResolvedValue(FILED);
      await user.click(send());
      await waitFor(() => expect(onDone).toHaveBeenCalledWith({ kind: "sent", post: FILED }));
      expect(screen.queryByText(APPEAL_MESSAGES.network)).not.toBeInTheDocument();
    });
  });
});
