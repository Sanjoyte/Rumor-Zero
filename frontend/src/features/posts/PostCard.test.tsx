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

  describe("sources (Part 4)", () => {
    const SOURCES = [
      { value: "10.1038/s41558-024-02102", kind: "doi" as const },
      { value: "https://www.iea.org/reports/renewables-2023", kind: "url" as const },
    ];

    it("shows the first source and '+N more' under a fact claim", () => {
      render(<PostCard {...BASE} sources={SOURCES} />);
      expect(screen.getByText("doi.org/10.1038/s41558-024-02102")).toBeInTheDocument();
      expect(screen.getByText("+1 more")).toBeInTheDocument();
    });

    it("has no source row when a fact has none", () => {
      render(<PostCard {...BASE} sources={[]} />);
      expect(screen.queryByRole("link")).toBeNull();
      expect(screen.queryByText(/more/)).toBeNull();
    });

    it("never shows one on an opinion, even if given sources", () => {
      render(
        <PostCard
          {...BASE}
          postType="opinion"
          status="published"
          verdictSource={null}
          sources={SOURCES}
        />,
      );
      expect(screen.queryByRole("link")).toBeNull();
    });

    it("never shows one on the removed tombstone", () => {
      render(<PostCard {...BASE} status="removed" sources={SOURCES} />);
      expect(screen.queryByRole("link")).toBeNull();
    });

    it("keeps the claim before the sources in reading order", () => {
      render(<PostCard {...BASE} sources={SOURCES} />);
      const claim = screen.getByText(/Solar capacity grew/);
      const link = screen.getByRole("link");
      expect(claim.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
  });

  describe("blank display name", () => {
    it("shows @username once, in bold, with no second handle", () => {
      render(<PostCard {...BASE} author={{ displayName: "", username: "ada" }} />);
      expect(screen.getAllByText("@ada")).toHaveLength(1);
      expect(screen.getByText("@ada")).toHaveClass("font-bold");
    });

    it("treats a whitespace-only display name as blank", () => {
      render(<PostCard {...BASE} author={{ displayName: "  ", username: "ada" }} />);
      expect(screen.getAllByText("@ada")).toHaveLength(1);
    });
  });

  it("lets a long name truncate instead of wrapping (390 px header)", () => {
    render(
      <PostCard
        {...BASE}
        author={{ displayName: "A very long display name indeed", username: "ada" }}
      />,
    );
    expect(screen.getByText("A very long display name indeed")).toHaveClass("truncate");
  });

  describe("the link to the detail page (Part 5)", () => {
    const HREF = "/p/11111111-1111-4111-8111-111111111111";
    const SOURCES = [
      { value: "10.1038/s41558-024-02102", kind: "doi" as const },
      { value: "https://www.iea.org/reports/renewables-2023", kind: "url" as const },
    ];

    it("makes the claim a link, without prefetch, when the card has an address", () => {
      render(<PostCard {...BASE} href={HREF} />);
      const link = screen.getByRole("link", { name: /Solar capacity grew/ });
      expect(link).toHaveAttribute("href", HREF);
      expect(link.className).toContain("after:absolute");
      expect(link.className).toContain("after:inset-0");
    });

    it("stays inert without an address", () => {
      render(<PostCard {...BASE} />);
      expect(screen.queryByRole("link")).toBeNull();
    });

    it("keeps the source links separate, above the card link, and sends '+N more' to #sources", () => {
      render(<PostCard {...BASE} href={HREF} sources={SOURCES} />);
      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(3);
      const source = screen.getByRole("link", { name: /doi\.org\/10\.1038/ });
      expect(source).toHaveAttribute("href", "https://doi.org/10.1038/s41558-024-02102");
      expect(source.className).toContain("z-10");
      const more = screen.getByRole("link", { name: "+1 more" });
      expect(more).toHaveAttribute("href", `${HREF}#sources`);
      expect(more.className).toContain("z-10");
      // No link sits inside another.
      for (const link of links) expect(link.querySelector("a")).toBeNull();
    });

    it("never links the removed tombstone", () => {
      render(<PostCard {...BASE} href={HREF} status="removed" />);
      expect(screen.queryByRole("link")).toBeNull();
    });
  });
});

describe("PostCard author link (Part 6)", () => {
  const WITH_LINK: PostCardProps = {
    ...BASE,
    author: { displayName: "Ada Lovelace", username: "ada", href: "/u/ada" },
    href: "/p/post-1",
  };

  it("links the avatar and name to the profile, without prefetching", () => {
    render(<PostCard {...WITH_LINK} />);
    const link = screen.getByRole("link", { name: /Ada Lovelace/ });
    expect(link).toHaveAttribute("href", "/u/ada");
    expect(link).toHaveTextContent("@ada");
  });

  it("keeps the time and the claim link outside the author link", () => {
    render(<PostCard {...WITH_LINK} />);
    const author = screen.getByRole("link", { name: /Ada Lovelace/ });
    expect(author).not.toContainElement(screen.getByText("3h"));
    const claim = screen.getByRole("link", { name: /Solar capacity grew/ });
    expect(claim).toHaveAttribute("href", "/p/post-1");
    expect(author).not.toContainElement(claim);
  });

  it("sits above the stretched claim link, so the rest of the card still opens the post", () => {
    render(<PostCard {...WITH_LINK} />);
    expect(screen.getByRole("link", { name: /Ada Lovelace/ })).toHaveClass("relative", "z-10");
  });

  it("is plain text without an href (the gallery, previews)", () => {
    render(<PostCard {...BASE} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("shows @username once, as the link, for a blank display name", () => {
    render(
      <PostCard {...WITH_LINK} author={{ displayName: "", username: "ada", href: "/u/ada" }} />,
    );
    expect(screen.getAllByText("@ada")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "@ada" })).toHaveAttribute("href", "/u/ada");
  });

  it("has no author on the removed tombstone, so no profile link", () => {
    render(<PostCard {...WITH_LINK} status="removed" />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});

describe("PostCard action bar (Part 7)", () => {
  it("renders the actions node under the claim and the sources", () => {
    render(
      <PostCard
        {...BASE}
        sources={[{ value: "10.1038/x", kind: "doi" }]}
        actions={<div data-testid="bar">bar</div>}
      />,
    );
    const claim = screen.getByText(/Solar capacity grew/);
    const bar = screen.getByTestId("bar");
    expect(claim.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/10\.1038\/x/).compareDocumentPosition(bar)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("has no bar unless one is given", () => {
    render(<PostCard {...BASE} />);
    expect(screen.queryByTestId("bar")).toBeNull();
  });

  it("never shows the bar on the removed tombstone", () => {
    render(<PostCard {...BASE} status="removed" actions={<div data-testid="bar">bar</div>} />);
    expect(screen.queryByTestId("bar")).toBeNull();
  });

  it("puts a header node first inside the card, before the author row", () => {
    render(<PostCard {...BASE} header={<p>Reposted by Bo</p>} />);
    const card = screen.getByRole("article");
    const header = screen.getByText("Reposted by Bo");
    expect(card).toContainElement(header);
    expect(header.compareDocumentPosition(screen.getByText("Ada Lovelace"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("has no header unless given one", () => {
    render(<PostCard {...BASE} />);
    expect(screen.queryByText(/Reposted by/)).toBeNull();
  });

  it("does not show the header on the removed tombstone", () => {
    render(<PostCard {...BASE} status="removed" header={<p>Reposted by Bo</p>} />);
    expect(screen.queryByText("Reposted by Bo")).toBeNull();
  });
});
