import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { APPEAL_MESSAGES } from "@/features/appeals/messages";
import { ApiError } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { RemovedPostCard } from "./RemovedPostCard";
import { makePost, renderWithSessionAndToast, type SessionKind } from "./test-helpers";
import { REMOVED_MESSAGES } from "./Tombstone";

const api = vi.hoisted(() => ({ appealPost: vi.fn() }));
vi.mock("@/features/appeals/appeals-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/appeals/appeals-api")>()),
  ...api,
}));

const NOW = new Date("2026-10-08T14:00:00Z");
const MINE = makePost({
  status: "removed",
  post_type: "fact",
  content: "My removed claim",
  is_mine: true,
  can_appeal: true,
  removal_reason: "Personal attack",
});
// What a visitor gets: the same keys, blanked.
const THEIRS = makePost({
  status: "removed",
  post_type: "fact",
  content: "",
  is_mine: false,
  removal_reason: "",
});

const FILED = { ...MINE, can_appeal: false, appeal_status: "open" as const };

beforeEach(() => {
  api.appealPost.mockReset();
  api.appealPost.mockResolvedValue(FILED);
});

function renderCard(post: Post, kind: SessionKind = "verified", props = {}) {
  return renderWithSessionAndToast(<RemovedPostCard post={post} now={NOW} {...props} />, kind);
}

