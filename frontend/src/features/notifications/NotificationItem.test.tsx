import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast } from "@/features/posts/test-helpers";
import type { NotificationData } from "@/lib/api/types";
import { NotificationItem } from "./NotificationItem";
import { BO_ACTOR, makeNotification, NOW, oneOfEach } from "./test-helpers";

function show(item: NotificationData, { read = false, onOpen = vi.fn() } = {}) {
  const view = renderWithSessionAndToast(
    <NotificationItem item={item} read={read} onOpen={onOpen} now={NOW} />,
  );
  return { ...view, onOpen, article: screen.getByRole("article") };
}

describe("NotificationItem: the nine kinds", () => {
  it("renders every kind with a link to where it leads", () => {
    for (const item of oneOfEach()) {
      const { unmount, article } = show(item);
      expect(article).toHaveAttribute("data-type", item.type);
      const link = within(article).getByRole("link");
      expect(link).toHaveAttribute(
        "href",
        item.type === "follow" ? "/u/bo" : "/p/11111111-1111-4111-8111-111111111111",
      );
      unmount();
    }
  });

  it("follow: names the person and offers Follow back", async () => {
    show(oneOfEach()[0]);
    expect(screen.getByText("Bo Bell")).toBeInTheDocument();
    expect(screen.getByText(/followed you\./)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Follow back" })).toBeInTheDocument();
  });

  it("follow: shows Following when you already follow them", async () => {
    show(makeNotification({ type: "follow", post: null, actor: { ...BO_ACTOR, following: true } }));
    expect(await screen.findByRole("button", { name: "Following" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Follow back" })).toBeNull();
  });

  it("follow: the button is not inside the link", async () => {
    const { article } = show(oneOfEach()[0]);
    const link = within(article).getByRole("link");
    const button = await screen.findByRole("button", { name: "Follow back" });
    expect(within(link).queryByRole("button")).toBeNull();
    expect(article).toContainElement(button);
    expect(button.parentElement?.className).toContain("z-10");
  });

  it("follow: a gone account says Someone, has no link and no button", () => {
    const { article } = show(makeNotification({ type: "follow", post: null, actor: null }));
    expect(within(article).getByText(/Someone/)).toBeInTheDocument();
    expect(within(article).queryByRole("link")).toBeNull();
    expect(within(article).queryByRole("button")).toBeNull();
  });

  it("like: says who and quotes the post", () => {
    show(makeNotification());
    expect(screen.getByText(/liked your post/)).toBeInTheDocument();
    expect(screen.getByText("“Rain is nice”")).toBeInTheDocument();
  });

  it("repost: says who and quotes the post", () => {
    show(makeNotification({ type: "repost" }));
    expect(screen.getByText(/reposted your post/)).toBeInTheDocument();
  });

  it("comment: shows the comment in a quote", () => {
    show(oneOfEach()[2]);
    expect(screen.getByText(/commented on your post/)).toBeInTheDocument();
    expect(screen.getByText("“Agreed, mostly”")).toBeInTheDocument();
  });

  it("verdict true: says verified and carries the VERIFIED chip, with no percentage", () => {
    show(oneOfEach()[4]);
    expect(screen.getByText(/checked and verified/)).toBeInTheDocument();
    expect(screen.getByText("VERIFIED")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("verdict false: says labelled FALSE and carries the FALSE chip", () => {
    show(makeNotification({ type: "verdict", outcome: "false", actor: null }));
    expect(screen.getByText(/labelled FALSE/)).toBeInTheDocument();
    expect(screen.getByText("FALSE")).toBeInTheDocument();
  });

  it("under review: carries the UNDER REVIEW chip", () => {
    show(makeNotification({ type: "under_review", actor: null }));
    expect(screen.getByText(/is under review/)).toBeInTheDocument();
    expect(screen.getByText("UNDER REVIEW")).toBeInTheDocument();
  });

  it("removed: carries the REMOVED chip and points to the reason", () => {
    show(makeNotification({ type: "removed", actor: null }));
    expect(screen.getByText("REMOVED")).toBeInTheDocument();
    expect(screen.getByText("The reason is on the post.")).toBeInTheDocument();
  });

  it("emergency demoted: carries the EMERGENCY chip and says it is still checked", () => {
    show(makeNotification({ type: "emergency_demoted", actor: null }));
    expect(screen.getByText("EMERGENCY")).toBeInTheDocument();
    expect(screen.getByText(/no longer pinned/)).toBeInTheDocument();
  });

  it("appeal resolved: upheld and overturned read differently", () => {
    const first = show(makeNotification({ type: "appeal_resolved", outcome: "upheld" }));
    expect(screen.getByText(/The decision stands/)).toBeInTheDocument();
    first.unmount();
    show(makeNotification({ type: "appeal_resolved", outcome: "overturned" }));
    expect(screen.getByText(/The decision was overturned/)).toBeInTheDocument();
  });

  it("never names a moderator", () => {
    for (const item of oneOfEach().filter((i) => i.actor === null)) {
      const { unmount, article } = show(item);
      expect(article.textContent).not.toMatch(/Bo Bell|@bo/);
      unmount();
    }
  });
});

describe("NotificationItem: reading it", () => {
  it("an unread item has a dot named Unread; a read one has none", () => {
    const first = show(makeNotification(), { read: false });
    expect(screen.getByText("Unread")).toBeInTheDocument();
    first.unmount();
    show(makeNotification(), { read: true });
    expect(screen.queryByText("Unread")).toBeNull();
  });

  it("shows the time as a short age with the exact time for tools", () => {
    show(makeNotification());
    const time = screen.getByText("1h");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("datetime", "2026-10-20T11:00:00Z");
  });

  it("calls onOpen with the item when its link is followed", async () => {
    const item = makeNotification();
    const { onOpen } = show(item);
    await userEvent.click(screen.getByRole("link"));
    expect(onOpen).toHaveBeenCalledWith(item);
  });

  it("makes the whole row clickable with a stretched link", () => {
    show(makeNotification());
    expect(screen.getByRole("link").className).toContain("after:absolute");
    expect(screen.getByRole("link").className).toContain("after:inset-0");
    expect(screen.getByRole("article").className).toContain("relative");
  });

  it("an opinion's quote is italic and a fact's is not", () => {
    const opinion = show(makeNotification());
    expect(screen.getByText("“Rain is nice”").className).toContain("italic");
    opinion.unmount();
    const post = makeNotification().post!;
    show(makeNotification({ post: { ...post, post_type: "fact" } }));
    expect(screen.getByText("“Rain is nice”").className).not.toContain("italic");
    expect(screen.getByText("“Rain is nice”").className).toContain("font-claim-headline");
  });

  it("uses the handle when the person has no display name", () => {
    show(makeNotification({ actor: { ...BO_ACTOR, display_name: "" } }));
    expect(screen.getByText("@bo")).toBeInTheDocument();
  });
});
