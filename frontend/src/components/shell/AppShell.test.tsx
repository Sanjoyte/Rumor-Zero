import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";
import type { ShellUser } from "./nav-items";

let pathname = "/home";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

const user: ShellUser = {
  username: "ada",
  display_name: "Ada Lovelace",
  avatar_url: null,
  is_email_verified: true,
};
const staff: ShellUser = { ...user, admin_url: "https://api.example.test/secret-admin/" };

function renderShell(props: {
  user: ShellUser | null;
  status?: "loading" | "anonymous" | "authenticated";
  onNewPost?: () => void;
  onLogout?: () => void;
}) {
  render(
    <AppShell {...props}>
      <p>Page content</p>
    </AppShell>,
  );
  const sidebar = screen.getByRole("complementary");
  const [railNav, bottomNav] = screen.getAllByRole("navigation", { name: "Main" });
  return { sidebar, railNav, bottomNav };
}

/** Text a reader gets: icon glyph names are aria-hidden, so they are left out. */
function textOf(element: Element): string {
  const copy = element.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((node) => node.remove());
  return (copy.textContent ?? "").trim();
}

/** Logos are told apart by size: wordmark md is 36px tall and wide, the mark is square. */
function logos(container: HTMLElement) {
  return within(container)
    .getAllByRole("img", { name: "Rumor Zero" })
    .map((img) => ({
      height: Number(img.getAttribute("height")),
      width: Number(img.getAttribute("width")),
    }));
}

beforeEach(() => {
  pathname = "/home";
});

