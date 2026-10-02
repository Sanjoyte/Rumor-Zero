import { describe, expect, it } from "vitest";
import {
  footerItems,
  isActive,
  moderationItem,
  nameOf,
  primaryItems,
  sheetItems,
  userMenuItems,
  type ShellUser,
} from "./nav-items";

const user: ShellUser = {
  username: "ada",
  display_name: "Ada",
  avatar_url: null,
  is_email_verified: true,
};
const staff: ShellUser = { ...user, admin_url: "https://api.example.test/secret-admin/" };
const labels = (items: { label: string }[]) => items.map((item) => item.label);

describe("nav items", () => {
  it("shows logged-out visitors only Home and Search", () => {
    expect(labels(primaryItems(null))).toEqual(["Home", "Search"]);
    expect(footerItems(null)).toEqual([]);
  });

  it("shows a user the full rail", () => {
    expect(labels(primaryItems(user))).toEqual([
      "Home",
      "Search",
      "Notifications",
      "Profile",
      "Bookmarks",
    ]);
    expect(primaryItems(user)[3].href).toBe("/u/ada");
    expect(labels(footerItems(user))).toEqual(["Settings"]);
    expect(labels(userMenuItems(user))).toEqual(["Profile", "Settings"]);
    expect(labels(sheetItems(user))).toEqual(["Bookmarks", "Settings"]);
  });

  it("adds Moderation only for staff, as an external link", () => {
    expect(moderationItem(user)).toBeNull();
    expect(moderationItem(staff)).toMatchObject({
      label: "Moderation",
      href: "https://api.example.test/secret-admin/",
      external: true,
    });
    expect(labels(footerItems(staff))).toEqual(["Moderation", "Settings"]);
    expect(labels(sheetItems(staff))).toEqual(["Bookmarks", "Settings", "Moderation"]);
  });

  it("is active on the page and below it, but not on a longer name", () => {
    expect(isActive("/home", "/home")).toBe(true);
    expect(isActive("/u/ada/followers", "/u/ada")).toBe(true);
    expect(isActive("/homepage", "/home")).toBe(false);
    expect(isActive("/u/adam", "/u/ada")).toBe(false);
  });

  it("falls back to the handle when the display name is blank", () => {
    expect(nameOf(user)).toBe("Ada");
    expect(nameOf({ ...user, display_name: "  " })).toBe("@ada");
  });
});
