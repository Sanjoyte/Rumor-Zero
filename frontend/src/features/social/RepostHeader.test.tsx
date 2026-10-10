import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RepostHeader } from "./RepostHeader";

const BO = { id: "u2", username: "bo", display_name: "Bo Stone", avatar_url: null };

describe("RepostHeader", () => {
  it("says who reposted, with a link to their profile", () => {
    render(<RepostHeader user={BO} />);
    expect(screen.getByText("Reposted by")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bo Stone" })).toHaveAttribute("href", "/u/bo");
  });

  it("uses @username when the display name is blank", () => {
    render(<RepostHeader user={{ ...BO, display_name: "  " }} />);
    expect(screen.getByRole("link", { name: "@bo" })).toHaveAttribute("href", "/u/bo");
  });

  it("sits above the card's stretched claim link", () => {
    const { container } = render(<RepostHeader user={BO} />);
    expect(container.firstChild).toHaveClass("relative", "z-10");
  });

  it("renders a name as plain text, never as markup", () => {
    const { container } = render(<RepostHeader user={{ ...BO, display_name: "<b>x</b>" }} />);
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByRole("link")).toHaveTextContent("<b>x</b>");
  });
});
