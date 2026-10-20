import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { sessionOf } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import type { NotificationData } from "@/lib/api/types";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { NOTIFICATION_MESSAGES } from "./messages";
import { NotificationsPage } from "./NotificationsPage";
import { makeNotification, NOW } from "./test-helpers";
import { UnreadCountProvider } from "./UnreadCountProvider";

const api = vi.hoisted(() => ({
  fetchNotifications: vi.fn(),
  markRead: vi.fn(),
  fetchUnreadCount: vi.fn(),
}));
vi.mock("./notifications-api", () => api);

beforeEach(() => {
  api.fetchNotifications.mockReset();
  api.markRead.mockReset();
  api.fetchUnreadCount.mockReset();
});

const page = (items: NotificationData[], nextCursor: string | null = null) => ({
  items,
  nextCursor,
});

function renderPage({
  counts = [0],
  intervalMs = 60_000,
}: { counts?: number[]; intervalMs?: number } = {}) {
  let n = 0;
  const fetchCount = vi.fn(async () => counts[Math.min(n++, counts.length - 1)]);
  const session = sessionOf("verified");
  const view = render(
    <AuthProvider session={session.session}>
      <ToastProvider>
        <UnreadCountProvider fetchCount={fetchCount} intervalMs={intervalMs}>
          <NotificationsPage now={NOW} />
        </UnreadCountProvider>
      </ToastProvider>
    </AuthProvider>,
  );
  return { ...view, fetchCount };
}

const unread = (n: number) =>
  makeNotification({ id: `u${n}`, created_at: `2026-10-20T11:0${n}:00Z` });
const read = (n: number) =>
  makeNotification({ id: `r${n}`, is_read: true, created_at: `2026-10-20T10:0${n}:00Z` });

async function loaded() {
  await screen.findAllByRole("article");
}

describe("NotificationsPage: loading and states", () => {
  it("shows a skeleton, then the items newest first", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(2), unread(1), read(1)]));
    renderPage({ counts: [2] });
    expect(screen.getByText("Loading notifications…")).toBeInTheDocument();
    await loaded();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(api.fetchNotifications).toHaveBeenCalledWith(null, expect.any(AbortSignal));
    expect(screen.getByRole("heading", { level: 1, name: "Notifications" })).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    api.fetchNotifications.mockResolvedValue(page([]));
    renderPage();
    expect(await screen.findByText(NOTIFICATION_MESSAGES.emptyTitle)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark all as read" })).toBeNull();
  });

  it("shows the error with Try again, and loads on retry", async () => {
    api.fetchNotifications.mockRejectedValueOnce(
      new ApiError({ status: 500, code: "x", detail: "", fieldErrors: {} }),
    );
    api.fetchNotifications.mockResolvedValueOnce(page([unread(1)]));
    renderPage();
    expect(await screen.findByText(NOTIFICATION_MESSAGES.listFailed)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await loaded();
  });

  it("says when the server is waking or when the allowance is used", async () => {
    api.fetchNotifications.mockRejectedValueOnce(
      new ApiError({ status: 503, code: "backend_waking", detail: "", fieldErrors: {} }),
    );
    const first = renderPage();
    expect(await screen.findByText(NOTIFICATION_MESSAGES.waking)).toBeInTheDocument();
    first.unmount();
    api.fetchNotifications.mockRejectedValueOnce(
      new ApiError({ status: 429, code: "throttled", detail: "", fieldErrors: {}, retryAfter: 20 }),
    );
    renderPage();
    expect(await screen.findByText(/You're going too fast/)).toBeInTheDocument();
  });

  it("loads more with the cursor and ends with a note", async () => {
    api.fetchNotifications.mockResolvedValueOnce(page([unread(2)], "c2"));
    api.fetchNotifications.mockResolvedValueOnce(page([read(1)]));
    renderPage();
    await loaded();
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(2));
    expect(api.fetchNotifications).toHaveBeenLastCalledWith("c2", expect.any(AbortSignal));
    expect(screen.getByText(NOTIFICATION_MESSAGES.endLabel)).toBeInTheDocument();
  });
});

describe("NotificationsPage: the unread chip", () => {
  it("shows the server's count, not the number of loaded unread items", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(1)], "c2"));
    renderPage({ counts: [7] });
    await loaded();
    expect(await screen.findByText("7 unread")).toBeInTheDocument();
  });

  it("shows no chip and no Mark all when nothing is unread", async () => {
    api.fetchNotifications.mockResolvedValue(page([read(1)]));
    renderPage({ counts: [0] });
    await loaded();
    expect(screen.queryByText(/unread$/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark all as read" })).toBeNull();
  });
});