describe("RemovedPostCard: everyone but the author", () => {
  it("is the tombstone on a card: no text, no link, no badge, no button", () => {
    const { container } = renderCard(THEIRS, "anonymous");
    expect(screen.getByText(REMOVED_MESSAGES.card)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(container.querySelector("blockquote, h1")).toBeNull();
    expect(screen.queryByText(/Only you can see/)).not.toBeInTheDocument();
  });

  it("is the page's notice, with the author row, on the post page", () => {
    renderCard(THEIRS, "verified", { layout: "page", authorRow: <p>The author row</p> });
    expect(screen.getByText(REMOVED_MESSAGES.page)).toBeInTheDocument();
    expect(screen.getByText("The author row")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("never shows a removal reason or an appeal to somebody else, even if one slipped in", () => {
    renderCard({ ...THEIRS, removal_reason: "leaked", appeal_status: "open", can_appeal: true });
    expect(screen.queryByText(/leaked/)).not.toBeInTheDocument();
    expect(screen.queryByText(/APPEAL PENDING/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("RemovedPostCard: the author, on a card", () => {
  it("shows their words, the reason and the button, and says only they can see it", async () => {
    renderCard(MINE);
    expect(screen.getByText(REMOVED_MESSAGES.card)).toBeInTheDocument();
    expect(screen.getByText(REMOVED_MESSAGES.onlyYou)).toBeInTheDocument();
    expect(screen.getByText(/My removed claim/)).toHaveTextContent("“My removed claim”");
    expect(screen.getByText("Reason given: Personal attack")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Request another look" })).toBeInTheDocument();
    expect(screen.queryByText("APPEAL PENDING")).not.toBeInTheDocument();
  });

  it("links the claim to the post page and has no action bar", () => {
    renderCard(MINE);
    expect(screen.getByRole("link", { name: /My removed claim/ })).toHaveAttribute(
      "href",
      `/p/${MINE.id}`,
    );
    expect(screen.queryByRole("button", { name: /Like|Repost|Report|Bookmark/ })).toBeNull();
  });

  it("uses the claim fonts: a fact in the headline face, an opinion in italics", () => {
    const { unmount } = renderCard(MINE);
    expect(screen.getByText(/My removed claim/).closest("blockquote")).toHaveClass(
      "font-claim-headline",
      "text-claim-headline",
    );
    unmount();
    renderCard({ ...MINE, post_type: "opinion" });
    expect(screen.getByText(/My removed claim/).closest("blockquote")).toHaveClass(
      "font-claim-opinion",
      "italic",
    );
  });

  it("has no 'Reason given' line when the moderator gave none", () => {
    renderCard({ ...MINE, removal_reason: "  " });
    expect(screen.queryByText(/Reason given/)).not.toBeInTheDocument();
  });

  it("shows the chip and the line instead of the button once an appeal is open", () => {
    renderCard({ ...MINE, can_appeal: false, appeal_status: "open" });
    expect(screen.getByText("APPEAL PENDING")).toBeInTheDocument();
    expect(
      screen.getByText(/A moderator who didn't make the first decision will review it/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).not.toBeInTheDocument();
  });

  it.each([
    ["upheld", "the post stays removed"],
    ["overturned", "reversed the decision"],
  ] as const)("says what became of the appeal: %s", (appeal_status, words) => {
    renderCard({ ...MINE, can_appeal: false, appeal_status });
    expect(screen.getByText(new RegExp(words))).toBeInTheDocument();
    expect(screen.queryByText("APPEAL PENDING")).not.toBeInTheDocument();
  });

  it("shows no button when the server says it can't be appealed", () => {
    renderCard({ ...MINE, can_appeal: false });
    expect(screen.queryByRole("button", { name: "Request another look" })).not.toBeInTheDocument();
  });

  it("shows a disabled button that explains itself when the email isn't verified", async () => {
    renderCard(MINE, "unverified");
    expect(await screen.findByRole("button", { name: "Request another look" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });
});

describe("RemovedPostCard: appealing from the card", () => {
  async function appeal(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: "Request another look" }));
    await user.click(screen.getByRole("button", { name: "Send request" }));
  }

  it("turns the button into the chip and the open line, and tells the caller", async () => {
    const user = userEvent.setup();
    const onFiled = vi.fn();
    renderCard(MINE, "verified", { onFiled });
    await appeal(user);
    expect(await screen.findByText("APPEAL PENDING")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).not.toBeInTheDocument();
    expect(screen.getByText(/will review it/)).toBeInTheDocument();
    expect(onFiled).toHaveBeenCalledWith(FILED);
  });

  it("keeps the chip when the list gives the card a new post object that doesn't know yet", async () => {
    const user = userEvent.setup();
    const view = renderCard(MINE);
    await appeal(user);
    expect(await screen.findByText("APPEAL PENDING")).toBeInTheDocument();
    // A poll builds a new object from the same stale data (`can_appeal` still true).
    view.rerender(<RemovedPostCard post={{ ...MINE }} now={NOW} />);
    expect(screen.getByText("APPEAL PENDING")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).not.toBeInTheDocument();
  });

  it("follows the server once its own copy knows the status", async () => {
    const user = userEvent.setup();
    const view = renderCard(MINE);
    await appeal(user);
    await screen.findByText("APPEAL PENDING");
    view.rerender(
      <RemovedPostCard post={{ ...MINE, can_appeal: false, appeal_status: "upheld" }} now={NOW} />,
    );
    expect(screen.queryByText("APPEAL PENDING")).not.toBeInTheDocument();
    expect(screen.getByText(/the post stays removed/)).toBeInTheDocument();
  });

  it("is only the one that was appealed: a different post's card is not affected", async () => {
    const user = userEvent.setup();
    const view = renderCard(MINE);
    await appeal(user);
    await screen.findByText("APPEAL PENDING");
    const other = { ...MINE, id: "22222222-2222-4222-8222-222222222222" };
    view.rerender(<RemovedPostCard post={other} now={NOW} />);
    expect(screen.queryByText("APPEAL PENDING")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request another look" })).toBeInTheDocument();
  });

  it("hides the button after 'already appealed' and tells the caller", async () => {
    const user = userEvent.setup();
    const onStale = vi.fn();
    api.appealPost.mockRejectedValue(
      new ApiError({ status: 409, code: "already_appealed", detail: "" }),
    );
    renderCard(MINE, "verified", { onStale });
    await appeal(user);
    expect(await screen.findByText(APPEAL_MESSAGES.already)).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Request another look" }),
      ).not.toBeInTheDocument(),
    );
    expect(onStale).toHaveBeenCalledTimes(1);
  });
});

describe("RemovedPostCard: the author, on the post page", () => {
  it("makes the claim the page's h1 and shows the type chip, the note, the reason and the footer", () => {
    renderCard(MINE, "verified", {
      layout: "page",
      authorRow: <p>The author row</p>,
      footer: <button type="button">Delete</button>,
    });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("“My removed claim”");
    expect(screen.getByText("FACT")).toBeInTheDocument();
    expect(screen.getByText("Removed")).toBeInTheDocument();
    expect(screen.getByText(REMOVED_MESSAGES.onlyYou)).toBeInTheDocument();
    expect(screen.getByText("Reason given: Personal attack")).toBeInTheDocument();
    expect(screen.getByText("The author row")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("shows the chip beside the type when an appeal is open, and no footer when none is given", () => {
    renderCard({ ...MINE, can_appeal: false, appeal_status: "open" }, "verified", {
      layout: "page",
    });
    expect(screen.getByText("APPEAL PENDING")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("renders the words as text, never as HTML", () => {
    renderCard({ ...MINE, content: "<img src=x onerror=alert(1)> **bold**" }, "verified", {
      layout: "page",
    });
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("<img src=x");
  });
});
