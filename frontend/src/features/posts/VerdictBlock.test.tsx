import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { explain, VerdictBlock } from "./VerdictBlock";
import { makePost } from "./test-helpers";

const fact = (overrides = {}) => makePost({ post_type: "fact", is_mine: false, ...overrides });

describe("VerdictBlock", () => {
  it("has no block for a published opinion, only a neutral line", () => {
    render(<VerdictBlock post={makePost()} />);
    expect(screen.getByText("Opinions aren't fact-checked.")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).toBeNull();
  });

  it("explains a pending fact and says it updates by itself", () => {
    render(<VerdictBlock post={fact({ status: "pending" })} />);
    expect(screen.getByRole("heading", { name: "Verdict" })).toBeInTheDocument();
    expect(screen.getByText("Checking facts…")).toBeInTheDocument();
    expect(screen.getByText(/updates on its own/)).toBeInTheDocument();
  });

  it("says 'Checked automatically · 94% confidence' for a pipeline verdict", () => {
    render(
      <VerdictBlock
        post={fact({
          status: "verified_true",
          verdict_source: "pipeline",
          confidence_score: "94.00",
        })}
      />,
    );
    expect(screen.getByText("Checked automatically · 94% confidence")).toBeInTheDocument();
    expect(screen.getByText("This claim was found to be true.")).toBeInTheDocument();
  });

  it("says FALSE, never debunked", () => {
    render(
      <VerdictBlock
        post={fact({
          status: "verified_false",
          verdict_source: "pipeline",
          confidence_score: "88.00",
        })}
      />,
    );
    expect(screen.getByText("This claim was found to be FALSE.")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/debunk/i);
  });

  it("says 'Reviewed by a moderator' with the moderator's note, and no percentage", () => {
    render(
      <VerdictBlock
        post={fact({
          status: "verified_false",
          verdict_source: "moderator",
          confidence_score: null,
          verdict_note: "The cited report says the opposite.",
        })}
      />,
    );
    expect(screen.getByText("Reviewed by a moderator")).toBeInTheDocument();
    expect(screen.getByText(/The cited report says the opposite\./)).toBeInTheDocument();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("shows a note only on a moderator's verdict", () => {
    render(
      <VerdictBlock
        post={fact({ status: "verified_true", verdict_source: "pipeline", verdict_note: "stray" })}
      />,
    );
    expect(screen.queryByText(/stray/)).toBeNull();
  });

  it("has no verdict for a removed post: the page's banner says it was removed", () => {
    const { container } = render(
      <VerdictBlock post={fact({ status: "removed", is_mine: true })} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("explains under review, for a fact and for an opinion", () => {
    const { rerender } = render(<VerdictBlock post={fact({ status: "under_review" })} />);
    expect(screen.getByText("Under review")).toBeInTheDocument();
    rerender(<VerdictBlock post={makePost({ status: "under_review" })} />);
    expect(screen.getByText("Under review")).toBeInTheDocument();
    expect(screen.queryByText("Opinions aren't fact-checked.")).toBeNull();
  });

  it("explain() copes with a verified post that has no confidence", () => {
    expect(
      explain({ status: "verified_true", verdict_source: "pipeline", confidence_score: null })
        .title,
    ).toBe("Checked automatically");
    expect(
      explain({ status: "verified_true", verdict_source: null, confidence_score: null }).title,
    ).toBe("Verified");
  });
});

// Part 9: the exact objects the API sends once the stub pipeline has answered (`#true`, `#false`,
// `#unsure`), and a post under review whose late verdict the API keeps private.
describe("VerdictBlock with the pipeline's real answers", () => {
  const cases: [string, Parameters<typeof fact>[0], string, string][] = [
    [
      "#true",
      { status: "verified_true", verdict_source: "pipeline", confidence_score: "95.00" },
      "Checked automatically · 95% confidence",
      "This claim was found to be true.",
    ],
    [
      "#false",
      { status: "verified_false", verdict_source: "pipeline", confidence_score: "92.00" },
      "Checked automatically · 92% confidence",
      "This claim was found to be FALSE.",
    ],
    [
      "#unsure",
      { status: "under_review", verdict_source: null, confidence_score: null },
      "Under review",
      "A moderator is taking a look at this post. The label changes once they decide.",
    ],
  ];

  it.each(cases)("%s", (_tag, post, title, body) => {
    render(<VerdictBlock post={fact(post)} />);
    expect(screen.getByText(title)).toBeInTheDocument();
    expect(screen.getByText(body)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/debunk/i);
  });

  it("shows no percentage while a post is under review", () => {
    render(<VerdictBlock post={fact({ status: "under_review" })} />);
    expect(screen.queryByText(/%/)).toBeNull();
  });
});
