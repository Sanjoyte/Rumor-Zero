import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithComposer, type SessionKind } from "@/features/posts/test-helpers";
import { ProfileHeader } from "./ProfileHeader";
import { makeProfile } from "./test-helpers";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/u/bob",
}));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
}));

function renderHeader(
  profile = makeProfile(),
  { viewerReady = true, kind = "verified" as SessionKind } = {},
) {
  const onFollowChange = vi.fn();
  renderWithComposer(
    <ProfileHeader profile={profile} viewerReady={viewerReady} onFollowChange={onFollowChange} />,
    kind,
  );
  return { onFollowChange };
}

describe("ProfileHeader", () => {
  it("shows the name as the one h1, the handle, the bio, the join month and the post count", () => {
    renderHeader();
    expect(screen.getByRole("heading", { level: 1, name: "Bob Stone" })).toBeInTheDocument();
    expect(screen.getByText("@bob")).toBeInTheDocument();
    expect(screen.getByText("Counting things.")).toBeInTheDocument();
    expect(screen.getByText("Joined March 2024")).toBeInTheDocument();
    expect(screen.getByText("42 posts")).toBeInTheDocument();
  });

  it("shows the credibility score in the meta row, with how it is calculated", () => {
    renderHeader(makeProfile({ reputation: { score: 72, sample: 23 } }));
    const region = screen.getByRole("region", { name: "Profile" });
    expect(within(region).getByText("Credibility 72")).toBeInTheDocument();
    expect(within(region).getByRole("link", { name: "How this is calculated" })).toHaveAttribute(
      "href",
      "/how-it-works#credibility",
    );
  });

  it("says Credibility: New while fewer than three events count", () => {
    renderHeader(makeProfile({ reputation: { score: null, sample: 2 } }));
    expect(screen.getByText(/^Credibility: New/)).toBeInTheDocument();
  });

  it("says '1 post' for one", () => {
    renderHeader(makeProfile({ counts: { ...makeProfile().counts, posts: 1 } }));
    expect(screen.getByText("1 post")).toBeInTheDocument();
  });

  it("shows @username once, as the heading, when the display name is blank", () => {
    renderHeader(makeProfile({ display_name: "" }));
    expect(screen.getByRole("heading", { level: 1, name: "@bob" })).toBeInTheDocument();
    expect(screen.getAllByText("@bob")).toHaveLength(1);
  });

  it("prints the counters in full with a separator, labelled Verified and FALSE (never 'debunked')", () => {
    renderHeader();
    const region = screen.getByRole("region", { name: "Profile" });
    expect(within(region).getByText("1,420")).toBeInTheDocument();
    expect(within(region).getByText("186")).toBeInTheDocument();
    expect(within(region).getByText("68")).toBeInTheDocument();
    for (const label of ["Followers", "Following", "Verified", "FALSE"]) {
      expect(within(region).getByText(label)).toBeInTheDocument();
    }
    expect(region.textContent?.toLowerCase()).not.toContain("debunk");
  });

  it("links the two network counters to their lists", () => {
    renderHeader();
    expect(screen.getByRole("link", { name: /1,420\s*Followers/ })).toHaveAttribute(
      "href",
      "/u/bob/followers",
    );
    expect(screen.getByRole("link", { name: /186\s*Following/ })).toHaveAttribute(
      "href",
      "/u/bob/following",
    );
  });

  it("offers Follow to someone else, and passes the change on", async () => {
    renderHeader(makeProfile({ is_following: true }));
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
  });

  it("shows Edit profile, linking to /settings, on your own profile (no Follow button)", () => {
    renderHeader(makeProfile({ is_me: true }));
    expect(screen.getByRole("link", { name: /Edit profile/ })).toHaveAttribute("href", "/settings");
    expect(screen.queryByRole("button", { name: /Follow/ })).not.toBeInTheDocument();
  });

  it("shows a placeholder, not a button, until the viewer's own view is in", () => {
    renderHeader(makeProfile(), { viewerReady: false });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Edit profile/ })).not.toBeInTheDocument();
  });

  it("renders the bio as text only", () => {
    renderHeader(makeProfile({ bio: "<img src=x onerror=alert(1)>" }));
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("leaves out the bio paragraph when there is no bio", () => {
    renderHeader(makeProfile({ bio: "" }));
    expect(screen.queryByText("Counting things.")).not.toBeInTheDocument();
  });

  it("shows the photo when there is one, initials otherwise", () => {
    renderHeader(makeProfile({ avatar_url: null }));
    expect(screen.getByText("BS")).toBeInTheDocument();
  });
});
