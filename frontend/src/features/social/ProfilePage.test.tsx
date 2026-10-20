import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ComposerTrigger } from "@/features/posts/ComposerTrigger";
import {
  feedEntry,
  makePost,
  renderWithComposer,
  type SessionKind,
} from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { makeEntry, makeSummary } from "@/features/reputation/test-helpers";
import { ProfilePage } from "./ProfilePage";
import { makeProfile } from "./test-helpers";

const api = vi.hoisted(() => ({
  fetchProfile: vi.fn(),
  fetchUserPosts: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
}));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  ...api,
}));
const posts = vi.hoisted(() => ({
  fetchStatuses: vi.fn(),
  createPost: vi.fn(),
  fetchFactQuota: vi.fn(),
}));
vi.mock("@/features/posts/posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/posts/posts-api")>()),
  ...posts,
}));
const reputation = vi.hoisted(() => ({
  fetchReputation: vi.fn(),
  fetchMyReputationEvents: vi.fn(),
}));
vi.mock("@/features/reputation/reputation-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/reputation/reputation-api")>()),
  ...reputation,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/u/bob",
}));

const page = (ids: string[], nextCursor: string | null = null) => ({
  items: ids.map((id) => feedEntry(makePost({ id, content: `Post ${id}`, is_mine: false }))),
  nextCursor,
});
const cards = () => screen.queryAllByRole("article");

beforeEach(() => {
  api.fetchProfile.mockReset();
  api.fetchProfile.mockResolvedValue(makeProfile());
  api.fetchUserPosts.mockReset();
  api.fetchUserPosts.mockResolvedValue(page(["a", "b"]));
  api.followUser.mockReset();
  api.followUser.mockResolvedValue({ is_following: true });
  api.unfollowUser.mockReset();
  api.unfollowUser.mockResolvedValue(undefined);
  reputation.fetchReputation.mockReset();
  reputation.fetchReputation.mockResolvedValue(makeSummary());
  reputation.fetchMyReputationEvents.mockReset();
  reputation.fetchMyReputationEvents.mockResolvedValue({ items: [makeEntry()], nextCursor: null });
  posts.fetchStatuses.mockReset();
  posts.fetchStatuses.mockResolvedValue([]);
  posts.createPost.mockReset();
  posts.fetchFactQuota.mockReset();
  posts.fetchFactQuota.mockResolvedValue({
    limit: 10,
    used: 0,
    remaining: 10,
    window_hours: 24,
    next_slot_at: null,
  });
});

function renderPage(
  kind: SessionKind = "verified",
  { initial = makeProfile() as ReturnType<typeof makeProfile> | null, strict = false } = {},
) {
  const ui: ReactNode = <ProfilePage username="bob" initial={initial} />;
  return renderWithComposer(strict ? <StrictMode>{ui}</StrictMode> : ui, kind);
}

/** Mounts its children only after the session settled: the order a client navigation gives. */
function AfterSession({ children }: { children: ReactNode }) {
  return useAuth().status === "authenticated" ? <>{children}</> : null;
}

