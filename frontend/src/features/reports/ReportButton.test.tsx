import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BO, renderWithSessionAndToast, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { REPORT_MESSAGES } from "./messages";
import { ReportButton, type ReportButtonProps } from "./ReportButton";

const api = vi.hoisted(() => ({ reportPost: vi.fn() }));
vi.mock("./reports-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./reports-api")>()),
  ...api,
}));

// By someone else than the test session's user (`u-1`).
const POST: ReportButtonProps["post"] = {
  id: "p1",
  content: "Rain is nice",
  post_type: "opinion",
  author: BO,
  is_mine: false,
  reported_by_me: false,
};

beforeEach(() => {
  api.reportPost.mockReset();
  api.reportPost.mockResolvedValue({ reported: true });
});

function renderButton(kind: SessionKind = "verified", props: Partial<ReportButtonProps> = {}) {
  return renderWithSessionAndToast(<ReportButton post={POST} {...props} />, kind);
}

async function report(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Report" }));
  await user.click(screen.getByRole("radio", { name: /Spam/ }));
  await user.click(screen.getByRole("button", { name: "Submit report" }));
}

describe("ReportButton", () => {
  it("is a log-in link for a visitor, back to the post afterwards", async () => {
    renderButton("anonymous");
    const link = await screen.findByRole("link", { name: "Report" });
    expect(link).toHaveAttribute("href", "/login?next=%2Fp%2Fp1");
    expect(link).toHaveAttribute("title", "Log in to report");
    expect(document.querySelector("dialog")).toBeNull();
  });

  it("shows the flag but nothing to click while the session is loading", () => {
    renderButton("loading");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Report")).toBeInTheDocument();
  });

  it("renders nothing on your own post, whichever way it is told", async () => {
    const nothing = () => {
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
      expect(screen.queryByText("Report")).not.toBeInTheDocument();
    };
    const first = renderButton("verified", { post: { ...POST, is_mine: true } });
    await waitFor(nothing); // after the session has settled
    first.unmount();
    // The server says it is yours, even before the session has finished loading.
    const early = renderButton("loading", { post: { ...POST, is_mine: true } });
    nothing();
    early.unmount();
    // The session's user is `u-1`: the same author id means it is theirs, even when the page
    // hasn't been told `is_mine` yet (the server-rendered, anonymous view).
    renderButton("verified", { post: { ...POST, author: { ...BO, id: "u-1" } } });
    await waitFor(nothing);
  });

  it("is a button named Report, with a title, that builds no dialog until it is clicked", async () => {
    renderButton();
    const button = await screen.findByRole("button", { name: "Report" });
    expect(button).toHaveAttribute("title", "Report this post");
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(document.querySelector("dialog")).toBeNull();
  });

  it("opens the report dialog on a click", async () => {
    const user = userEvent.setup();
    renderButton();
    await user.click(await screen.findByRole("button", { name: "Report" }));
    expect(screen.getByRole("dialog", { name: "Report this post" })).toBeInTheDocument();
    expect(api.reportPost).not.toHaveBeenCalled();
  });

  it("is aria-disabled for an unverified email, explains itself and opens nothing", async () => {
    const user = userEvent.setup();
    renderButton("unverified");
    const button = await screen.findByRole("button", { name: "Report" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription(REPORT_MESSAGES.verifyHint);
    await user.click(button);
    expect(await screen.findByText(REPORT_MESSAGES.verifyToast)).toBeInTheDocument();
    expect(document.querySelector("dialog")).toBeNull();
    expect(api.reportPost).not.toHaveBeenCalled();
  });

  describe("after a report", () => {
    it("closes the dialog, thanks the person and turns into 'You reported this'", async () => {
      const user = userEvent.setup();
      renderButton();
      await report(user);
      expect(await screen.findByText(REPORT_MESSAGES.sent)).toBeInTheDocument();
      expect(api.reportPost).toHaveBeenCalledWith("p1", { reason: "spam", details: "" });
      const button = screen.getByRole("button", { name: "You reported this" });
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAttribute("title", "You reported this");
      expect(button).not.toHaveClass("opacity-60");
      expect(screen.queryByRole("dialog", { name: "Report this post" })).not.toBeInTheDocument();
    });

    it("stays the same button, and focus comes back to it", async () => {
      const user = userEvent.setup();
      renderButton();
      const before = await screen.findByRole("button", { name: "Report" });
      await report(user);
      await screen.findByText(REPORT_MESSAGES.sent);
      const after = screen.getByRole("button", { name: "You reported this" });
      expect(after).toBe(before);
      await waitFor(() => expect(after).toHaveFocus());
    });

    it("can't report twice: a click only says so", async () => {
      const user = userEvent.setup();
      renderButton();
      await report(user);
      await screen.findByText(REPORT_MESSAGES.sent);
      await user.click(screen.getByRole("button", { name: "You reported this" }));
      expect(await screen.findByText(REPORT_MESSAGES.already)).toBeInTheDocument();
      expect(api.reportPost).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole("dialog", { name: "Report this post" })).not.toBeInTheDocument();
    });

    it("says it was reported already when the server says so, and follows it", async () => {
      const user = userEvent.setup();
      api.reportPost.mockRejectedValue(
        new ApiError({ status: 409, code: "already_reported", detail: "" }),
      );
      renderButton();
      await report(user);
      expect(await screen.findByText(REPORT_MESSAGES.already)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "You reported this" })).toBeInTheDocument();
    });

    it("says the post is gone and does not mark it reported", async () => {
      const user = userEvent.setup();
      api.reportPost.mockRejectedValue(
        new ApiError({ status: 404, code: "not_found", detail: "" }),
      );
      renderButton();
      await report(user);
      expect(await screen.findByText(REPORT_MESSAGES.gone)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Report" })).toBeInTheDocument();
    });

    it("keeps the dialog open, with the choices, after a failure", async () => {
      const user = userEvent.setup();
      api.reportPost.mockRejectedValue(
        new ApiError({ status: 0, code: "network_error", detail: "" }),
      );
      renderButton();
      await report(user);
      expect(await screen.findByText(REPORT_MESSAGES.network)).toBeInTheDocument();
      expect(screen.getByRole("dialog", { name: "Report this post" })).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: /Spam/ })).toBeChecked();
      expect(screen.queryByText(REPORT_MESSAGES.sent)).not.toBeInTheDocument();
    });

    it("keeps the choices when the dialog is closed and opened again", async () => {
      const user = userEvent.setup();
      renderButton();
      await user.click(await screen.findByRole("button", { name: "Report" }));
      await user.click(screen.getByRole("radio", { name: /Spam/ }));
      await user.click(screen.getByRole("button", { name: "Cancel" }));
      expect(screen.queryByRole("dialog", { name: "Report this post" })).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Report" }));
      expect(screen.getByRole("radio", { name: /Spam/ })).toBeChecked();
    });
  });

  it("starts as 'You reported this' when the server says so, with no dialog to build", async () => {
    const user = userEvent.setup();
    renderButton("verified", { post: { ...POST, reported_by_me: true } });
    const button = await screen.findByRole("button", { name: "You reported this" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    await user.click(button);
    expect(await screen.findByText(REPORT_MESSAGES.already)).toBeInTheDocument();
    expect(document.querySelector("dialog")).toBeNull();
  });

  it("draws the reported flag filled and in secondary, the unreported one outline", async () => {
    const { unmount } = renderButton("verified", { post: { ...POST, reported_by_me: true } });
    const on = (await screen.findByText("flag")) as HTMLElement;
    expect(on).toHaveClass("text-secondary");
    expect(on.className).toContain("FILL");
    unmount();
    renderButton("verified");
    const off = (await screen.findByText("flag")) as HTMLElement;
    expect(off).not.toHaveClass("text-secondary");
    expect(off.className).not.toContain("FILL");
  });

  it("is never blocked for an unverified email once the report exists", async () => {
    renderButton("unverified", { post: { ...POST, reported_by_me: true } });
    const button = await screen.findByRole("button", { name: "You reported this" });
    expect(button).not.toHaveAttribute("aria-describedby");
  });

  it("follows the server when a refetch brings a new answer", async () => {
    const view = renderButton();
    await screen.findByRole("button", { name: "Report" });
    act(() => view.rerender(<ReportButton post={{ ...POST, reported_by_me: true }} />));
    expect(await screen.findByRole("button", { name: "You reported this" })).toBeInTheDocument();
    act(() => view.rerender(<ReportButton post={{ ...POST, reported_by_me: false }} />));
    expect(await screen.findByRole("button", { name: "Report" })).toBeInTheDocument();
  });

  it("shows the word from sm up on the post page, and 'Reported' afterwards", async () => {
    const user = userEvent.setup();
    renderButton("verified", { showLabel: true });
    const word = await screen.findByText("Report", { selector: "[aria-hidden]" });
    expect(word).toHaveClass("hidden", "sm:inline");
    await report(user);
    await screen.findByText(REPORT_MESSAGES.sent);
    expect(screen.getByText("Reported", { selector: "[aria-hidden]" })).toBeInTheDocument();
    // The visible word is inside the accessible name ("Reported" ⊂ "You reported this").
    expect(screen.getByRole("button", { name: /reported/i })).toBeInTheDocument();
  });

  it("sits above the card's stretched link", async () => {
    renderButton();
    expect(await screen.findByRole("button", { name: "Report" })).toHaveClass("z-10");
  });
});
