import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UnavailablePostCard } from "./UnavailablePostCard";

const BO = { id: "u2", username: "bo", display_name: "Bo", avatar_url: null };

describe("UnavailablePostCard", () => {
  it("says the post is no longer available and who reposted it", () => {
    render(<UnavailablePostCard reposter={BO} />);
    const card = screen.getByRole("article");
    expect(card).toHaveTextContent("This post is no longer available");
    expect(card).toHaveTextContent("Reposted by");
    expect(screen.getByRole("link", { name: "Bo" })).toHaveAttribute("href", "/u/bo");
  });

  it("has no Undo repost unless the repost is yours", () => {
    render(<UnavailablePostCard reposter={BO} />);
    expect(screen.queryByRole("button", { name: "Undo repost" })).toBeNull();
  });

  it("offers Undo repost when it is yours, and calls back", async () => {
    const onUndo = vi.fn();
    render(<UnavailablePostCard reposter={BO} onUndo={onUndo} />);
    await userEvent.click(screen.getByRole("button", { name: "Undo repost" }));
    expect(onUndo).toHaveBeenCalledTimes(1);
  });

  it("disables the button while undoing", () => {
    render(<UnavailablePostCard reposter={BO} onUndo={() => {}} undoing />);
    expect(screen.getByRole("button", { name: /Undo repost/ })).toBeDisabled();
  });

  it("carries nothing of the original: no text, no actions", () => {
    render(<UnavailablePostCard reposter={BO} onUndo={() => {}} />);
    expect(screen.queryByRole("button", { name: /Like|Repost \d|Bookmark/ })).toBeNull();
  });
});
