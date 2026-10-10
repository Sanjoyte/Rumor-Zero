import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { ApiError } from "@/lib/api/client";
import { REPORT_MESSAGES } from "./messages";
import { REPORT_REASONS } from "./reasons";
import { ReportModal, type ReportedPost, type ReportOutcome } from "./ReportModal";

const api = vi.hoisted(() => ({ reportPost: vi.fn() }));
vi.mock("./reports-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./reports-api")>()),
  ...api,
}));

const POST: ReportedPost = {
  id: "p1",
  content: "Rain is nice",
  post_type: "opinion",
  author: { id: "u-9", username: "bo", display_name: "Bo" },
};

let onClose: Mock<() => void>;
let onDone: Mock<(outcome: ReportOutcome) => void>;

beforeEach(() => {
  api.reportPost.mockReset();
  api.reportPost.mockResolvedValue({ reported: true });
  onClose = vi.fn<() => void>();
  onDone = vi.fn<(outcome: ReportOutcome) => void>();
});

function renderModal(post: ReportedPost = POST, open = true) {
  return render(<ReportModal open={open} post={post} onClose={onClose} onDone={onDone} />);
}

const submitButton = () => screen.getByRole("button", { name: "Submit report" });
const radio = (name: string) => screen.getByRole("radio", { name: new RegExp(name) });

