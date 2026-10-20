import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { CredibilityPanel } from "./CredibilityPanel";
import { CREDIBILITY_COPY } from "./ledger-copy";
import { makeEntry } from "./test-helpers";

const api = vi.hoisted(() => ({ fetchMyReputationEvents: vi.fn() }));
vi.mock("./reputation-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./reputation-api")>()),
  ...api,
}));

beforeEach(() => vi.clearAllMocks());

const page = (items = [makeEntry()], nextCursor: string | null = null) => ({ items, nextCursor });

async function setup(
  items = [makeEntry()],
  props: { publicScore?: number | null; defaultOpen?: boolean } = {},
) {
  api.fetchMyReputationEvents.mockResolvedValue(page(items));
  const view = renderWithSessionAndToast(
    <CredibilityPanel
      publicScore={"publicScore" in props ? props.publicScore! : 62}
      defaultOpen={props.defaultOpen}
    />,
    "verified",
  );
  await screen.findByText(/^Your score:/);
  return view;
}

describe("CredibilityPanel", () => {
  it("shows the real score from the newest row", async () => {
    await setup([makeEntry({ score_after: 58 }), makeEntry({ score_after: 61 })]);
    expect(screen.getByText("Your score: 58")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Your credibility score is 58 out of 100." }),
    ).toBeInTheDocument();
  });

  it("an empty ledger reads 50 and says there is no history yet", async () => {
    await setup([]);
    expect(screen.getByText("Your score: 50")).toBeInTheDocument();
    expect(screen.getByText(CREDIBILITY_COPY.emptyTitle)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /history/i })).not.toBeInTheDocument();
  });

  it("says what others see while the public score is hidden, and not otherwise", async () => {
    const hidden = await setup([makeEntry()], { publicScore: null });
    expect(
      screen.getByText("Others see New until 3 of your posts are checked."),
    ).toBeInTheDocument();
    hidden.unmount();
    await setup([makeEntry()], { publicScore: 62 });
    expect(screen.queryByText(/Others see New/)).not.toBeInTheDocument();
  });

  it("keeps the history folded until you open it, then lists the rows", async () => {
    const user = userEvent.setup();
    await setup([makeEntry({ label: "Fact verified true" })]);
    const toggle = screen.getByRole("button", { name: /Show history \(1\)/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Fact verified true")).not.toBeInTheDocument();
    await user.click(toggle);
    expect(screen.getByRole("button", { name: /Hide history/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText("Fact verified true")).toBeInTheDocument();
  });

  it("starts open with defaultOpen (Settings, Part 14)", async () => {
    await setup([makeEntry({ label: "Fact verified true" })], { defaultOpen: true });
    expect(screen.getByText("Fact verified true")).toBeInTheDocument();
  });

  it("a row shows its date, signed change, score after, and a link to the post", async () => {
    await setup(
      [
        makeEntry({
          label: "Fact labelled FALSE",
          positive: "0.00",
          negative: "1.00",
          score_after: 55,
          created_at: "2026-10-12T09:30:00Z",
          post_id: "11111111-1111-4111-8111-111111111111",
        }),
      ],
      { defaultOpen: true },
    );
    const row = screen.getByRole("listitem");
    expect(within(row).getByText("Oct 12, 2026")).toBeInTheDocument();
    expect(within(row).getByText("−1")).toBeInTheDocument();
    expect(within(row).getByText("score after 55")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "View post" })).toHaveAttribute(
      "href",
      "/p/11111111-1111-4111-8111-111111111111",
    );
  });

  it("a row without a post (deleted) has no link", async () => {
    await setup([makeEntry({ post_id: null })], { defaultOpen: true });
    expect(screen.queryByRole("link", { name: "View post" })).not.toBeInTheDocument();
  });

  it("marks a reversed row with a word and a strike-through; its reversal reads as a row", async () => {
    await setup(
      [
        makeEntry({
          kind: "reversal",
          label: "Reversed: Fact labelled FALSE",
          positive: "0.00",
          negative: "-1.00",
          reverses: "e-x",
        }),
        makeEntry({
          label: "Fact labelled FALSE",
          positive: "0.00",
          negative: "1.00",
          reversed: true,
        }),
      ],
      { defaultOpen: true },
    );
    const [reversal, original] = screen.getAllByRole("listitem");
    expect(within(original).getByText("Reversed")).toBeInTheDocument();
    expect(within(original).getByText("Fact labelled FALSE")).toHaveClass("line-through");
    expect(within(reversal).queryByText("Reversed")).not.toBeInTheDocument();
    expect(within(reversal).getByText("Reversed: Fact labelled FALSE")).not.toHaveClass(
      "line-through",
    );
    expect(within(reversal).getByText("+1")).toBeInTheDocument();
  });

  it("offers 'Ask for another look' on a negative row you can still appeal", async () => {
    await setup(
      [
        makeEntry({
          label: "Fact labelled FALSE",
          negative: "1.00",
          positive: "0.00",
          post_id: "22222222-2222-4222-8222-222222222222",
          appeal: { status: null, can_appeal: true },
        }),
      ],
      { defaultOpen: true },
    );
    expect(screen.getByRole("link", { name: "Ask for another look" })).toHaveAttribute(
      "href",
      "/p/22222222-2222-4222-8222-222222222222",
    );
  });

  it.each([
    ["open", "Appeal open"],
    ["upheld", "Appeal upheld — the decision stands"],
    ["overturned", "Appeal overturned"],
  ] as const)("an existing %s appeal reads as words, not a link", async (status, words) => {
    await setup(
      [makeEntry({ negative: "1.00", positive: "0.00", appeal: { status, can_appeal: false } })],
      {
        defaultOpen: true,
      },
    );
    expect(screen.getByText(words)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ask for another look" })).not.toBeInTheDocument();
  });

  it("no appeal link on positive rows, or when the post is gone", async () => {
    await setup(
      [
        makeEntry({ label: "Fact verified true" }),
        makeEntry({
          label: "Fact labelled FALSE",
          post_id: null,
          appeal: { status: null, can_appeal: true },
        }),
      ],
      { defaultOpen: true },
    );
    expect(screen.queryByRole("link", { name: "Ask for another look" })).not.toBeInTheDocument();
  });

  it("loads more rows and ends with a note", async () => {
    const user = userEvent.setup();
    api.fetchMyReputationEvents
      .mockResolvedValueOnce(page([makeEntry({ label: "First row" })], "next-1"))
      .mockResolvedValueOnce(page([makeEntry({ label: "Second row" })], null));
    renderWithSessionAndToast(<CredibilityPanel publicScore={62} defaultOpen />, "verified");
    await screen.findByText("First row");
    expect(screen.getByRole("button", { name: /Hide history \(1\+\)/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Second row")).toBeInTheDocument();
    expect(api.fetchMyReputationEvents).toHaveBeenLastCalledWith("next-1", expect.any(AbortSignal));
    expect(screen.getByText(CREDIBILITY_COPY.end)).toBeInTheDocument();
  });

  it("shows an alert with Try again when the first page fails", async () => {
    const user = userEvent.setup();
    api.fetchMyReputationEvents.mockRejectedValueOnce(
      new ApiError({ status: 500, code: "server_error", detail: "boom" }),
    );
    renderWithSessionAndToast(<CredibilityPanel publicScore={62} />, "verified");
    expect(await screen.findByText(CREDIBILITY_COPY.loadFailed)).toBeInTheDocument();
    api.fetchMyReputationEvents.mockResolvedValueOnce(page());
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/^Your score:/)).toBeInTheDocument();
  });

  it("makes no request for a visitor", async () => {
    renderWithSessionAndToast(<CredibilityPanel publicScore={62} />, "anonymous");
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Your credibility history" })).toBeInTheDocument(),
    );
    expect(api.fetchMyReputationEvents).not.toHaveBeenCalled();
  });
});
