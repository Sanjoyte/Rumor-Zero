import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithComposer, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { FollowButton } from "./FollowButton";
import { SOCIAL_MESSAGES } from "./messages";

const api = vi.hoisted(() => ({ followUser: vi.fn(), unfollowUser: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/u/bob",
}));
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
  api.followUser.mockReset();
  api.followUser.mockResolvedValue({ is_following: true });
  api.unfollowUser.mockReset();
  api.unfollowUser.mockResolvedValue(undefined);
});

function renderButton(
  kind: SessionKind = "verified",
  props: Partial<React.ComponentProps<typeof FollowButton>> = {},
) {
  return renderWithComposer(
    <FollowButton username="bob" initialFollowing={false} {...props} />,
    kind,
  );
}

describe("FollowButton", () => {
  it("is a log-in link for a visitor, back to the profile afterwards", async () => {
    renderButton("anonymous");
    const link = await screen.findByRole("link", { name: "Follow" });
    expect(link).toHaveAttribute("href", "/login?next=%2Fu%2Fbob");
    expect(api.followUser).not.toHaveBeenCalled();
  });

  it("says Follow back when a screen asks for it, in every state", async () => {
    const first = renderButton("verified", { label: "Follow back" });
    expect(await screen.findByRole("button", { name: "Follow back" })).toBeInTheDocument();
    first.unmount();
    const second = renderButton("anonymous", { label: "Follow back" });
    expect(await screen.findByRole("link", { name: "Follow back" })).toBeInTheDocument();
    second.unmount();
    renderButton("unverified", { label: "Follow back" });
    expect(await screen.findByRole("button", { name: "Follow back" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("renders nothing to click while the session is loading", () => {
    renderButton("loading");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("is aria-disabled for an unverified email, explains itself and sends nothing", async () => {
    renderButton("unverified");
    const button = await screen.findByRole("button", { name: "Follow" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("Verify your email to follow people.");
    await userEvent.click(button);
    expect(await screen.findByText(SOCIAL_MESSAGES.verifyToFollow)).toBeInTheDocument();
    expect(api.followUser).not.toHaveBeenCalled();
  });

  it("lets an unverified user who already follows unfollow", async () => {
    renderButton("unverified", { initialFollowing: true });
    await userEvent.click(await screen.findByRole("button", { name: "Following" }));
    await waitFor(() => expect(api.unfollowUser).toHaveBeenCalledWith("bob"));
  });

  it("flips at once, before the request finishes, and tells the parent", async () => {
    const pending = deferred<{ is_following: true }>();
    api.followUser.mockReturnValue(pending.promise);
    const onChange = vi.fn();
    renderButton("verified", { onChange });
    await userEvent.click(await screen.findByRole("button", { name: "Follow" }));
    expect(api.followUser).toHaveBeenCalledWith("bob");
    expect(onChange).toHaveBeenCalledWith(true);
    expect(screen.getByRole("button", { name: "Following" })).toBeDisabled(); // busy
    await act(async () => pending.resolve({ is_following: true }));
    expect(screen.getByRole("button", { name: "Following" })).toBeEnabled();
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("unfollows when it says Following; the accessible name is 'Following', the hover word is hidden", async () => {
    const onChange = vi.fn();
    renderButton("verified", { initialFollowing: true, onChange });
    const button = await screen.findByRole("button", { name: "Following" });
    expect(button).toHaveAttribute("title", "Unfollow @bob");
    expect(screen.getByText("Unfollow")).toHaveAttribute("aria-hidden", "true");
    await userEvent.click(button);
    expect(api.unfollowUser).toHaveBeenCalledWith("bob");
    expect(await screen.findByRole("button", { name: "Follow" })).toBeInTheDocument();
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("rolls back and toasts when a follow fails", async () => {
    api.followUser.mockRejectedValue(
      new ApiError({ status: 403, code: "email_unverified", detail: "no" }),
    );
    const onChange = vi.fn();
    renderButton("verified", { onChange });
    await userEvent.click(await screen.findByRole("button", { name: "Follow" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.verifyToFollow)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Follow" })).toBeEnabled();
    expect(onChange.mock.calls).toEqual([[true], [false]]);
  });

  it("rolls back an unfollow that fails", async () => {
    api.unfollowUser.mockRejectedValue(new ApiError({ status: 500, code: "x", detail: "x" }));
    const onChange = vi.fn();
    renderButton("verified", { initialFollowing: true, onChange });
    await userEvent.click(await screen.findByRole("button", { name: "Following" }));
    expect(await screen.findByText(SOCIAL_MESSAGES.unfollowFailed)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Following" })).toBeInTheDocument();
    expect(onChange.mock.calls).toEqual([[false], [true]]);
  });

  it("sends one request for a double click", async () => {
    const pending = deferred<{ is_following: true }>();
    api.followUser.mockReturnValue(pending.promise);
    renderButton();
    const button = await screen.findByRole("button", { name: "Follow" });
    await userEvent.dblClick(button);
    expect(api.followUser).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve({ is_following: true }));
    expect(api.unfollowUser).not.toHaveBeenCalled();
  });

  it("ignores a second click that arrives before React has re-rendered", async () => {
    const pending = deferred<{ is_following: true }>();
    api.followUser.mockReturnValue(pending.promise);
    renderButton();
    const button = await screen.findByRole("button", { name: "Follow" });
    act(() => {
      button.click();
      button.click(); // same tick: the disabled state hasn't been painted yet
    });
    expect(api.followUser).toHaveBeenCalledTimes(1);
    expect(api.unfollowUser).not.toHaveBeenCalled();
    await act(async () => pending.resolve({ is_following: true }));
  });

  it("follows the server when the profile is refetched with another answer", async () => {
    function Harness() {
      const [server, setServer] = useState(false);
      return (
        <>
          <button onClick={() => setServer(true)}>server says yes</button>
          <FollowButton username="bob" initialFollowing={server} />
        </>
      );
    }
    renderWithComposer(<Harness />);
    expect(await screen.findByRole("button", { name: "Follow" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "server says yes" }));
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
    expect(api.followUser).not.toHaveBeenCalled();
  });
});