describe("ReportModal", () => {
  it("shows nothing while it is closed", () => {
    renderModal(POST, false);
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByText("Submit report")).not.toBeInTheDocument();
  });

  it("quotes the post, offers the five reasons with none chosen, and explains what happens next", () => {
    renderModal();
    expect(screen.getByRole("dialog", { name: "Report this post" })).toBeInTheDocument();
    expect(screen.getByText("@bo").parentElement).toHaveTextContent("Bo @bo");
    expect(screen.getByText(/Rain is nice/)).toHaveTextContent("“Rain is nice”");
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(5);
    for (const option of REPORT_REASONS) {
      expect(radio(option.label)).not.toBeChecked();
      expect(screen.getByText(option.description)).toBeInTheDocument();
    }
    expect(screen.getByText("What happens next")).toBeInTheDocument();
    expect(screen.getByText(/stays visible/)).toBeInTheDocument();
    expect(
      screen.getByText("Reports are private. The author is never told who reported."),
    ).toBeInTheDocument();
  });

  it("uses the plain labels, never the old jargon", () => {
    renderModal();
    expect(document.body.textContent).not.toMatch(/evidentiary|sybil|governance|protocol/i);
    expect(
      screen
        .getAllByRole("radio")
        .map((r) => r.closest("label")?.querySelector("span span")?.textContent),
    ).toEqual([
      "False or inaccurate",
      "Missing context or misleading",
      "Harassment or defamation",
      "Spam or fake accounts",
      "Something else",
    ]);
  });

  it("puts the focus on the first reason when it opens", () => {
    renderModal();
    expect(radio("False or inaccurate")).toHaveFocus();
  });

  it("quotes a fact in the claim face and an opinion in italics, clamped to three lines", () => {
    const { unmount } = renderModal({ ...POST, post_type: "fact" });
    const fact = screen.getByText(/Rain is nice/);
    expect(fact).toHaveClass("font-claim-headline", "line-clamp-3");
    expect(fact).not.toHaveClass("italic");
    unmount();
    renderModal();
    expect(screen.getByText(/Rain is nice/)).toHaveClass("font-claim-opinion", "italic");
  });

  it("shows only @username when the display name is blank", () => {
    renderModal({ ...POST, author: { id: "u-9", username: "bo", display_name: "" } });
    expect(screen.getByText("@bo").parentElement).toHaveTextContent(/^@bo$/);
  });

  describe("checks before it sends", () => {
    it("asks for a reason, focuses the first one and sends nothing", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(screen.getByRole("textbox", { name: "Details" }));
      await user.click(submitButton());
      expect(screen.getByRole("alert")).toHaveTextContent("Choose a reason.");
      expect(radio("False or inaccurate")).toHaveFocus();
      expect(api.reportPost).not.toHaveBeenCalled();
    });

    it("clears the reason error as soon as one is chosen", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(submitButton());
      expect(screen.getByRole("alert")).toBeInTheDocument();
      await user.click(radio("Spam"));
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("needs details for 'Something else', and says so up front", async () => {
      const user = userEvent.setup();
      renderModal();
      expect(screen.getByText("Optional.")).toBeInTheDocument();
      await user.click(radio("Something else"));
      expect(screen.getByText("Required for “Something else”.")).toBeInTheDocument();
      await user.click(submitButton());
      expect(await screen.findByText("Tell us what's wrong.")).toBeInTheDocument();
      expect(screen.getByRole("textbox", { name: "Details" })).toHaveFocus();
      expect(screen.getByRole("textbox", { name: "Details" })).toHaveAttribute(
        "aria-invalid",
        "true",
      );
      expect(api.reportPost).not.toHaveBeenCalled();
    });

    it("treats spaces as nothing for 'Something else'", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(radio("Something else"));
      await user.type(screen.getByRole("textbox", { name: "Details" }), "    ");
      await user.click(submitButton());
      expect(await screen.findByText("Tell us what's wrong.")).toBeInTheDocument();
    });

    it("clears the details error when you type", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(radio("Something else"));
      await user.click(submitButton());
      expect(await screen.findByText("Tell us what's wrong.")).toBeInTheDocument();
      await user.type(screen.getByRole("textbox", { name: "Details" }), "x");
      expect(screen.queryByText("Tell us what's wrong.")).not.toBeInTheDocument();
    });

    it("refuses details over 500 characters, counted as code points", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(radio("Spam"));
      const box = screen.getByRole("textbox", { name: "Details" });
      await user.click(box);
      await user.paste("😀".repeat(501));
      await user.click(submitButton());
      expect(await screen.findByText("Keep it to 500 characters.")).toBeInTheDocument();
      expect(api.reportPost).not.toHaveBeenCalled();
      await user.clear(box);
      await user.click(box);
      await user.paste("😀".repeat(500));
      await user.click(submitButton());
      await waitFor(() => expect(api.reportPost).toHaveBeenCalledTimes(1));
    });

    it("counts the details as you type", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.type(screen.getByRole("textbox", { name: "Details" }), "abc");
      expect(screen.getByText("3 / 500 characters")).toBeInTheDocument();
    });
  });

  describe("sending", () => {
    it("sends the reason and the trimmed details, then says it is done", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(radio("Harassment"));
      await user.type(screen.getByRole("textbox", { name: "Details" }), "  It targets me.  ");
      await user.click(submitButton());
      await waitFor(() => expect(onDone).toHaveBeenCalledWith("sent"));
      expect(api.reportPost).toHaveBeenCalledWith("p1", {
        reason: "harassment",
        details: "It targets me.",
      });
    });

    it("sends empty details when none were typed for the other four reasons", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(radio("False or inaccurate"));
      await user.click(submitButton());
      await waitFor(() => expect(onDone).toHaveBeenCalledWith("sent"));
      expect(api.reportPost).toHaveBeenCalledWith("p1", { reason: "inaccurate", details: "" });
    });

    it("locks while sending: busy button, locked fields, no Cancel, no Escape, no second request", async () => {
      const user = userEvent.setup();
      let finish!: () => void;
      api.reportPost.mockImplementation(
        () => new Promise((resolve) => (finish = () => resolve({ reported: true }))),
      );
      renderModal();
      await user.click(radio("Spam"));
      await user.click(submitButton());
      await waitFor(() => expect(submitButton()).toHaveAttribute("aria-busy", "true"));
      expect(radio("Spam").closest("fieldset")).toBeDisabled();
      expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
      // Escape and the close button both ask the dialog to close: neither works while sending.
      // (`user.keyboard` would send the key to `body`, since the busy button lost the focus.)
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
      await user.click(screen.getByRole("button", { name: "Close" }));
      expect(onClose).not.toHaveBeenCalled();
      await user.click(submitButton());
      expect(api.reportPost).toHaveBeenCalledTimes(1);
      finish();
      await waitFor(() => expect(onDone).toHaveBeenCalledWith("sent"));
      expect(submitButton()).not.toHaveAttribute("aria-busy", "true");
    });

    it("closes from Cancel and from Escape when nothing is being sent", async () => {
      const user = userEvent.setup();
      renderModal();
      await user.click(screen.getByRole("button", { name: "Cancel" }));
      expect(onClose).toHaveBeenCalledTimes(1);
      await user.keyboard("{Escape}");
      expect(onClose).toHaveBeenCalledTimes(2);
      expect(api.reportPost).not.toHaveBeenCalled();
    });
  });

  describe("when the server says no", () => {
    async function submitWith(error: ApiError) {
      const user = userEvent.setup();
      api.reportPost.mockRejectedValue(error);
      renderModal();
      await user.click(radio("Spam"));
      await user.type(screen.getByRole("textbox", { name: "Details" }), "details kept");
      await user.click(submitButton());
      return user;
    }

    it("treats 409 already_reported as done: the parent says so", async () => {
      await submitWith(new ApiError({ status: 409, code: "already_reported", detail: "" }));
      await waitFor(() => expect(onDone).toHaveBeenCalledWith("already"));
    });

    it("treats a 404 as the post being gone", async () => {
      await submitWith(new ApiError({ status: 404, code: "not_found", detail: "" }));
      await waitFor(() => expect(onDone).toHaveBeenCalledWith("gone"));
    });

    it("asks to verify the email, in a warning, and keeps the choices", async () => {
      await submitWith(new ApiError({ status: 403, code: "email_unverified", detail: "" }));
      const notice = await screen.findByText(REPORT_MESSAGES.verifyInModal);
      // A warning, not an error: it is a prompt, and it isn't announced as an alert.
      const box = notice.closest(".rounded-lg");
      expect(box).toHaveClass("border-verdict-review/30");
      expect(box).not.toHaveAttribute("role", "alert");
      expect(onDone).not.toHaveBeenCalled();
      expect(radio("Spam")).toBeChecked();
      expect(screen.getByRole("textbox", { name: "Details" })).toHaveValue("details kept");
    });

    it("says when it is too fast, with the wait", async () => {
      await submitWith(
        new ApiError({ status: 429, code: "throttled", detail: "", retryAfter: 300 }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "You're reporting too fast. Try again in about 5 minutes.",
      );
      expect(onDone).not.toHaveBeenCalled();
    });

    it("puts a server field error on its field and focuses it", async () => {
      await submitWith(
        new ApiError({
          status: 400,
          code: "validation_error",
          detail: "",
          fieldErrors: { details: ["Keep it to 500 characters."] },
        }),
      );
      expect(await screen.findByText("Keep it to 500 characters.")).toBeInTheDocument();
      expect(screen.getByRole("textbox", { name: "Details" })).toHaveFocus();
    });

    it("puts a server reason error under the reasons", async () => {
      await submitWith(
        new ApiError({
          status: 400,
          code: "validation_error",
          detail: "",
          fieldErrors: { reason: ["Choose a reason."] },
        }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent("Choose a reason.");
      expect(radio("False or inaccurate")).toHaveFocus();
    });

    it.each([
      [
        "a signed-out session",
        { status: 401, code: "not_authenticated" },
        REPORT_MESSAGES.signedOut,
      ],
      ["no connection", { status: 0, code: "network_error" }, REPORT_MESSAGES.network],
      ["a sleeping server", { status: 503, code: "backend_waking" }, REPORT_MESSAGES.waking],
      ["anything else", { status: 500, code: "server_error" }, REPORT_MESSAGES.failed],
      ["your own post", { status: 403, code: "cannot_report_own" }, REPORT_MESSAGES.own],
    ])("shows a message for %s and keeps the choices", async (_, init, message) => {
      await submitWith(new ApiError({ ...init, detail: "" }));
      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(onDone).not.toHaveBeenCalled();
      expect(radio("Spam")).toBeChecked();
    });

    it("can be tried again after a failure", async () => {
      const user = await submitWith(new ApiError({ status: 0, code: "network_error", detail: "" }));
      expect(await screen.findByText(REPORT_MESSAGES.network)).toBeInTheDocument();
      api.reportPost.mockResolvedValue({ reported: true });
      await user.click(submitButton());
      await waitFor(() => expect(onDone).toHaveBeenCalledWith("sent"));
      expect(screen.queryByText(REPORT_MESSAGES.network)).not.toBeInTheDocument();
    });
  });
});
