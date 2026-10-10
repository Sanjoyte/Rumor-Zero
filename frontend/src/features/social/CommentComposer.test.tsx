import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { CommentComposer, commentProblem } from "./CommentComposer";
import { SOCIAL_MESSAGES } from "./messages";
import { makeComment } from "./test-helpers";

const api = vi.hoisted(() => ({ createComment: vi.fn() }));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  ...api,
}));

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  api.createComment.mockReset();
  api.createComment.mockResolvedValue(makeComment({ id: "new", content: "Hello" }));
});

function renderComposer(kind: SessionKind = "verified", onPosted = vi.fn()) {
  renderWithSessionAndToast(<CommentComposer postId="p1" onPosted={onPosted} />, kind);
  return onPosted;
}

const box = () => screen.findByRole("textbox", { name: "Add a comment" });

describe("commentProblem", () => {
  it("refuses blank and over-long text with the server's words, counting code points", () => {
    expect(commentProblem("")).toBe(SOCIAL_MESSAGES.commentBlank);
    expect(commentProblem("  \n ")).toBe(SOCIAL_MESSAGES.commentBlank);
    expect(commentProblem("x".repeat(501))).toBe(SOCIAL_MESSAGES.commentTooLong);
    expect(commentProblem("x".repeat(500))).toBeNull();
    expect(commentProblem("😀".repeat(500))).toBeNull(); // 1000 UTF-16 units, 500 characters
    expect(commentProblem("😀".repeat(501))).toBe(SOCIAL_MESSAGES.commentTooLong);
    expect(commentProblem(`  ${"x".repeat(500)}  `)).toBeNull(); // trimmed first
  });
});

describe("CommentComposer", () => {
  it("is a log-in link for a visitor, back to the post afterwards", async () => {
    renderComposer("anonymous");
    const link = await screen.findByRole("link", { name: SOCIAL_MESSAGES.logInToComment });
    expect(link).toHaveAttribute("href", "/login?next=%2Fp%2Fp1");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("is a placeholder while the session loads", () => {
    renderComposer("loading");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("is locked with the reason for an unverified email, and sends nothing", async () => {
    renderComposer("unverified");
    expect(await box()).toBeDisabled();
    expect(screen.getByRole("button", { name: "Comment" })).toBeDisabled();
    expect(screen.getByText(SOCIAL_MESSAGES.verifyToComment)).toBeInTheDocument();
    expect(api.createComment).not.toHaveBeenCalled();
  });

  it("counts characters out of 500", async () => {
    renderComposer();
    await userEvent.type(await box(), "Hello");
    expect(screen.getByText("5 / 500 characters")).toBeInTheDocument();
  });

  it("sends the trimmed text, clears the box and hands the saved comment on", async () => {
    const onPosted = renderComposer();
    await userEvent.type(await box(), "  Hello  ");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    await waitFor(() => expect(onPosted).toHaveBeenCalledTimes(1));
    expect(api.createComment).toHaveBeenCalledWith("p1", "Hello");
    expect(onPosted.mock.calls[0][0]).toMatchObject({ id: "new", content: "Hello" });
    expect(await box()).toHaveValue("");
  });

  it("gives the box focus back after posting so the next comment can be typed", async () => {
    renderComposer();
    await userEvent.type(await box(), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    await waitFor(() => expect(screen.getByRole("textbox")).toHaveFocus());
  });

  it("submits with Ctrl+Enter and with Cmd+Enter", async () => {
    renderComposer();
    await userEvent.type(await box(), "one{Control>}{Enter}{/Control}");
    await waitFor(() => expect(api.createComment).toHaveBeenCalledWith("p1", "one"));
    await userEvent.type(await box(), "two{Meta>}{Enter}{/Meta}");
    await waitFor(() => expect(api.createComment).toHaveBeenLastCalledWith("p1", "two"));
  });

  it("a plain Enter adds a line and sends nothing", async () => {
    renderComposer();
    await userEvent.type(await box(), "a{Enter}b");
    expect(await box()).toHaveValue("a\nb");
    expect(api.createComment).not.toHaveBeenCalled();
  });

  it("refuses blank text with the server's words, without a request", async () => {
    renderComposer();
    await userEvent.type(await box(), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.commentBlank)).toBeInTheDocument();
    expect(api.createComment).not.toHaveBeenCalled();
  });

  it("refuses text over 500 characters, without a request, and clears the message on typing", async () => {
    renderComposer();
    const field = await box();
    await userEvent.click(field);
    await userEvent.paste("x".repeat(501));
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.commentTooLong)).toBeInTheDocument();
    expect(api.createComment).not.toHaveBeenCalled();
    await userEvent.type(field, "y");
    expect(screen.queryByText(SOCIAL_MESSAGES.commentTooLong)).toBeNull();
  });

  it("keeps the draft and says why when sending fails", async () => {
    api.createComment.mockRejectedValue(
      new ApiError({ status: 429, code: "throttled", detail: "slow", retryAfter: 600 }),
    );
    const onPosted = renderComposer();
    await userEvent.type(await box(), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    expect(await screen.findByText(/commenting too fast/)).toBeInTheDocument();
    expect(await box()).toHaveValue("Hello");
    expect(onPosted).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Comment" })).toBeEnabled();
  });

  it("shows a server field error in the server's words", async () => {
    api.createComment.mockRejectedValue(
      new ApiError({
        status: 400,
        code: "invalid",
        detail: "x",
        fieldErrors: { content: ["Write something first."] },
      }),
    );
    renderComposer();
    await userEvent.type(await box(), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    expect(await screen.findByText("Write something first.")).toBeInTheDocument();
  });

  it("locks the box while posting and sends one request for two submits in one tick", async () => {
    const pending = deferred<ReturnType<typeof makeComment>>();
    api.createComment.mockReturnValue(pending.promise);
    renderComposer();
    await userEvent.type(await box(), "Hello");
    const button = screen.getByRole("button", { name: "Comment" });
    act(() => {
      button.click();
      button.click();
    });
    expect(api.createComment).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("textbox")).toBeDisabled();
    await act(async () => pending.resolve(makeComment()));
    expect(screen.getByRole("textbox")).toBeEnabled();
  });

  it("shows the Ctrl + Enter hint beside the button", async () => {
    renderComposer();
    expect(await screen.findByText("Ctrl + Enter to post")).toBeInTheDocument();
  });
});
