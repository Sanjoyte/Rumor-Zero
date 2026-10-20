import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SearchBar } from "./SearchBar";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/search",
}));

const field = () => screen.getByRole("textbox", { name: "Search query" });

describe("SearchBar", () => {
  it("is a named search form with the query in an editable field", () => {
    render(<SearchBar q="storm" type="posts" filter="all" />);
    expect(screen.getByRole("search", { name: "Search results" })).toHaveAttribute(
      "action",
      "/search",
    );
    expect(field()).toHaveValue("storm");
    expect(field()).toHaveAttribute("name", "q");
    expect(field()).toHaveAttribute("maxlength", "200");
  });

  it("carries the tab and the chip only when they aren't the default", () => {
    const plain = render(<SearchBar q="x" type="posts" filter="all" />);
    expect(plain.container.querySelectorAll("input[type=hidden]")).toHaveLength(0);
    plain.unmount();
    const people = render(<SearchBar q="x" type="users" filter="all" />);
    expect(people.container.querySelector("input[name=type]")).toHaveValue("users");
    expect(people.container.querySelector("input[name=filter]")).toBeNull();
    people.unmount();
    const chip = render(<SearchBar q="x" type="posts" filter="false" />);
    expect(chip.container.querySelector("input[name=filter]")).toHaveValue("false");
    expect(chip.container.querySelector("input[name=type]")).toBeNull();
  });

  it("clears the field and focuses it, and hides the button when the field is empty", async () => {
    render(<SearchBar q="storm" type="posts" filter="all" />);
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(field()).toHaveValue("");
    expect(field()).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
    await userEvent.type(field(), "a");
    expect(screen.getByRole("button", { name: "Clear search" })).toBeInTheDocument();
  });

  it("shows a new query when the address brings one", () => {
    const view = render(<SearchBar q="one" type="posts" filter="all" />);
    view.rerender(<SearchBar q="two" type="posts" filter="all" />);
    expect(field()).toHaveValue("two");
  });

  it("keeps what is typed while the address is unchanged", async () => {
    const view = render(<SearchBar q="one" type="posts" filter="all" />);
    await userEvent.type(field(), " more");
    view.rerender(<SearchBar q="one" type="posts" filter="false" />);
    expect(field()).toHaveValue("one more");
  });
});
