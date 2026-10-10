import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CommentItem } from "./CommentItem";
import { makeComment } from "./test-helpers";

const NOW = new Date("2026-10-08T12:00:00Z");

describe("CommentItem", () => {
  it("shows the author, handle, relative time and text", () => {
    render(<CommentItem comment={makeComment()} now={NOW} />);
    expect(screen.getByText("Cy Lane")).toBeInTheDocument();
    expect(screen.getByText("@cy")).toBeInTheDocument();
    const time = screen.getByText("1h");
    expect(time).toHaveAttribute("dateTime", "2026-10-08T11:00:00Z");
    expect(time).toHaveAttribute("title", "Oct 8, 2026, 11:00 AM UTC");
    expect(screen.getByText("A fair point.")).toBeInTheDocument();
  });

  it("links the author to their profile", () => {
    render(<CommentItem comment={makeComment()} now={NOW} />);
    expect(screen.getByRole("link", { name: /Cy Lane/ })).toHaveAttribute("href", "/u/cy");
  });

  it("shows @username once when the display name is blank", () => {
    const author = { id: "u-3", username: "cy", display_name: "", avatar_url: null };
    render(<CommentItem comment={makeComment({ author })} now={NOW} />);
    expect(screen.getAllByText("@cy")).toHaveLength(1);
  });

  it("keeps line breaks and never turns text into HTML", () => {
    const content = "line one\nline two <b>not bold</b> <script>x()</script>";
    const { container } = render(<CommentItem comment={makeComment({ content })} now={NOW} />);
    const body = screen.getByText(/line one/);
    expect(body).toHaveClass("whitespace-pre-wrap");
    expect(body.textContent).toBe(content);
    expect(container.querySelector("b, script")).toBeNull();
  });

  it("has a Delete button only on your own comment", async () => {
    const onDelete = vi.fn();
    const mine = makeComment({ is_mine: true });
    const { rerender } = render(<CommentItem comment={mine} onDelete={onDelete} now={NOW} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith(mine);
    rerender(<CommentItem comment={makeComment()} onDelete={onDelete} now={NOW} />);
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });

  it("has no Delete without a handler, even on your own comment", () => {
    render(<CommentItem comment={makeComment({ is_mine: true })} now={NOW} />);
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });
});
