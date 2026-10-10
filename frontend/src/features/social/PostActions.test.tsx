import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makePost, renderWithSessionAndToast } from "@/features/posts/test-helpers";
import { PostActions } from "./PostActions";

vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  likePost: vi.fn(),
  unlikePost: vi.fn(),
  repostPost: vi.fn(),
  unrepostPost: vi.fn(),
  bookmarkPost: vi.fn(),
  unbookmarkPost: vi.fn(),
}));

const post = makePost({
  id: "p1",
  is_mine: false,
  like_count: 2,
  comment_count: 5,
  repost_count: 4,
});

describe("PostActions", () => {
  it("on a card: like, a comment link to the discussion, repost, and the bookmark", async () => {
    const { container } = renderWithSessionAndToast(<PostActions post={post} />);
    expect(await screen.findByRole("button", { name: "Like 2" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 5" })).toHaveAttribute(
      "href",
      "/p/p1#comments",
    );
    expect(screen.getByRole("button", { name: "Repost 4" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bookmark" })).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("border-t", "justify-between");
  });

  it("puts the bookmark at the right of the bar, apart from the counters", async () => {
    const { container } = renderWithSessionAndToast(<PostActions post={post} />);
    await screen.findByRole("button", { name: "Bookmark" });
    const bar = container.firstChild as HTMLElement;
    expect(bar.children).toHaveLength(2);
    expect(bar.children[0]).toContainElement(screen.getByRole("button", { name: "Repost 4" }));
    expect(bar.children[1]).toBe(screen.getByRole("button", { name: "Bookmark" }));
  });

  it("on the post page: one row, with words, and the link jumps to the section below", async () => {
    const { container } = renderWithSessionAndToast(<PostActions post={post} variant="detail" />);
    expect(await screen.findByRole("link", { name: "Comments 5" })).toHaveAttribute(
      "href",
      "#comments",
    );
    expect(screen.getByText("Comments", { selector: "[aria-hidden]" })).toHaveClass("sm:inline");
    expect(screen.getByText("Repost", { selector: "[aria-hidden]" })).toHaveClass("sm:inline");
    expect(screen.getByRole("button", { name: "Bookmark" })).toBeInTheDocument();
    expect(container.firstChild).not.toHaveClass("border-t");
  });

  it("puts its buttons above the card's stretched link", async () => {
    renderWithSessionAndToast(<PostActions post={post} />);
    for (const name of ["Like 2", "Repost 4", "Bookmark"]) {
      expect(await screen.findByRole("button", { name })).toHaveClass("z-10");
    }
    expect(screen.getByRole("link", { name: "Comments 5" })).toHaveClass("z-10");
  });

  it("prints big counts compactly and zero as 0", async () => {
    renderWithSessionAndToast(
      <PostActions post={{ ...post, like_count: 0, comment_count: 1200, repost_count: 1500 }} />,
    );
    expect(await screen.findByRole("button", { name: "Like 0" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 1.2K" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repost 1.5K" })).toBeInTheDocument();
  });

  it("reflects what the viewer already did", async () => {
    renderWithSessionAndToast(
      <PostActions
        post={{ ...post, liked_by_me: true, reposted_by_me: true, bookmarked_by_me: true }}
      />,
    );
    for (const name of ["Like 2", "Repost 4", "Bookmark"]) {
      expect(await screen.findByRole("button", { name })).toHaveAttribute("aria-pressed", "true");
    }
  });

  it.each([
    ["your own post", { is_mine: true }, "You can't repost your own post."],
    [
      "a FALSE post",
      { status: "verified_false" as const },
      "Posts labelled FALSE can't be reposted.",
    ],
    ["a removed post", { status: "removed" as const }, "Removed posts can't be reposted."],
  ])("disables Repost with the reason for %s", async (_, change, reason) => {
    renderWithSessionAndToast(<PostActions post={{ ...post, ...change }} />);
    const button = await screen.findByRole("button", { name: "Repost 4" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription(reason);
  });

  it("still lets you undo a repost of a post that has since turned FALSE", async () => {
    renderWithSessionAndToast(
      <PostActions post={{ ...post, status: "verified_false", reposted_by_me: true }} />,
    );
    const button = await screen.findByRole("button", { name: "Repost 4" });
    expect(button).not.toHaveAttribute("aria-disabled");
  });

  it("acts on the post id it was given, which for a repost item is the original", async () => {
    const { repostPost } = await import("./social-api");
    renderWithSessionAndToast(<PostActions post={post} />);
    const button = await screen.findByRole("button", { name: "Repost 4" });
    button.click();
    expect(repostPost).toHaveBeenCalledWith("p1");
  });
});
