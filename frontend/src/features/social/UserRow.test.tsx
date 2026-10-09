import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithComposer } from "@/features/posts/test-helpers";
import { makeRow } from "./test-helpers";
import { UserRow } from "./UserRow";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/u/bob",
}));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
}));

describe("UserRow", () => {
  it("shows the name, the handle, the bio and a Follow button; the name links to the profile", async () => {
    renderWithComposer(<UserRow user={makeRow({ bio: "Hello\nthere" })} />);
    const link = screen.getByRole("link", { name: /Cy Lane/ });
    expect(link).toHaveAttribute("href", "/u/cy");
    expect(screen.getByText("@cy")).toBeInTheDocument();
    expect(screen.getByText(/Hello\s+there/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Follow" })).toBeInTheDocument();
  });

  it("shows @username once when the display name is blank", () => {
    renderWithComposer(<UserRow user={makeRow({ display_name: "  " })} />);
    expect(screen.getAllByText("@cy")).toHaveLength(1);
  });

  it("starts as Following when the viewer already follows", async () => {
    renderWithComposer(<UserRow user={makeRow({ is_following: true })} />);
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
  });

  it("has no button on your own row", async () => {
    renderWithComposer(<UserRow user={makeRow({ is_me: true })} />);
    await screen.findByRole("article");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("has no bio line without a bio", () => {
    const { container } = renderWithComposer(<UserRow user={makeRow({ bio: "" })} />);
    expect(container.querySelector("p")).toBeNull();
  });

  it("renders a bio as text, never as markup", () => {
    renderWithComposer(<UserRow user={makeRow({ bio: "<b>bold</b>" })} />);
    expect(screen.getByText("<b>bold</b>")).toBeInTheDocument();
  });
});