describe("NotificationsPage: opening an item", () => {
  it("marks it read at once, adjusts the count, and tells the server", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(2), unread(1)]));
    api.markRead.mockResolvedValue(1);
    renderPage({ counts: [2] });
    await loaded();
    await screen.findByText("2 unread");
    const [first] = screen.getAllByRole("article");
    await userEvent.click(within(first).getByRole("link"));
    expect(within(first).queryByText("Unread")).toBeNull();
    expect(api.markRead).toHaveBeenCalledWith({ ids: ["u2"] });
    expect(await screen.findByText("1 unread")).toBeInTheDocument();
  });

  it("lowers the count before the server has answered", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(2), unread(1)]));
    let resolve: (n: number) => void = () => {};
    api.markRead.mockImplementation(() => new Promise<number>((r) => (resolve = r)));
    renderPage({ counts: [2] });
    await loaded();
    await screen.findByText("2 unread");
    await userEvent.click(within(screen.getAllByRole("article")[0]).getByRole("link"));
    expect(screen.getByText("1 unread")).toBeInTheDocument();
    await act(async () => resolve(1));
    expect(screen.getByText("1 unread")).toBeInTheDocument();
  });

  it("opening an item that is already read does nothing", async () => {
    api.fetchNotifications.mockResolvedValue(page([read(1)]));
    renderPage({ counts: [3] });
    await loaded();
    await userEvent.click(screen.getByRole("link"));
    expect(api.markRead).not.toHaveBeenCalled();
  });

  it("opening the same item twice tells the server once", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(1)]));
    api.markRead.mockResolvedValue(0);
    renderPage({ counts: [1] });
    await loaded();
    await userEvent.click(screen.getByRole("link"));
    await userEvent.click(screen.getByRole("link"));
    expect(api.markRead).toHaveBeenCalledTimes(1);
  });

  it("stays quiet when the background call fails", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(1)]));
    api.markRead.mockRejectedValue(new Error("down"));
    renderPage({ counts: [1] });
    await loaded();
    await userEvent.click(screen.getByRole("link"));
    await waitFor(() => expect(api.markRead).toHaveBeenCalled());
    expect(screen.queryByRole("status")?.textContent ?? "").toBe("");
  });
});

describe("NotificationsPage: Mark all as read", () => {
  it("marks every loaded item read at once, then takes the server's count", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(2), unread(1)]));
    api.markRead.mockResolvedValue(0);
    renderPage({ counts: [2] });
    await loaded();
    await screen.findByText("2 unread");
    await userEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(api.markRead).toHaveBeenCalledWith({ all: true });
    await waitFor(() => expect(screen.queryByText("Unread")).toBeNull());
    expect(screen.queryByText(/unread$/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark all as read" })).toBeNull();
  });

  it("keeps a higher server count when new items arrived meanwhile", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(1)]));
    api.markRead.mockResolvedValue(3);
    renderPage({ counts: [1] });
    await loaded();
    await screen.findByText("1 unread");
    await userEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(await screen.findByText("3 unread")).toBeInTheDocument();
  });

  it("rolls back with a toast when it fails", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(2), unread(1)]));
    api.markRead.mockRejectedValue(
      new ApiError({ status: 500, code: "x", detail: "", fieldErrors: {} }),
    );
    renderPage({ counts: [2] });
    await loaded();
    await screen.findByText("2 unread");
    await userEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(await screen.findByText(NOTIFICATION_MESSAGES.markAllFailed)).toBeInTheDocument();
    expect(screen.getAllByText("Unread")).toHaveLength(2);
    expect(screen.getByText("2 unread")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark all as read" })).toBeEnabled();
  });

  it("sends one request for a double click", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(1)]));
    let resolve: (n: number) => void = () => {};
    api.markRead.mockImplementation(() => new Promise<number>((r) => (resolve = r)));
    renderPage({ counts: [1] });
    await loaded();
    await screen.findByText("1 unread");
    const button = screen.getByRole("button", { name: "Mark all as read" });
    act(() => {
      button.click();
      button.click();
    });
    expect(api.markRead).toHaveBeenCalledTimes(1);
    await act(async () => resolve(0));
  });
});

describe("NotificationsPage: new items arriving while it is open", () => {
  it("puts new items on top without resetting the list", async () => {
    const fresh = makeNotification({ id: "new", created_at: "2026-10-20T11:30:00Z" });
    api.fetchNotifications
      .mockResolvedValueOnce(page([unread(1)], "c2")) // first load
      .mockResolvedValueOnce(page([read(1)])) // Load more
      .mockResolvedValue(page([fresh, unread(1)], "c2")); // the arrival reload
    renderPage({ counts: [1, 1, 2], intervalMs: 40 });
    await loaded();
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(2));
    // The poll sees 2 > 1: the first page is fetched again and `fresh` goes on top.
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(3));
    const ids = screen
      .getAllByRole("article")
      .map((a) => a.querySelector("time")?.getAttribute("datetime"));
    expect(ids).toEqual(["2026-10-20T11:30:00Z", "2026-10-20T11:01:00Z", "2026-10-20T10:01:00Z"]);
  });

  it("adds several new items oldest first so the newest ends on top", async () => {
    const a = makeNotification({ id: "a", created_at: "2026-10-20T11:20:00Z" });
    const b = makeNotification({ id: "b", created_at: "2026-10-20T11:40:00Z" });
    api.fetchNotifications
      .mockResolvedValueOnce(page([unread(1)]))
      .mockResolvedValue(page([b, a, unread(1)]));
    renderPage({ counts: [1, 3], intervalMs: 40 });
    await loaded();
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(3));
    const stamps = screen
      .getAllByRole("article")
      .map((x) => x.querySelector("time")?.getAttribute("datetime"));
    expect(stamps[0]).toBe("2026-10-20T11:40:00Z");
    expect(stamps[1]).toBe("2026-10-20T11:20:00Z");
  });

  it("does not reload when the count falls or stays", async () => {
    api.fetchNotifications.mockResolvedValue(page([unread(1)]));
    renderPage({ counts: [2, 2, 1], intervalMs: 30 });
    await loaded();
    await new Promise((r) => setTimeout(r, 150));
    expect(api.fetchNotifications).toHaveBeenCalledTimes(1);
  });

  it("stays quiet when the reload fails", async () => {
    api.fetchNotifications
      .mockResolvedValueOnce(page([unread(1)]))
      .mockRejectedValue(new Error("down"));
    renderPage({ counts: [1, 2], intervalMs: 40 });
    await loaded();
    await waitFor(() => expect(api.fetchNotifications).toHaveBeenCalledTimes(2));
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.queryByText(NOTIFICATION_MESSAGES.listFailed)).toBeNull();
  });
});
