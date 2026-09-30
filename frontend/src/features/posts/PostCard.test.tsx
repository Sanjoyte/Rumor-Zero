import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PostCard, type PostCardProps } from "./PostCard";

const NOW = new Date("2026-09-30T12:00:00Z");

const BASE: PostCardProps = {
  author: { displayName: "Ada Lovelace", username: "ada" },
  content: "Solar capacity grew 30% last year.",
  postType: "fact",
  status: "verified_true",
  verdictSource: "pipeline",
  confidenceScore: "94.00",
  createdAt: "2026-09-30T09:00:00Z",
  now: NOW,
};

const stripe = (container: HTMLElement) => container.querySelector("[data-tone]");

describe("PostCard", () => {
  it("shows the author, handle and relative time", () => {
    render(<PostCard {...BASE} />);
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("@ada")).toBeInTheDocument();
    expect(screen.getByText("3h")).toHaveAttribute("datetime", "2026-09-30T09:00:00Z");
  });

  it("quotes a fact in upright serif claim text", () => {
    render(<PostCard {...BASE} />);
    const claim = screen.getByText(/Solar capacity grew/);
    expect(claim.tagName).toBe("BLOCKQUOTE");
    expect(claim).toHaveTextContent("\u201CSolar capacity grew 30% last year.\u201D");
    expect(claim).toHaveClass("font-claim-headline", "text-claim-headline");
    expect(claim).not.toHaveClass("italic");
  });

  it("sets an opinion in italic serif with the opinion tokens", () => {
    render(<PostCard {...BASE} postType="opinion" status="published" verdictSource={null} />);
    const claim = screen.getByText(/Solar capacity grew/);
    expect(claim).toHaveClass("font-claim-opinion", "text-claim-opinion", "italic");
    expect(screen.getByText("OPINION")).toBeInTheDocument();
  });

  it("keeps the plain-text whitespace and never renders markup", () => {
    const { container } = render(<PostCard {...BASE} content={"line one\n<b>not bold</b>"} />);
    expect(screen.getByText(/line one/)).toHaveClass("whitespace-pre-wrap", "break-words");
    expect(container.querySelector("b")).toBeNull();
  });

  it("shows the category chip and a status stripe for a verified fact", () => {
    const { container } = render(<PostCard {...BASE} />);
    expect(screen.getByText("FACT")).toBeInTheDocument();
    expect(screen.getByText("VERIFIED 94%")).toBeInTheDocument();
    expect(stripe(container)).toHaveAttribute("data-tone", "primary");
    expect(screen.queryByText("EMERGENCY")).toBeNull();
  });

  it.each([
    ["verified_false", "error", "FALSE 94%"],
    ["under_review", "verdict-review", "UNDER REVIEW"],
    ["pending", "outline-variant", "CHECKING FACTS…"],
  ] as const)("uses the %s colour when there is no emergency", (status, tone, label) => {
    const { container } = render(<PostCard {...BASE} status={status} />);
    expect(stripe(container)).toHaveAttribute("data-tone", tone);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("shows the violet stripe and the EMERGENCY chip while an emergency is active", () => {
    const { container } = render(<PostCard {...BASE} status="pending" emergencyActive />);
    expect(stripe(container)).toHaveAttribute("data-tone", "tertiary");
    expect(screen.getByText("EMERGENCY")).toBeInTheDocument();
    expect(screen.getByText("CHECKING FACTS…")).toBeInTheDocument();
  });

  it("puts the EMERGENCY chip next to the status badge for any live status", () => {
    const { container } = render(<PostCard {...BASE} status="verified_true" emergencyActive />);
    expect(stripe(container)).toHaveAttribute("data-tone", "tertiary");
    expect(screen.getByText(/VERIFIED/)).toBeInTheDocument();
    expect(screen.getByText("EMERGENCY")).toBeInTheDocument();
  });

  it("goes back to the status colour once the emergency is over", () => {
    const { container } = render(<PostCard {...BASE} emergencyActive={false} />);
    expect(stripe(container)).toHaveAttribute("data-tone", "primary");
    expect(screen.queryByText("EMERGENCY")).toBeNull();
  });

  it("shows the appeal chip to the author while an appeal is open", () => {
    render(<PostCard {...BASE} status="under_review" appealPending />);
    expect(screen.getByText("UNDER REVIEW")).toBeInTheDocument();
    expect(screen.getByText("APPEAL PENDING")).toBeInTheDocument();
  });

  it("renders a removed post as a tombstone without text, stripe or badges", () => {
    const { container } = render(<PostCard {...BASE} status="removed" emergencyActive />);
    expect(screen.getByText("Removed by a moderator")).toBeInTheDocument();
    expect(screen.queryByText(/Solar capacity grew/)).toBeNull();
    expect(stripe(container)).toBeNull();
    expect(screen.queryByText("EMERGENCY")).toBeNull();
    expect(screen.queryByText("FACT")).toBeNull();
  });

  it("falls back to initials for the author, and shows a photo when there is one", () => {
    const { rerender } = render(<PostCard {...BASE} />);
    expect(screen.getByText("AL")).toBeInTheDocument();
    rerender(
      <PostCard {...BASE} author={{ ...BASE.author, avatarUrl: "/api/v1/avatars/x/1-96.webp" }} />,
    );
    expect(document.querySelector("img")).toHaveAttribute("src", "/api/v1/avatars/x/1-96.webp");
  });

  it("never says debunked", () => {
    render(<PostCard {...BASE} status="verified_false" />);
    expect(document.body.textContent).not.toMatch(/debunk/i);
  });
});
