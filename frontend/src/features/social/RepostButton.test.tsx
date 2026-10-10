import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { SOCIAL_MESSAGES } from "./messages";
import { RepostButton } from "./RepostButton";

const api = vi.hoisted(() => ({ repostPost: vi.fn(), unrepostPost: vi.fn() }));
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
  api.repostPost.mockReset();
  api.repostPost.mockResolvedValue({ reposted: true });
  api.unrepostPost.mockReset();
  api.unrepostPost.mockResolvedValue(undefined);
});

function renderButton(
  kind: SessionKind = "verified",
  props: Partial<React.ComponentProps<typeof RepostButton>> = {},
) {
  return renderWithSessionAndToast(
    <RepostButton postId="p1" initialReposted={false} initialCount={3} {...props} />,
    kind,
  );
}

describe("RepostButton", () => {
  it("is a log-in link for a visitor, back to the post afterwards", async () => {
    renderButton("anonymous");
    const link = await screen.findByRole("link", { name: "Repost 3" });
    expect(link).toHaveAttribute("href", "/login?next=%2Fp%2Fp1");
    expect(api.repostPost).not.toHaveBeenCalled();
  });

  it("shows the count but nothing to click while the session is loading", () => {
    renderButton("loading");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Repost 3")).toBeInTheDocument();
  });

  it("is aria-disabled for an unverified email, explains itself and sends nothing", async () => {
    renderButton("unverified");
    const button = await screen.findByRole("button", { name: "Repost 3" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("Verify your email to repost posts.");
    await userEvent.click(button);
    expect(await screen.findByText(SOCIAL_MESSAGES.verifyToRepost)).toBeInTheDocument();
    expect(api.repostPost).not.toHaveBeenCalled();
  });

  it("lets an unverified user who already reposted take the repost back", async () => {
    renderButton("unverified", { initialReposted: true });
    const button = await screen.findByRole("button", { name: "Repost 3" });
    expect(button).not.toHaveAttribute("aria-disabled");
    await userEvent.click(button);
    await waitFor(() => expect(api.unrepostPost).toHaveBeenCalledWith("p1"));
  });

  it.each([
    ["your own post", SOCIAL_MESSAGES.cannotRepostOwn],
    ["a FALSE post", SOCIAL_MESSAGES.cannotRepostFalse],
    ["a removed post", SOCIAL_MESSAGES.cannotRepostRemoved],
  ])("is disabled with the reason for %s, and sends nothing", async (_, reason) => {
    renderButton("verified", { blockedReason: reason });
    const button = await screen.findByRole("button", { name: "Repost 3" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAttribute("title", reason);
    expect(button).toHaveAccessibleDescription(reason);
    await userEvent.click(button);
    expect(api.repostPost).not.toHaveBeenCalled();
    expect(await screen.findAllByText(reason)).not.toHaveLength(0);
  });

  it("says the post's own reason before asking to verify the email", async () => {
    renderButton("unverified", { blockedReason: SOCIAL_MESSAGES.cannotRepostFalse });
    const button = await screen.findByRole("button", { name: "Repost 3" });
    expect(button).toHaveAccessibleDescription(SOCIAL_MESSAGES.cannotRepostFalse);
  });

  it("stays enabled to undo a repost even when the post can no longer be reposted", async () => {
    renderButton("verified", {
      initialReposted: true,
      blockedReason: SOCIAL_MESSAGES.cannotRepostFalse,
    });
    const button = await screen.findByRole("button", { name: "Repost 3" });
    expect(button).not.toHaveAttribute("aria-disabled");
    await userEvent.click(button);
    expect(api.unrepostPost).toHaveBeenCalledWith("p1");
  });

  it("has a stable name and says whether it is on with aria-pressed", async () => {
    renderButton("verified", { initialReposted: true });
    const button = await screen.findByRole("button", { name: "Repost 3" });
    expect(button).toHaveAttribute("aria-pressed", "true");
  });

  it("draws the reposted glyph in secondary and the other one plain", async () => {
    const { unmount } = renderButton("verified", { initialReposted: true });
    expect(await screen.findByText("cached")).toHaveClass("text-secondary");
    unmount();
    renderButton("verified", { initialReposted: false });
    expect(await screen.findByText("cached")).not.toHaveClass("text-secondary");
  });

  it("flips at once, before the request finishes", async () => {
    const pending = deferred<{ reposted: true }>();
    api.repostPost.mockReturnValue(pending.promise);
    renderButton();
    await userEvent.click(await screen.findByRole("button", { name: "Repost 3" }));
    expect(api.repostPost).toHaveBeenCalledWith("p1");
    expect(screen.getByRole("button", { name: "Repost 4" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await act(async () => pending.resolve({ reposted: true }));
  });

  it("undoes a repost, and the count goes down but never below zero", async () => {
    renderButton("verified", { initialReposted: true, initialCount: 1 });
    await userEvent.click(await screen.findByRole("button", { name: "Repost 1" }));
    expect(api.unrepostPost).toHaveBeenCalledWith("p1");
    expect(await screen.findByRole("button", { name: "Repost 0" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("never shows a negative count, even if the server's number was behind", async () => {
    renderButton("verified", { initialReposted: true, initialCount: 0 });
    await userEvent.click(await screen.findByRole("button", { name: "Repost 0" }));
    expect(await screen.findByRole("button", { name: "Repost 0" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("prints a long count compactly", async () => {
    renderButton("verified", { initialCount: 1400 });
    expect(await screen.findByRole("button", { name: "Repost 1.4K" })).toBeInTheDocument();
  });

  it.each([
    [{ status: 409, code: "cannot_repost_own" }, SOCIAL_MESSAGES.cannotRepostOwn],
    [{ status: 409, code: "cannot_repost_false" }, SOCIAL_MESSAGES.cannotRepostFalse],
    [{ status: 403, code: "email_unverified" }, SOCIAL_MESSAGES.verifyToRepost],
    [{ status: 500, code: "x" }, SOCIAL_MESSAGES.repostFailed],
  ])("rolls back and toasts the reason when a repost fails (%o)", async (failure, message) => {
    api.repostPost.mockRejectedValue(new ApiError({ ...failure, detail: "no" }));
    renderButton();
    await userEvent.click(await screen.findByRole("button", { name: "Repost 3" }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repost 3" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("rolls back an undo that fails, with the undo message", async () => {
    api.unrepostPost.mockRejectedValue(new ApiError({ status: 500, code: "x", detail: "x" }));
    renderButton("verified", { initialReposted: true });
    await userEvent.click(await screen.findByRole("button", { name: "Repost 3" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.unrepostFailed)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repost 3" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("sends one request for two clicks in one tick", async () => {
    const pending = deferred<{ reposted: true }>();
    api.repostPost.mockReturnValue(pending.promise);
    renderButton();
    const button = await screen.findByRole("button", { name: "Repost 3" });
    act(() => {
      button.click();
      button.click();
    });
    expect(api.repostPost).toHaveBeenCalledTimes(1);
    expect(api.unrepostPost).not.toHaveBeenCalled();
    await act(async () => pending.resolve({ reposted: true }));
  });

  it("follows the server when the post is refetched with other numbers", async () => {
    function Harness() {
      const [server, setServer] = useState({ reposted: false, count: 3 });
      return (
        <>
          <button onClick={() => setServer({ reposted: true, count: 9 })}>server says so</button>
          <RepostButton postId="p1" initialReposted={server.reposted} initialCount={server.count} />
        </>
      );
    }
    renderWithSessionAndToast(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "server says so" }));
    expect(await screen.findByRole("button", { name: "Repost 9" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(api.repostPost).not.toHaveBeenCalled();
  });

  it("shows the word Repost beside the glyph on the post page", async () => {
    renderButton("verified", { showLabel: true });
    expect(await screen.findByText("Repost", { selector: "[aria-hidden]" })).toHaveClass(
      "sm:inline",
    );
  });

  it("gives each disabled button its own hint id (a feed has many)", async () => {
    renderWithSessionAndToast(
      <>
        <RepostButton postId="a" initialReposted={false} initialCount={0} blockedReason="no" />
        <RepostButton postId="b" initialReposted={false} initialCount={0} blockedReason="no" />
      </>,
    );
    const [first, second] = await screen.findAllByRole("button");
    expect(first.getAttribute("aria-describedby")).not.toBe(
      second.getAttribute("aria-describedby"),
    );
  });
});
