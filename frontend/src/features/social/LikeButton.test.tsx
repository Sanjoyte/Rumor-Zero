import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { LikeButton } from "./LikeButton";
import { SOCIAL_MESSAGES } from "./messages";

const api = vi.hoisted(() => ({ likePost: vi.fn(), unlikePost: vi.fn() }));
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
  api.likePost.mockReset();
  api.likePost.mockResolvedValue({ liked: true });
  api.unlikePost.mockReset();
  api.unlikePost.mockResolvedValue(undefined);
});

function renderButton(
  kind: SessionKind = "verified",
  props: Partial<React.ComponentProps<typeof LikeButton>> = {},
) {
  return renderWithSessionAndToast(
    <LikeButton postId="p1" initialLiked={false} initialCount={3} {...props} />,
    kind,
  );
}

describe("LikeButton", () => {
  it("is a log-in link for a visitor, back to the post afterwards", async () => {
    renderButton("anonymous");
    const link = await screen.findByRole("link", { name: "Like 3" });
    expect(link).toHaveAttribute("href", "/login?next=%2Fp%2Fp1");
    expect(api.likePost).not.toHaveBeenCalled();
  });

  it("shows the count but nothing to click while the session is loading", () => {
    renderButton("loading");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Like 3")).toBeInTheDocument();
  });

  it("is aria-disabled for an unverified email, explains itself and sends nothing", async () => {
    renderButton("unverified");
    const button = await screen.findByRole("button", { name: "Like 3" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("Verify your email to like posts.");
    await userEvent.click(button);
    expect(await screen.findByText(SOCIAL_MESSAGES.verifyToLike)).toBeInTheDocument();
    expect(api.likePost).not.toHaveBeenCalled();
  });

  it("lets an unverified user who already liked take the like back", async () => {
    renderButton("unverified", { initialLiked: true });
    await userEvent.click(await screen.findByRole("button", { name: "Like 3" }));
    await waitFor(() => expect(api.unlikePost).toHaveBeenCalledWith("p1"));
  });

  it("has a stable name and says whether it is on with aria-pressed", async () => {
    renderButton("verified", { initialLiked: true });
    const button = await screen.findByRole("button", { name: "Like 3" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Like 3" })).toBe(button);
  });

  it("draws the liked glyph filled and in secondary, the unliked one outline", async () => {
    const { unmount } = renderButton("verified", { initialLiked: true });
    const on = (await screen.findByText("favorite")) as HTMLElement;
    expect(on).toHaveClass("text-secondary");
    expect(on.className).toContain("FILL");
    unmount();
    renderButton("verified", { initialLiked: false });
    const off = (await screen.findByText("favorite")) as HTMLElement;
    expect(off).not.toHaveClass("text-secondary");
    expect(off.className).not.toContain("FILL");
  });

  it("flips at once, before the request finishes, and tells the parent the new count", async () => {
    const pending = deferred<{ liked: true }>();
    api.likePost.mockReturnValue(pending.promise);
    const onChange = vi.fn();
    renderButton("verified", { onChange });
    await userEvent.click(await screen.findByRole("button", { name: "Like 3" }));
    expect(api.likePost).toHaveBeenCalledWith("p1");
    expect(onChange).toHaveBeenCalledWith(true, 4);
    expect(screen.getByRole("button", { name: "Like 4" })).toHaveAttribute("aria-pressed", "true");
    await act(async () => pending.resolve({ liked: true }));
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("unlikes when it is on, and the count goes down", async () => {
    const onChange = vi.fn();
    renderButton("verified", { initialLiked: true, initialCount: 1, onChange });
    await userEvent.click(await screen.findByRole("button", { name: "Like 1" }));
    expect(api.unlikePost).toHaveBeenCalledWith("p1");
    expect(await screen.findByRole("button", { name: "Like 0" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(onChange).toHaveBeenCalledWith(false, 0);
  });

  it("prints a long count compactly", async () => {
    renderButton("verified", { initialCount: 1400 });
    expect(await screen.findByRole("button", { name: "Like 1.4K" })).toBeInTheDocument();
  });

  it("rolls back, tells the parent and toasts when a like fails", async () => {
    api.likePost.mockRejectedValue(
      new ApiError({ status: 403, code: "email_unverified", detail: "no" }),
    );
    const onChange = vi.fn();
    renderButton("verified", { onChange });
    await userEvent.click(await screen.findByRole("button", { name: "Like 3" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.verifyToLike)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Like 3" })).toHaveAttribute("aria-pressed", "false");
    expect(onChange.mock.calls).toEqual([
      [true, 4],
      [false, 3],
    ]);
  });

  it("rolls back an unlike that fails, with the unlike message", async () => {
    api.unlikePost.mockRejectedValue(new ApiError({ status: 500, code: "x", detail: "x" }));
    renderButton("verified", { initialLiked: true });
    await userEvent.click(await screen.findByRole("button", { name: "Like 3" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.unlikeFailed)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Like 3" })).toHaveAttribute("aria-pressed", "true");
  });

  it("sends one request for a double click, and for two clicks in one tick", async () => {
    const pending = deferred<{ liked: true }>();
    api.likePost.mockReturnValue(pending.promise);
    renderButton();
    const button = await screen.findByRole("button", { name: "Like 3" });
    act(() => {
      button.click();
      button.click(); // same tick: React hasn't re-rendered yet, only the ref can stop this
    });
    expect(api.likePost).toHaveBeenCalledTimes(1);
    expect(api.unlikePost).not.toHaveBeenCalled();
    await act(async () => pending.resolve({ liked: true }));
  });

  it("follows the server when the post is refetched with other numbers", async () => {
    function Harness() {
      const [server, setServer] = useState({ liked: false, count: 3 });
      return (
        <>
          <button onClick={() => setServer({ liked: true, count: 9 })}>server says so</button>
          <LikeButton postId="p1" initialLiked={server.liked} initialCount={server.count} />
        </>
      );
    }
    renderWithSessionAndToast(<Harness />);
    expect(await screen.findByRole("button", { name: "Like 3" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "server says so" }));
    expect(await screen.findByRole("button", { name: "Like 9" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(api.likePost).not.toHaveBeenCalled();
  });

  it("shows the word Like beside the glyph on the post page", async () => {
    renderButton("verified", { showLabel: true });
    expect(await screen.findByText("Like", { selector: "[aria-hidden]" })).toHaveClass("sm:inline");
  });
});