describe("AppShell, logged in", () => {
  it("lists the rail items and marks the current page", () => {
    const { railNav } = renderShell({ user });
    const names = within(railNav).getAllByRole("link").map(textOf);
    expect(names).toEqual(["Home", "Search", "Notifications", "Profile", "Bookmarks"]);
    expect(within(railNav).getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(railNav).getByRole("link", { name: "Search" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(within(railNav).getByRole("link", { name: "Profile" })).toHaveAttribute(
      "href",
      "/u/ada",
    );
  });

  it("keeps Profile active on nested pages", () => {
    pathname = "/u/ada/followers";
    const { railNav, bottomNav } = renderShell({ user });
    expect(within(railNav).getByRole("link", { name: "Profile" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(bottomNav).getByRole("link", { name: "Profile" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(railNav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("has New post in the rail and the bottom bar", async () => {
    const onNewPost = vi.fn();
    const { sidebar, bottomNav } = renderShell({ user, onNewPost });
    await userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
    await userEvent.click(within(bottomNav).getByRole("button", { name: "New post" }));
    expect(onNewPost).toHaveBeenCalledTimes(2);
  });

  it("shows the user card with a menu of Profile, Settings and Log out", async () => {
    const onLogout = vi.fn();
    const { sidebar } = renderShell({ user, onLogout });
    expect(within(sidebar).getByText("Ada Lovelace")).toBeInTheDocument();
    expect(within(sidebar).getByText("@ada")).toBeInTheDocument();
    const trigger = within(sidebar).getByRole("button", { name: "User menu" });
    const menu = document.getElementById(trigger.getAttribute("popovertarget") ?? "");
    expect(menu).toHaveAttribute("popover", "auto");
    const entries = within(menu as HTMLElement).getAllByRole("listitem", { hidden: true });
    expect(entries.map(textOf)).toEqual(["Profile", "Settings", "Log out"]);
    await userEvent.click(within(menu as HTMLElement).getByRole("button", { hidden: true }));
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("shows Moderation only to staff, opening Django Admin in a new tab", () => {
    renderShell({ user });
    expect(screen.queryByRole("link", { name: /Moderation/ })).toBeNull();
    document.body.innerHTML = "";
    const { sidebar } = renderShell({ user: staff });
    const moderation = within(sidebar).getByRole("link", { name: /Moderation/ });
    expect(moderation).toHaveAttribute("href", "https://api.example.test/secret-admin/");
    expect(moderation).toHaveAttribute("target", "_blank");
    expect(moderation).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("has five bottom tabs and an account sheet with the rest, then Log out", async () => {
    const onLogout = vi.fn();
    const { bottomNav } = renderShell({ user: staff, onLogout });
    const tabs = Array.from(bottomNav.children).map(textOf);
    expect(tabs).toEqual(["Home", "Search", "New post", "Notifications", "Profile"]);
    const trigger = screen.getByRole("button", { name: "Account menu" });
    const sheet = document.getElementById(trigger.getAttribute("popovertarget") ?? "");
    const entries = within(sheet as HTMLElement).getAllByRole("listitem", { hidden: true });
    expect(entries.map(textOf)).toEqual([
      "Bookmarks",
      "Settings",
      "Moderation (opens in a new tab)",
      "Log out",
    ]);
    await userEvent.click(
      within(sheet as HTMLElement).getByRole("button", { name: "Log out", hidden: true }),
    );
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("has no Log out entry without a handler", () => {
    renderShell({ user });
    expect(screen.queryByRole("button", { name: "Log out", hidden: true })).toBeNull();
  });

  it("shows the unverified banner only to unverified users", () => {
    renderShell({ user: { ...user, is_email_verified: false } });
    const main = screen.getByRole("main");
    expect(within(main).getByText("Verify your email to post, comment and report.")).toBeVisible();
    expect(within(main).getByText("Check your inbox for the link.")).toBeVisible();
    document.body.innerHTML = "";
    renderShell({ user });
    expect(screen.queryByText(/Verify your email/)).toBeNull();
  });

  it("links the top-bar avatar to the profile", () => {
    renderShell({ user });
    expect(screen.getByRole("link", { name: "Your profile" })).toHaveAttribute("href", "/u/ada");
  });
});

describe("AppShell, while the session loads", () => {
  it("shows placeholders instead of the account areas, and no banner", () => {
    const { sidebar, railNav, bottomNav } = renderShell({
      user: { ...user, is_email_verified: false },
      status: "loading",
    });
    expect(within(railNav).getAllByRole("link").map(textOf)).toEqual(["Home", "Search"]);
    expect(within(sidebar).getByTestId("account-loading")).toBeInTheDocument();
    expect(within(sidebar).queryByRole("link", { name: "Log in" })).toBeNull();
    expect(within(sidebar).queryByRole("link", { name: "Sign up" })).toBeNull();
    expect(within(sidebar).queryByText("Ada Lovelace")).toBeNull();
    expect(screen.queryByRole("link", { name: "Your profile" })).toBeNull();
    expect(screen.queryByRole("button", { name: /menu/i })).toBeNull();
    expect(within(bottomNav).getAllByRole("link").map(textOf)).toEqual(["Home", "Search"]);
    expect(screen.queryByText(/Verify your email/)).toBeNull();
  });
});

describe("AppShell, logged out", () => {
  it("shows only Home and Search, and Log in / Sign up", () => {
    const { sidebar, railNav, bottomNav } = renderShell({ user: null });
    expect(within(railNav).getAllByRole("link").map(textOf)).toEqual(["Home", "Search"]);
    expect(within(sidebar).getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(within(sidebar).getByRole("link", { name: "Sign up" })).toHaveAttribute(
      "href",
      "/signup",
    );
    expect(within(sidebar).queryByRole("button", { name: "New post" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Notifications" })).toBeNull();
    expect(within(bottomNav).getAllByRole("link").map(textOf)).toEqual([
      "Home",
      "Search",
      "Log in",
    ]);
    expect(screen.queryByRole("button", { name: /menu/i })).toBeNull();
  });
});

describe("AppShell layout", () => {
  it("places the logo: wordmark and mark in the rail, small wordmark on phones", () => {
    const { sidebar } = renderShell({ user });
    const [wordmark, mark] = logos(sidebar);
    expect(wordmark.height).toBe(36);
    expect(wordmark.width).toBeGreaterThan(wordmark.height * 2);
    expect(mark).toEqual({ height: 36, width: 36 });
    const phoneBar = screen.getAllByRole("banner").find((el) => el.className.includes("md:hidden"));
    const [phoneLogo] = logos(phoneBar as HTMLElement);
    expect(phoneLogo.height).toBe(24);
    expect(phoneLogo.width).toBeGreaterThan(phoneLogo.height * 2);
  });

  it("switches layouts at 768px and 1280px (rail, icon dock, phone bars)", () => {
    const { sidebar, bottomNav } = renderShell({ user });
    expect(sidebar).toHaveClass("hidden", "md:flex", "w-16", "xl:w-64");
    const [topBar, phoneBar] = screen.getAllByRole("banner");
    expect(topBar).toHaveClass("hidden", "md:flex", "left-16", "xl:left-64");
    expect(phoneBar).toHaveClass("md:hidden");
    expect(bottomNav).toHaveClass("md:hidden");
    expect(screen.getByRole("main")).toHaveClass(
      "pt-16",
      "pb-16",
      "md:pb-0",
      "md:pl-16",
      "xl:pl-64",
    );
    // Dock labels stay as accessible names.
    expect(within(sidebar).getByText("Home")).toHaveClass("sr-only", "xl:not-sr-only");
  });

  it("searches with GET /search?q=", () => {
    renderShell({ user });
    const form = screen.getByRole("search");
    expect(form).toHaveAttribute("action", "/search");
    expect(within(form).getByRole("searchbox", { name: "Search" })).toHaveAttribute("name", "q");
  });

  it("starts with a skip link to the content", () => {
    renderShell({ user });
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getByText("Page content")).toBeInTheDocument();
  });
});
