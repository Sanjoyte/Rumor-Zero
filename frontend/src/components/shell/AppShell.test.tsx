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
  onNewPostBlocked?: () => void;
  onResend?: () => void;
  resendSecondsLeft?: number;
  resending?: boolean;
  onLogout?: () => void;
  unreadCount?: number;
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

  it("keeps Moderation out of the phone account sheet for people who aren't staff", () => {
    // The sheet is a closed popover, so its links are hidden from the default role queries (the
    // rail test above can't see them): look at its entries directly.
    renderShell({ user, onLogout: vi.fn() });
    const trigger = screen.getByRole("button", { name: "Account menu" });
    const sheet = document.getElementById(trigger.getAttribute("popovertarget") ?? "");
    const entries = within(sheet as HTMLElement).getAllByRole("listitem", { hidden: true });
    expect(entries.map(textOf)).toEqual(["Bookmarks", "Settings", "Log out"]);
    expect(screen.queryByRole("link", { name: /Moderation/, hidden: true })).toBeNull();
    expect(document.body.textContent).not.toContain("secret-admin");
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

  describe("while the email is unverified", () => {
    const unverified: ShellUser = { ...user, is_email_verified: false };

    it("keeps New post focusable but aria-disabled, with a hint for each copy", () => {
      const { sidebar, bottomNav } = renderShell({ user: unverified });
      const rail = within(sidebar).getByRole("button", { name: "New post" });
      const tab = within(bottomNav).getByRole("button", { name: "New post" });
      for (const button of [rail, tab]) {
        expect(button).toHaveAttribute("aria-disabled", "true");
        expect(button).not.toBeDisabled();
        expect(button).toHaveClass("aria-disabled:cursor-not-allowed", "aria-disabled:opacity-60");
        expect(button.className).not.toMatch(/(^|\s)hover:/);
        button.focus();
        expect(button).toHaveFocus();
      }
      // Both copies are in the DOM, so each needs its own hint id.
      const hints = [rail, tab].map((button) => button.getAttribute("aria-describedby"));
      expect(hints[0]).toBeTruthy();
      expect(hints[1]).toBeTruthy();
      expect(hints[0]).not.toBe(hints[1]);
      expect(rail).toHaveAccessibleDescription("Verify your email to post.");
      expect(tab).toHaveAccessibleDescription("Verify your email to post.");
    });

    it("calls onNewPostBlocked, not onNewPost, from both copies", async () => {
      const onNewPost = vi.fn();
      const onNewPostBlocked = vi.fn();
      const { sidebar, bottomNav } = renderShell({ user: unverified, onNewPost, onNewPostBlocked });
      await userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
      await userEvent.click(within(bottomNav).getByRole("button", { name: "New post" }));
      expect(onNewPostBlocked).toHaveBeenCalledTimes(2);
      expect(onNewPost).not.toHaveBeenCalled();
    });

    it("works with the keyboard", async () => {
      const onNewPostBlocked = vi.fn();
      const { sidebar } = renderShell({ user: unverified, onNewPostBlocked });
      within(sidebar).getByRole("button", { name: "New post" }).focus();
      await userEvent.keyboard("{Enter}");
      expect(onNewPostBlocked).toHaveBeenCalledTimes(1);
    });

    it("does not crash without a blocked handler", async () => {
      const { sidebar } = renderShell({ user: unverified });
      await userEvent.click(within(sidebar).getByRole("button", { name: "New post" }));
    });

    it("becomes a normal button once the user is verified", async () => {
      const onNewPost = vi.fn();
      const onNewPostBlocked = vi.fn();
      const { sidebar, bottomNav } = renderShell({ user, onNewPost, onNewPostBlocked });
      for (const nav of [sidebar, bottomNav]) {
        const button = within(nav).getByRole("button", { name: "New post" });
        expect(button).not.toHaveAttribute("aria-disabled");
        expect(button).not.toHaveAttribute("aria-describedby");
        await userEvent.click(button);
      }
      expect(onNewPost).toHaveBeenCalledTimes(2);
      expect(onNewPostBlocked).not.toHaveBeenCalled();
      expect(screen.queryByText("Verify your email to post.")).toBeNull();
    });

    it("has no Resend in the banner unless the layout provides one", () => {
      renderShell({ user: unverified });
      expect(screen.queryByRole("button", { name: /Resend/ })).toBeNull();
    });

    it("shows Resend in the banner and calls it", async () => {
      const onResend = vi.fn();
      renderShell({ user: unverified, onResend, resendSecondsLeft: 0 });
      const button = within(screen.getByRole("main")).getByRole("button", { name: "Resend link" });
      expect(button).toBeEnabled();
      await userEvent.click(button);
      expect(onResend).toHaveBeenCalledTimes(1);
    });

    it("shows the countdown and disables Resend while it runs", async () => {
      const onResend = vi.fn();
      renderShell({ user: unverified, onResend, resendSecondsLeft: 42 });
      const button = within(screen.getByRole("main")).getByRole("button", {
        name: "Resend link (42s)",
      });
      expect(button).toBeDisabled();
      await userEvent.click(button);
      expect(onResend).not.toHaveBeenCalled();
    });

    it("shows the busy state while a resend is running", () => {
      renderShell({ user: unverified, onResend: vi.fn(), resending: true });
      expect(
        within(screen.getByRole("main")).getByRole("button", { name: "Resend link" }),
      ).toHaveAttribute("aria-busy", "true");
    });
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

describe("AppShell, the unread badge (Part 13)", () => {
  it("shows nothing for 0 and adds nothing to the link's name", () => {
    const { railNav, bottomNav } = renderShell({ user, unreadCount: 0 });
    expect(screen.queryByTestId("unread-badge")).toBeNull();
    expect(within(railNav).getByRole("link", { name: "Notifications" })).toBeInTheDocument();
    expect(within(bottomNav).getByRole("link", { name: "Notifications" })).toBeInTheDocument();
  });

  it("shows nothing when no count is given", () => {
    renderShell({ user });
    expect(screen.queryByTestId("unread-badge")).toBeNull();
  });

  it("puts the number on the rail's link (a pill and a dock corner) and on the phone tab", () => {
    const { railNav, bottomNav } = renderShell({ user, unreadCount: 3 });
    expect(
      within(railNav)
        .getAllByTestId("unread-badge")
        .map((b) => b.textContent),
    ).toEqual(["3", "3"]);
    expect(
      within(bottomNav)
        .getAllByTestId("unread-badge")
        .map((b) => b.textContent),
    ).toEqual(["3"]);
  });

  it("is spoken as part of the link's name, once, and the visible number is hidden from readers", () => {
    const { railNav, bottomNav } = renderShell({ user, unreadCount: 3 });
    expect(
      within(railNav).getByRole("link", { name: "Notifications, 3 unread" }),
    ).toBeInTheDocument();
    expect(
      within(bottomNav).getByRole("link", { name: "Notifications, 3 unread" }),
    ).toBeInTheDocument();
    for (const badge of screen.getAllByTestId("unread-badge")) {
      expect(badge).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("gives the whole name as one label, because browsers put a space before a hidden span's text", () => {
    const { railNav, bottomNav } = renderShell({ user, unreadCount: 3 });
    expect(within(railNav).getByRole("link", { name: /^Notifications/ })).toHaveAttribute(
      "aria-label",
      "Notifications, 3 unread",
    );
    expect(within(bottomNav).getByRole("link", { name: /^Notifications/ })).toHaveAttribute(
      "aria-label",
      "Notifications, 3 unread",
    );
    expect(within(railNav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-label");
  });

  it("caps the number at 99+", () => {
    const { railNav } = renderShell({ user, unreadCount: 250 });
    expect(within(railNav).getAllByTestId("unread-badge")[0]).toHaveTextContent("99+");
    expect(
      within(railNav).getByRole("link", { name: "Notifications, 99+ unread" }),
    ).toBeInTheDocument();
  });

  it("shows 99 as 99", () => {
    const { railNav } = renderShell({ user, unreadCount: 99 });
    expect(within(railNav).getAllByTestId("unread-badge")[0]).toHaveTextContent("99");
    expect(within(railNav).getAllByTestId("unread-badge")[0]).not.toHaveTextContent("99+");
  });

  it("badges only the Notifications link", () => {
    const { railNav } = renderShell({ user, unreadCount: 4 });
    for (const name of ["Home", "Search", "Profile", "Bookmarks"]) {
      const link = within(railNav).getByRole("link", { name });
      expect(within(link).queryByTestId("unread-badge")).toBeNull();
    }
  });

  it("inverts the colours on the active item, which is already filled", () => {
    pathname = "/notifications";
    const { railNav } = renderShell({ user, unreadCount: 2 });
    const link = within(railNav).getByRole("link", { name: "Notifications, 2 unread" });
    expect(link).toHaveAttribute("aria-current", "page");
    for (const badge of within(link).getAllByTestId("unread-badge")) {
      expect(badge).toHaveClass("bg-on-secondary", "text-secondary");
    }
  });

  it("uses the filled colours on an inactive item", () => {
    const { railNav } = renderShell({ user, unreadCount: 2 });
    for (const badge of within(railNav).getAllByTestId("unread-badge")) {
      expect(badge).toHaveClass("bg-secondary", "text-on-secondary");
    }
  });

  it("gives a visitor no Notifications link and so no badge", () => {
    renderShell({ user: null, unreadCount: 5 });
    expect(screen.queryByTestId("unread-badge")).toBeNull();
  });
});
