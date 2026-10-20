import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { testSession } from "@/features/auth/test-helpers";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import Page, { metadata } from "./page";

const api = vi.hoisted(() => ({
  fetchNotifications: vi.fn(async () => ({ items: [], nextCursor: null })),
  markRead: vi.fn(),
  fetchUnreadCount: vi.fn(async () => 0),
}));
vi.mock("@/features/notifications/notifications-api", () => api);

describe("/notifications", () => {
  it("has a fixed title and is never indexed", () => {
    expect(metadata.title).toBe("Notifications");
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });

  it("sets no page-level share tags, so nothing replaces the root's", () => {
    expect(metadata.openGraph).toBeUndefined();
    expect(metadata.twitter).toBeUndefined();
  });

  it("is a static page: it takes no props or searchParams", () => {
    expect(Page.length).toBe(0);
  });

  it("renders the screen", async () => {
    render(
      <AuthProvider session={testSession({}, { loggedIn: true }).session}>
        <ToastProvider>
          <Page />
        </ToastProvider>
      </AuthProvider>,
    );
    expect(
      await screen.findByRole("heading", { level: 1, name: "Notifications" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Nothing yet")).toBeInTheDocument();
  });
});
