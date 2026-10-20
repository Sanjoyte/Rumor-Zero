import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmergencyNote } from "./EmergencyNote";
import { makePost } from "./test-helpers";

const emergency = (overrides: Parameters<typeof makePost>[0] = {}) =>
  makePost({
    post_type: "fact",
    status: "verified_true",
    is_emergency: true,
    emergency_active: false,
    created_at: "2026-10-19T08:00:00Z",
    ...overrides,
  });

describe("EmergencyNote", () => {
  it("says the priority ended once an emergency expired", () => {
    render(<EmergencyNote post={emergency()} />);
    expect(
      screen.getByText("Posted as an emergency on Oct 19, 2026. Priority ended."),
    ).toBeInTheDocument();
  });

  it("says a moderator removed the priority after a demotion", () => {
    render(<EmergencyNote post={emergency({ emergency_demoted: true })} />);
    expect(
      screen.getByText("Posted as an emergency on Oct 19, 2026. Priority removed by a moderator."),
    ).toBeInTheDocument();
  });

  it("appears at once when the poll finds the emergency FALSE", () => {
    render(
      <EmergencyNote post={emergency({ status: "verified_false", emergency_active: true })} />,
    );
    expect(screen.getByText(/Priority ended\./)).toBeInTheDocument();
  });

  it("is absent while the emergency is still pinned, for a plain post, and on a removed one", () => {
    const { container, rerender } = render(
      <EmergencyNote post={emergency({ emergency_active: true })} />,
    );
    expect(container).toBeEmptyDOMElement();
    rerender(<EmergencyNote post={makePost()} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<EmergencyNote post={emergency({ status: "removed" })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is neutral, never violet", () => {
    const { container } = render(<EmergencyNote post={emergency()} />);
    expect(container.innerHTML).not.toMatch(/tertiary/);
  });
});