describe("ProfilePage: the server-rendered start", () => {
  it("shows the header and the posts, and a visitor makes no profile request", async () => {
    renderPage("anonymous");
    expect(await screen.findByRole("heading", { level: 1, name: "Bob Stone" })).toBeInTheDocument();
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(api.fetchProfile).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Follow" })).toHaveAttribute(
      "href",
      "/login?next=%2Fu%2Fbob",
    );
  });

  it("fetches once for a signed-in visitor, to learn is_following", async () => {
    api.fetchProfile.mockResolvedValue(makeProfile({ is_following: true }));
    renderPage("verified");
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
    expect(api.fetchProfile).toHaveBeenCalledTimes(1);
    expect(api.fetchProfile).toHaveBeenCalledWith("bob", expect.any(AbortSignal));
  });

  it("shows no follow button until that fetch lands (it never flashes the wrong state)", async () => {
    let resolve!: (value: ReturnType<typeof makeProfile>) => void;
    api.fetchProfile.mockReturnValue(new Promise((res) => (resolve = res)));
    renderPage("verified");
    await screen.findByRole("heading", { level: 1, name: "Bob Stone" });
    expect(screen.queryByRole("button", { name: /Follow/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Edit profile/ })).not.toBeInTheDocument();
    await act(async () => resolve(makeProfile({ is_following: true })));
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
  });

  it("shows Edit profile on your own page once the fetch says is_me", async () => {
    api.fetchProfile.mockResolvedValue(makeProfile({ username: "ada", is_me: true }));
    renderPage("verified");
    expect(await screen.findByRole("link", { name: /Edit profile/ })).toHaveAttribute(
      "href",
      "/settings",
    );
  });

  it("still fetches when mounted after the session settled, under StrictMode", async () => {
    // StrictMode aborts the first request; the viewer must not be marked as fetched too early.
    api.fetchProfile.mockResolvedValue(makeProfile({ is_following: true }));
    renderWithComposer(
      <StrictMode>
        <AfterSession>
          <ProfilePage username="bob" initial={makeProfile()} />
        </AfterSession>
      </StrictMode>,
      "verified",
    );
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
  });

  it("without a server render, shows a skeleton and then fetches as soon as the session is known", async () => {
    renderPage("anonymous", { initial: null });
    expect(await screen.findByRole("heading", { level: 1, name: "Bob Stone" })).toBeInTheDocument();
    expect(api.fetchProfile).toHaveBeenCalledTimes(1);
  });

  it("does not fetch while the session is loading", async () => {
    renderPage("loading", { initial: null });
    expect(screen.getByText("Loading profile…")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.fetchProfile).not.toHaveBeenCalled();
    expect(api.fetchUserPosts).not.toHaveBeenCalled();
  });

  it("says so when there is no such account", async () => {
    api.fetchProfile.mockRejectedValue(
      new ApiError({ status: 404, code: "not_found", detail: "x" }),
    );
    renderPage("anonymous", { initial: null });
    expect(await screen.findByText("Profile not found")).toBeInTheDocument();
  });

  it("shows an error with Try again when the profile can't load", async () => {
    api.fetchProfile
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }))
      .mockResolvedValueOnce(makeProfile());
    renderPage("anonymous", { initial: null });
    expect(await screen.findByText("Couldn't load this profile")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Bob Stone" })).toBeInTheDocument();
  });

  it("keeps the page it has when a quiet refetch fails", async () => {
    api.fetchProfile.mockRejectedValue(new ApiError({ status: 500, code: "x", detail: "x" }));
    renderPage("verified");
    await screen.findByRole("heading", { level: 1, name: "Bob Stone" });
    await waitFor(() => expect(api.fetchProfile).toHaveBeenCalled());
    expect(screen.queryByText("Couldn't load this profile")).not.toBeInTheDocument();
  });
});

