import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { BookmarkButton } from "./BookmarkButton";
import { SOCIAL_MESSAGES } from "./messages";

const api = vi.hoisted(() => ({ bookmarkPost: vi.fn(), unbookmarkPost: vi.fn() }));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  ...api,
}));

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

beforeEach(() => {
  api.bookmarkPost.mockReset();
  api.bookmarkPost.mockResolvedValue({ bookmarked: true });
  api.unbookmarkPost.mockReset();
  api.unbookmarkPost.mockResolvedValue(undefined);
});

function renderButton(kind: SessionKind = "verified", initialBookmarked = false) {
  return renderWithSessionAndToast(
    <BookmarkButton postId="p1" initialBookmarked={initialBookmarked} />,
    kind,
  );
}

describe("BookmarkButton", () => {
  it("is a log-in link for a visitor", async () => {
    renderButton("anonymous");
    expect(await screen.findByRole("link", { name: "Bookmark" })).toHaveAttribute(
      "href",
      "/login?next=%2Fp%2Fp1",
    );
  });

  it("has nothing to click while the session is loading", () => {
    renderButton("loading");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("works for an unverified email: bookmarks are private, so nothing is checked", async () => {
    renderButton("unverified");
    const button = await screen.findByRole("button", { name: "Bookmark" });
    expect(button).not.toHaveAttribute("aria-disabled");
    await userEvent.click(button);
    expect(api.bookmarkPost).toHaveBeenCalledWith("p1");
  });

  it("shows no count, only a glyph and a stable name", async () => {
    renderButton("verified", true);
    const button = await screen.findByRole("button", { name: "Bookmark" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(button.textContent).toBe("bookmarkBookmark"); // the glyph name and the sr-only name
    expect(button.querySelector("[aria-hidden='true'].tabular-nums")).toBeNull();
  });

  it("draws the saved glyph filled and in secondary, the other one outline", async () => {
    const { unmount } = renderButton("verified", true);
    const on = (await screen.findByText("bookmark")) as HTMLElement;
    expect(on).toHaveClass("text-secondary");
    expect(on.className).toContain("FILL");
    unmount();
    renderButton("verified", false);
    const off = (await screen.findByText("bookmark")) as HTMLElement;
    expect(off).not.toHaveClass("text-secondary");
    expect(off.className).not.toContain("FILL");
  });

  it("flips at once and sends a bookmark, then a removal", async () => {
    const pending = deferred<{ bookmarked: true }>();
    api.bookmarkPost.mockReturnValue(pending.promise);
    renderButton();
    await userEvent.click(await screen.findByRole("button", { name: "Bookmark" }));
    expect(screen.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await act(async () => pending.resolve({ bookmarked: true }));
    await userEvent.click(screen.getByRole("button", { name: "Bookmark" }));
    expect(api.unbookmarkPost).toHaveBeenCalledWith("p1");
    expect(screen.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it.each([
    [{ status: 500, code: "x" }, SOCIAL_MESSAGES.bookmarkFailed],
    [{ status: 404, code: "not_found" }, SOCIAL_MESSAGES.postGone],
  ])("rolls back and toasts when a bookmark fails (%o)", async (failure, message) => {
    api.bookmarkPost.mockRejectedValue(new ApiError({ ...failure, detail: "no" }));
    renderButton();
    await userEvent.click(await screen.findByRole("button", { name: "Bookmark" }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("rolls back a removal that fails, with the removal message", async () => {
    api.unbookmarkPost.mockRejectedValue(new ApiError({ status: 500, code: "x", detail: "x" }));
    renderButton("verified", true);
    await userEvent.click(await screen.findByRole("button", { name: "Bookmark" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.unbookmarkFailed)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("sends one request for two clicks in one tick", async () => {
    const pending = deferred<{ bookmarked: true }>();
    api.bookmarkPost.mockReturnValue(pending.promise);
    renderButton();
    const button = await screen.findByRole("button", { name: "Bookmark" });
    act(() => {
      button.click();
      button.click();
    });
    expect(api.bookmarkPost).toHaveBeenCalledTimes(1);
    expect(api.unbookmarkPost).not.toHaveBeenCalled();
    await act(async () => pending.resolve({ bookmarked: true }));
  });

  it("follows the server when the post is refetched", async () => {
    function Harness() {
      const [saved, setSaved] = useState(false);
      return (
        <>
          <button onClick={() => setSaved(true)}>server says so</button>
          <BookmarkButton postId="p1" initialBookmarked={saved} />
        </>
      );
    }
    renderWithSessionAndToast(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "server says so" }));
    expect(await screen.findByRole("button", { name: "Bookmark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(api.bookmarkPost).not.toHaveBeenCalled();
  });
});
