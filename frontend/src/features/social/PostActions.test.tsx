import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast } from "@/features/posts/test-helpers";
import { PostActions } from "./PostActions";

vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  likePost: vi.fn(),
  unlikePost: vi.fn(),
}));

const props = { postId: "p1", liked: false, likeCount: 2, commentCount: 5 };

describe("PostActions", () => {
  it("on a card: a like button, and a comment link to the post's discussion", async () => {
    const { container } = renderWithSessionAndToast(<PostActions {...props} />);
    expect(await screen.findByRole("button", { name: "Like 2" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 5" })).toHaveAttribute(
      "href",
      "/p/p1#comments",
    );
    expect(container.firstChild).toHaveClass("border-t");
  });

  it("on the post page: the same links jump to the section below, with words", async () => {
    const { container } = renderWithSessionAndToast(<PostActions {...props} variant="detail" />);
    expect(await screen.findByRole("link", { name: "Comments 5" })).toHaveAttribute(
      "href",
      "#comments",
    );
    expect(screen.getByText("Comments", { selector: "[aria-hidden]" })).toHaveClass("sm:inline");
    expect(container.firstChild).not.toHaveClass("border-t");
  });

  it("puts its buttons above the card's stretched link", async () => {
    renderWithSessionAndToast(<PostActions {...props} />);
    expect(await screen.findByRole("button", { name: "Like 2" })).toHaveClass("z-10");
    expect(screen.getByRole("link", { name: "Comments 5" })).toHaveClass("z-10");
  });

  it("prints big counts compactly and zero as 0", async () => {
    renderWithSessionAndToast(<PostActions {...props} likeCount={0} commentCount={1200} />);
    expect(await screen.findByRole("button", { name: "Like 0" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 1.2K" })).toBeInTheDocument();
  });
});