describe("ProfilePage: following", () => {
  it("moves the follower count at once and puts it back when the request fails", async () => {
    api.fetchProfile.mockResolvedValue(makeProfile());
    renderPage("verified");
    const header = await screen.findByRole("region", { name: "Profile" });
    expect(within(header).getByText("1,420")).toBeInTheDocument();
    api.followUser.mockRejectedValueOnce(new ApiError({ status: 500, code: "x", detail: "x" }));
    await userEvent.click(await screen.findByRole("button", { name: "Follow" }));
    await waitFor(() => expect(api.followUser).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Couldn't follow. Try again.")).toBeInTheDocument();
    expect(within(header).getByText("1,420")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Follow" }));
    expect(await within(header).findByText("1,421")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Following" }));
    expect(await within(header).findByText("1,420")).toBeInTheDocument();
  });
});

describe("ProfilePage: the post list", () => {
  it("loads the person's posts, newest first, and ends with 'You're caught up.'", async () => {
    renderPage("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(api.fetchUserPosts).toHaveBeenCalledWith("bob", "all", null, expect.any(AbortSignal));
    expect(screen.getByText("You're caught up.")).toBeInTheDocument();
  });

  it("loads more with the cursor", async () => {
    api.fetchUserPosts.mockResolvedValueOnce(page(["a"], "c1")).mockResolvedValueOnce(page(["b"]));
    renderPage("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(api.fetchUserPosts).toHaveBeenLastCalledWith(
      "bob",
      "all",
      "c1",
      expect.any(AbortSignal),
    );
  });

  it("filters with All / Facts / Opinions, starting again from the top each time", async () => {
    renderPage("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    api.fetchUserPosts.mockResolvedValue(page(["f1"]));
    await userEvent.click(screen.getByRole("button", { name: "Facts" }));
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(api.fetchUserPosts).toHaveBeenLastCalledWith(
      "bob",
      "fact",
      null,
      expect.any(AbortSignal),
    );
    expect(screen.getByRole("button", { name: "Facts" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Opinions" }));
    await waitFor(() =>
      expect(api.fetchUserPosts).toHaveBeenLastCalledWith(
        "bob",
        "opinion",
        null,
        expect.any(AbortSignal),
      ),
    );
  });

  it("goes back to All when the pressed chip is pressed again", async () => {
    renderPage("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: "Facts" }));
    await userEvent.click(screen.getByRole("button", { name: "Facts" }));
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(api.fetchUserPosts).toHaveBeenLastCalledWith(
      "bob",
      "all",
      null,
      expect.any(AbortSignal),
    );
  });

  it("words the empty state for someone else, and for a filter", async () => {
    api.fetchUserPosts.mockResolvedValue(page([]));
    renderPage("anonymous");
    expect(await screen.findByText("No posts yet")).toBeInTheDocument();
    expect(screen.getByText("Bob Stone hasn't shared any posts yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Facts" }));
    expect(await screen.findByText("No fact posts yet")).toBeInTheDocument();
  });

  it("words the empty state for your own profile", async () => {
    api.fetchUserPosts.mockResolvedValue(page([]));
    api.fetchProfile.mockResolvedValue(makeProfile({ username: "ada", is_me: true }));
    renderPage("verified");
    expect(await screen.findByText("You haven't shared any posts yet.")).toBeInTheDocument();
  });

  it("shows an error with Try again", async () => {
    api.fetchUserPosts
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }))
      .mockResolvedValueOnce(page(["a"]));
    renderPage("anonymous");
    expect(await screen.findByText("Couldn't load posts")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(cards()).toHaveLength(1));
  });

  it("links each card's author to this profile and its claim to the post", async () => {
    renderPage("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(2));
    const card = cards()[0];
    expect(within(card).getByRole("link", { name: /Ada/ })).toHaveAttribute("href", "/u/ada");
  });
});

describe("ProfilePage: live badges", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => vi.useRealTimers());

  it("polls the pending posts it lists and updates the badge", async () => {
    api.fetchUserPosts.mockResolvedValue({
      items: [
        feedEntry(makePost({ id: "p1", post_type: "fact", status: "pending", is_mine: false })),
      ],
      nextCursor: null,
    });
    posts.fetchStatuses.mockResolvedValue([
      { id: "p1", status: "verified_true", confidence_score: "94.00", verdict_source: "pipeline" },
    ]);
    renderPage("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(screen.getByText(/CHECKING FACTS/)).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    await waitFor(() => expect(screen.getByText(/VERIFIED 94%/)).toBeInTheDocument());
    expect(posts.fetchStatuses).toHaveBeenCalledWith(["p1"], expect.any(AbortSignal));
  });
});

describe("ProfilePage: your own new post", () => {
  async function postOpinion(text: string) {
    await userEvent.click(await screen.findByRole("button", { name: /What do you want to say/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Opinion" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), text);
    await userEvent.click(screen.getByRole("button", { name: "Post opinion" }));
  }

  it("is added at the top of your own profile", async () => {
    api.fetchProfile.mockResolvedValue(makeProfile({ username: "ada", is_me: true }));
    posts.createPost.mockResolvedValue(
      makePost({ id: "mine", content: "Brand new", is_mine: true }),
    );
    renderWithComposer(
      <>
        <ComposerTrigger />
        <ProfilePage username="ada" initial={makeProfile({ username: "ada" })} />
      </>,
    );
    await waitFor(() => expect(cards()).toHaveLength(2));
    await screen.findByRole("link", { name: /Edit profile/ });
    await postOpinion("Brand new");
    await waitFor(() => expect(cards()).toHaveLength(3));
    expect(within(cards()[0]).getByText(/Brand new/)).toBeInTheDocument();
    expect(api.fetchUserPosts).toHaveBeenCalledTimes(1);
  });

  it("is added only when it matches the filter in use", async () => {
    api.fetchProfile.mockResolvedValue(makeProfile({ username: "ada", is_me: true }));
    posts.createPost.mockResolvedValue(
      makePost({ id: "mine", content: "Brand new", is_mine: true }),
    );
    renderWithComposer(
      <>
        <ComposerTrigger />
        <ProfilePage username="ada" initial={makeProfile({ username: "ada" })} />
      </>,
    );
    await waitFor(() => expect(cards()).toHaveLength(2));
    await screen.findByRole("link", { name: /Edit profile/ });
    api.fetchUserPosts.mockResolvedValue(page(["f1"]));
    await userEvent.click(screen.getByRole("button", { name: "Facts" }));
    await waitFor(() => expect(cards()).toHaveLength(1));
    await postOpinion("Brand new"); // an opinion: not for the Facts list
    await waitFor(() => expect(posts.createPost).toHaveBeenCalled());
    await screen.findByText(/Posted\./);
    expect(cards()).toHaveLength(1);
    expect(screen.queryByText(/Brand new/)).not.toBeInTheDocument();
  });

  it("is not added to someone else's profile", async () => {
    posts.createPost.mockResolvedValue(
      makePost({ id: "mine", content: "Brand new", is_mine: true }),
    );
    renderWithComposer(
      <>
        <ComposerTrigger />
        <ProfilePage username="bob" initial={makeProfile()} />
      </>,
    );
    await waitFor(() => expect(cards()).toHaveLength(2));
    await screen.findByRole("button", { name: "Follow" });
    await postOpinion("Brand new");
    await waitFor(() => expect(posts.createPost).toHaveBeenCalled());
    expect(cards()).toHaveLength(2);
  });
});

describe("ProfilePage: the credibility widget and panel (Part 11D)", () => {
  const scored = (overrides = {}) =>
    makeProfile({
      reputation: { score: 68, sample: 23 },
      counts: { followers: 1, following: 1, posts: 30, verified: 20, false: 3 },
      ...overrides,
    });

  it("shows the widget to a visitor, between the header and the filter chips", async () => {
    api.fetchProfile.mockResolvedValue(scored());
    renderPage("anonymous", { initial: scored() });
    const widget = await screen.findByRole("region", { name: "Credibility" });
    const header = screen.getByRole("region", { name: "Profile" });
    const chips = screen.getByRole("group", { name: "Show" });
    expect(header.compareDocumentPosition(widget) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(widget.compareDocumentPosition(chips) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await within(widget).findByText("Last 30 days");
    expect(reputation.fetchReputation).toHaveBeenCalledWith("bob", expect.any(AbortSignal));
  });

  it("keeps the header free of the widget's numbers", async () => {
    renderPage("anonymous", { initial: scored() });
    const header = await screen.findByRole("region", { name: "Profile" });
    expect(within(header).queryByText("3 FALSE")).not.toBeInTheDocument();
    expect(within(header).queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows New and makes no trend request for an account with a hidden score", async () => {
    renderPage("anonymous");
    const widget = await screen.findByRole("region", { name: "Credibility" });
    expect(within(widget).getByRole("img", { name: /^Credibility: New/ })).toBeInTheDocument();
    expect(reputation.fetchReputation).not.toHaveBeenCalled();
  });

  it("never shows your history panel to a visitor or on someone else's profile", async () => {
    renderPage("verified");
    await screen.findByRole("region", { name: "Credibility" });
    await waitFor(() => expect(api.fetchProfile).toHaveBeenCalled());
    expect(
      screen.queryByRole("heading", { name: "Your credibility history" }),
    ).not.toBeInTheDocument();
    expect(reputation.fetchMyReputationEvents).not.toHaveBeenCalled();
  });

  it("shows your history panel on your own profile once the session is settled", async () => {
    api.fetchProfile.mockResolvedValue(scored({ is_me: true }));
    renderPage("verified", { initial: scored() });
    expect(
      await screen.findByRole("heading", { name: "Your credibility history" }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/^Your score:/)).toBeInTheDocument();
    expect(reputation.fetchMyReputationEvents).toHaveBeenCalled();
  });
});
