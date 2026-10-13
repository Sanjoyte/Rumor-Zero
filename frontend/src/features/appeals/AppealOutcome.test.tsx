import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppealOutcome, appealOutcomeText } from "./AppealOutcome";

const LEAD = "You asked for another look.";

describe("appealOutcomeText", () => {
  it.each([
    [
      { status: "under_review", appeal_status: "open" },
      "A moderator who didn't make the first decision will review it.",
    ],
    [
      { status: "removed", appeal_status: "open" },
      "A moderator who didn't make the first decision will review it.",
    ],
    [
      { status: "removed", appeal_status: "upheld" },
      "A moderator reviewed it, and the post stays removed.",
    ],
    [
      { status: "verified_false", appeal_status: "upheld" },
      "A moderator reviewed it, and the FALSE label stays.",
    ],
    [
      { status: "verified_true", appeal_status: "upheld" },
      "A moderator reviewed it, and the decision stands.",
    ],
    [
      { status: "verified_true", appeal_status: "overturned" },
      "A moderator reversed the decision.",
    ],
    [{ status: "published", appeal_status: "overturned" }, "A moderator reversed the decision."],
    [
      { status: "verified_false", appeal_status: "overturned" },
      "A moderator reversed the decision.",
    ],
  ] as const)("%j", (post, rest) => {
    expect(appealOutcomeText(post)).toBe(`${LEAD} ${rest}`);
  });

  it("is null when there is no appeal", () => {
    expect(appealOutcomeText({ status: "verified_false", appeal_status: null })).toBeNull();
  });
});

describe("AppealOutcome", () => {
  it("renders the sentence with the gavel", () => {
    render(<AppealOutcome post={{ status: "removed", appeal_status: "upheld" }} />);
    expect(screen.getByText(/the post stays removed/)).toBeInTheDocument();
    expect(document.querySelector("[aria-hidden='true']")).toHaveTextContent("gavel");
  });

  it("renders nothing without an appeal", () => {
    const { container } = render(
      <AppealOutcome post={{ status: "verified_false", appeal_status: null }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
