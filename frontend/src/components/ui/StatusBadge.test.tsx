import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PostDisplayInput } from "@/lib/post-display";
import { CategoryChip } from "./CategoryChip";
import { AppealPendingBadge, EmergencyBadge, StatusBadge } from "./StatusBadge";

// One row per line of the ARCHITECTURE section 4 badge table.
const ROWS: {
  name: string;
  input?: PostDisplayInput;
  label: string | null;
  glyph?: string;
  tone?: string;
}[] = [
  {
    name: "pending",
    input: { status: "pending" },
    label: "CHECKING FACTS…",
    glyph: "progress_activity",
    tone: "border-dashed",
  },
  { name: "published opinion", input: { status: "published" }, label: null },
  {
    name: "verified_true, pipeline",
    input: { status: "verified_true", verdictSource: "pipeline", confidenceScore: "94.00" },
    label: "VERIFIED 94%",
    glyph: "check_circle",
    tone: "text-primary",
  },
  {
    name: "verified_true, moderator",
    input: { status: "verified_true", verdictSource: "moderator" },
    label: "VERIFIED · REVIEWED",
    glyph: "check_circle",
    tone: "text-primary",
  },
  {
    name: "verified_false, pipeline",
    input: { status: "verified_false", verdictSource: "pipeline", confidenceScore: "88.00" },
    label: "FALSE 88%",
    glyph: "cancel",
    tone: "text-error",
  },
  {
    name: "verified_false, moderator",
    input: { status: "verified_false", verdictSource: "moderator" },
    label: "FALSE · REVIEWED",
    glyph: "cancel",
    tone: "text-error",
  },
  {
    name: "under_review",
    input: { status: "under_review" },
    label: "UNDER REVIEW",
    glyph: "hourglass_top",
    tone: "text-on-verdict-review",
  },
  {
    name: "removed",
    input: { status: "removed" },
    label: "REMOVED",
    glyph: "block",
    tone: "text-outline",
  },
];

describe("StatusBadge", () => {
  it.each(ROWS)("$name", ({ input, label, glyph, tone }) => {
    const { container } = render(<StatusBadge {...input!} />);
    if (label === null) {
      expect(container).toBeEmptyDOMElement();
      return;
    }
    const badge = screen.getByText(label, { exact: false }).closest("span.inline-flex");
    expect(badge).toHaveTextContent(label);
    expect(screen.getByText(glyph!)).toHaveAttribute("aria-hidden", "true");
    expect(badge).toHaveClass(tone!, "rounded-lg", "border", "uppercase");
  });

  it("spins the pending glyph, but stands still for reduced motion", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText("progress_activity")).toHaveClass(
      "animate-spin",
      "motion-reduce:animate-none",
    );
  });

  it("never says debunked, and always spells out FALSE", () => {
    render(
      <>
        <StatusBadge status="verified_false" verdictSource="pipeline" confidenceScore="70" />
        <StatusBadge status="verified_false" verdictSource="moderator" />
      </>,
    );
    expect(document.body.textContent).not.toMatch(/debunk/i);
    expect(screen.getAllByText(/^FALSE/)).toHaveLength(2);
  });

  it("shows a percentage only for pipeline verdicts that have a score", () => {
    const { rerender } = render(<StatusBadge status="verified_true" verdictSource="pipeline" />);
    expect(screen.getByText("VERIFIED")).toBeInTheDocument();
    rerender(<StatusBadge status="verified_true" verdictSource="moderator" confidenceScore="99" />);
    expect(screen.queryByText(/%/)).toBeNull();
  });
});

describe("EmergencyBadge", () => {
  it("is the violet EMERGENCY chip with a solid bolt", () => {
    render(<EmergencyBadge />);
    const chip = screen.getByText("EMERGENCY").closest("span.inline-flex");
    expect(chip).toHaveClass("text-tertiary", "bg-tertiary/10", "border-tertiary/30");
    expect(screen.getByText("bolt")).toHaveClass("[font-variation-settings:'FILL'_1]");
  });
});

describe("AppealPendingBadge", () => {
  it("is the amber APPEAL PENDING chip", () => {
    render(<AppealPendingBadge />);
    expect(screen.getByText("APPEAL PENDING").closest("span.inline-flex")).toHaveClass(
      "text-on-verdict-review",
    );
  });
});

describe("CategoryChip (the OPINION row of the badge table)", () => {
  it("shows OPINION with no glyph, in neutral colours", () => {
    const { container } = render(<CategoryChip type="opinion" />);
    const chip = screen.getByText("OPINION");
    expect(chip).toHaveClass(
      "text-outline",
      "bg-surface-container-low",
      "border-outline-variant/30",
    );
    expect(container.querySelector(".material-symbols-outlined")).toBeNull();
  });

  it("shows FACT", () => {
    render(<CategoryChip type="fact" />);
    expect(screen.getByText("FACT")).toBeInTheDocument();
  });
});
