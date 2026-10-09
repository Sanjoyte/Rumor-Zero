import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { FactQuota } from "@/lib/api/types";
import { ComposerModal, type ComposerModalProps, type ComposerSubmit } from "./ComposerModal";
import { type Draft, emptyDraft, newRow } from "./draft";
import type { ComposerFailure } from "./messages";
import { makeQuota } from "./test-helpers";

const NOW = new Date("2026-10-08T12:00:00Z");

type Overrides = Partial<
  Pick<ComposerModalProps, "submitting" | "failure" | "verified" | "open" | "onClose">
> & {
  draft?: Draft;
  quota?: FactQuota | null;
  onSubmit?: ComposerModalProps["onSubmit"];
};

/** Stands in for the provider: it owns the draft and answers `onSubmit`. */
function Harness({ draft: initial, onSubmit, quota = makeQuota(), ...rest }: Overrides) {
  const [draft, setDraft] = useState(initial ?? emptyDraft());
  return (
    <ComposerModal
      open
      onClose={() => {}}
      submitting={false}
      failure={null}
      verified
      onSubmit={onSubmit ?? (async () => null)}
      {...rest}
      draft={draft}
      onDraftChange={(patch) => setDraft((d) => ({ ...d, ...patch }))}
      quota={quota}
      now={NOW}
      timeZone="UTC"
    />
  );
}

const noFailure = async () => null;

function setup(overrides: Overrides = {}) {
  const onSubmit = vi.fn<ComposerModalProps["onSubmit"]>(overrides.onSubmit ?? noFailure);
  const view = render(<Harness {...overrides} onSubmit={onSubmit} />);
  return { onSubmit, ...view };
}

const text = () => screen.getByRole("textbox", { name: "Post text" });
const submitButton = () => screen.getByRole("button", { name: /^Post(\b|ing)/ });
const typeFact = () => userEvent.click(screen.getByRole("radio", { name: "Fact" }));
const typeOpinion = () => userEvent.click(screen.getByRole("radio", { name: "Opinion" }));
const sourceInputs = () => screen.queryAllByRole("textbox", { name: /^Source \d/ });
const lastPayload = (onSubmit: ReturnType<typeof setup>["onSubmit"]): ComposerSubmit =>
  onSubmit.mock.calls.at(-1)![0];

describe("ComposerModal: the form", () => {
  it("opens on the text box with nothing chosen", () => {
    setup();
    expect(screen.getByRole("dialog", { name: "New post" })).toBeInTheDocument();
    expect(text()).toHaveFocus();
    expect(screen.getByText("Choose one to continue")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Opinion" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Fact" })).not.toBeChecked();
  });

  it("renders nothing inside while it is closed", () => {
    setup({ open: false });
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("shows the draft it is given", () => {
    setup({ draft: { content: "Half written", postType: "opinion", rows: [newRow()] } });
    expect(text()).toHaveValue("Half written");
    expect(screen.getByRole("radio", { name: "Opinion" })).toBeChecked();
  });

  it("counts characters up to 500", async () => {
    setup();
    expect(screen.getByText("0 / 500 characters")).toBeInTheDocument();
    await userEvent.type(text(), "Hello");
    expect(screen.getByText("5 / 500 characters")).toBeInTheDocument();
  });

  it("just says Post until a type is chosen", () => {
    setup();
    expect(screen.getByRole("button", { name: "Post" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Post opinion" })).toBeNull();
  });

  it("closes from Cancel", async () => {
    const onClose = vi.fn();
    setup({ onClose });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("has no source field for an opinion, and one for a fact", async () => {
    setup();
    await typeOpinion();
    expect(sourceInputs()).toHaveLength(0);
    expect(screen.getByText("Opinions are published at once")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Post opinion" })).toBeInTheDocument();
    await typeFact();
    expect(sourceInputs()).toHaveLength(1);
    expect(screen.getByText("DOI preferred")).toBeInTheDocument();
    expect(screen.getByText("Fact posts are checked after you post")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Post fact, will be checked" })).toBeInTheDocument();
  });
});

describe("ComposerModal: client validation", () => {
  it("blocks an empty post and a missing type, shows both, and focuses the text", async () => {
    const { onSubmit } = setup();
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Write something first.")).toBeInTheDocument();
    expect(screen.getByText("Choose Opinion or Fact.")).toBeInTheDocument();
    expect(text()).toHaveFocus();
    expect(text()).toHaveAttribute("aria-invalid", "true");
  });

  it("focuses the type choice when only the type is missing", async () => {
    const { onSubmit } = setup();
    await userEvent.type(text(), "Something to say");
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Choose Opinion or Fact.")).toBeInTheDocument();
    expect(screen.getAllByRole("radio")[0]).toHaveFocus();
  });

  it("treats whitespace-only text as empty", async () => {
    const { onSubmit } = setup();
    await typeOpinion();
    await userEvent.type(text(), "  \n  ");
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Write something first.")).toBeInTheDocument();
  });

  it("blocks more than 500 characters, counting an emoji as one", async () => {
    const { onSubmit } = setup({
      draft: { content: "\u{1F600}".repeat(501), postType: "opinion", rows: [newRow()] },
    });
    expect(screen.getByText("501 / 500 characters")).toHaveClass("text-error");
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Keep it to 500 characters.")).toBeInTheDocument();
  });

  it("allows exactly 500 emoji", async () => {
    const { onSubmit } = setup({
      draft: { content: "\u{1F600}".repeat(500), postType: "opinion", rows: [newRow()] },
    });
    await userEvent.click(submitButton());
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("clears an error as soon as the field is fixed", async () => {
    setup();
    await userEvent.click(submitButton());
    await userEvent.type(text(), "Now there is text");
    expect(screen.queryByText("Write something first.")).toBeNull();
    await typeOpinion();
    expect(screen.queryByText("Choose Opinion or Fact.")).toBeNull();
  });
});

describe("ComposerModal: sending", () => {
  it("sends an opinion without sources", async () => {
    const { onSubmit } = setup();
    await typeOpinion();
    await userEvent.type(text(), "  Rain is nice  ");
    await userEvent.click(submitButton());
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(lastPayload(onSubmit)).toEqual({
      content: "Rain is nice",
      postType: "opinion",
      sources: [],
      rowIds: [],
    });
  });

  it("sends a fact with no sources at all", async () => {
    const { onSubmit } = setup();
    await typeFact();
    await userEvent.type(text(), "Water boils at 100C");
    await userEvent.click(submitButton());
    expect(lastPayload(onSubmit)).toMatchObject({ postType: "fact", sources: [] });
  });

  it("sends normalised sources in order and drops the empty rows", async () => {
    const rows = [newRow("HTTPS://Example.org/a"), newRow(""), newRow("doi:10.1000/xyz")];
    const { onSubmit } = setup({ draft: { content: "Claim", postType: "fact", rows } });
    await userEvent.click(submitButton());
    expect(lastPayload(onSubmit)).toEqual({
      content: "Claim",
      postType: "fact",
      sources: ["https://example.org/a", "10.1000/xyz"],
      rowIds: [rows[0].id, rows[2].id],
    });
  });

  it("does not send the sources of a fact that was switched to an opinion", async () => {
    const rows = [newRow("10.1000/xyz")];
    const { onSubmit } = setup({ draft: { content: "Claim", postType: "fact", rows } });
    await typeOpinion();
    await userEvent.click(submitButton());
    expect(lastPayload(onSubmit)).toMatchObject({ postType: "opinion", sources: [] });
  });

  it("shows Posting… and locks the form while the post is on its way", () => {
    setup({
      submitting: true,
      draft: { content: "Claim", postType: "fact", rows: [newRow("10.1000/xyz")] },
    });
    const button = screen.getByRole("button", { name: /Posting/ });
    expect(button).toBeDisabled();
    expect(text()).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Opinion" })).toBeDisabled();
    expect(sourceInputs()[0]).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add another source" })).toBeDisabled();
  });
});

describe("ComposerModal: source rows", () => {
  const withFact = (rows = [newRow()]) =>
    setup({ draft: { content: "Claim", postType: "fact", rows } });

  it("adds rows up to five, then the button goes away", async () => {
    withFact();
    for (let n = 2; n <= 5; n += 1) {
      await userEvent.click(screen.getByRole("button", { name: "Add another source" }));
      expect(sourceInputs()).toHaveLength(n);
    }
    expect(screen.queryByRole("button", { name: "Add another source" })).toBeNull();
  });

  it("focuses a new row", async () => {
    withFact();
    await userEvent.click(screen.getByRole("button", { name: "Add another source" }));
    await waitFor(() => expect(sourceInputs()[1]).toHaveFocus());
  });

  it("has no remove button on the first row, and one on each extra row", () => {
    withFact([newRow("a"), newRow("b"), newRow("c")]);
    expect(screen.queryByRole("button", { name: "Remove source 1" })).toBeNull();
    expect(screen.getByRole("button", { name: "Remove source 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove source 3" })).toBeInTheDocument();
  });

  it("removes a row and moves focus to the one before it", async () => {
    withFact([
      newRow("https://a.example/"),
      newRow("https://b.example/"),
      newRow("https://c.example/"),
    ]);
    await userEvent.click(screen.getByRole("button", { name: "Remove source 2" }));
    expect(sourceInputs().map((i) => (i as HTMLInputElement).value)).toEqual([
      "https://a.example/",
      "https://c.example/",
    ]);
    await waitFor(() => expect(sourceInputs()[0]).toHaveFocus());
  });

  it("brings the add button back after removing a row at the limit", async () => {
    withFact([newRow("a"), newRow("b"), newRow("c"), newRow("d"), newRow("e")]);
    expect(screen.queryByRole("button", { name: "Add another source" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Remove source 5" }));
    expect(screen.getByRole("button", { name: "Add another source" })).toBeInTheDocument();
  });

  it.each([
    ["javascript:alert(1)", /starts with https:\/\//],
    ["data:text/html,hi", /starts with https:\/\//],
    ["https://user:pw@example.org/", /username or password/],
    ["http://127.0.0.1/", /IP addresses and localhost/],
    ["https://localhost:3000/", /IP addresses and localhost/],
    ["doi:abc", /doesn't look like a DOI/],
    ["10.12/x", /doesn't look like a DOI/],
  ])("flags %s when the field is left", async (value, message) => {
    withFact();
    await userEvent.type(sourceInputs()[0], value);
    await userEvent.tab();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(sourceInputs()[0]).toHaveAttribute("aria-invalid", "true");
  });

  it("accepts a DOI and a URL without a word", async () => {
    withFact();
    await userEvent.type(sourceInputs()[0], "doi:10.1000/xyz");
    await userEvent.tab();
    expect(sourceInputs()[0]).not.toHaveAttribute("aria-invalid");
  });

  it("does not complain about an empty row when it is left", async () => {
    withFact();
    await userEvent.click(sourceInputs()[0]);
    await userEvent.tab();
    expect(sourceInputs()[0]).not.toHaveAttribute("aria-invalid");
  });

  it("clears a row's error when it is edited", async () => {
    withFact();
    await userEvent.type(sourceInputs()[0], "nope");
    await userEvent.tab();
    expect(sourceInputs()[0]).toHaveAttribute("aria-invalid", "true");
    await userEvent.type(sourceInputs()[0], "x");
    expect(sourceInputs()[0]).not.toHaveAttribute("aria-invalid");
  });

  it("refuses a repeat on the later row, even across kinds, and does not send", async () => {
    const { onSubmit } = setup({
      draft: {
        content: "Claim",
        postType: "fact",
        rows: [newRow("doi:10.1000/xyz"), newRow("https://doi.org/10.1000/XYZ")],
      },
    });
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Same as source 1.")).toBeInTheDocument();
    expect(sourceInputs()[1]).toHaveFocus();
  });

  it("refuses to send while a source is bad, and focuses it", async () => {
    const { onSubmit } = setup({
      draft: {
        content: "Claim",
        postType: "fact",
        rows: [newRow("10.1000/ok"), newRow("javascript:x")],
      },
    });
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(sourceInputs()[1]).toHaveFocus();
    expect(sourceInputs()[0]).not.toHaveAttribute("aria-invalid");
  });
});

describe("ComposerModal: what the server says", () => {
  const fieldsFailure = (fields: Partial<ComposerFailure["fields"]>): ComposerFailure => ({
    kind: "fields",
    message: "Fix the highlighted fields and try again.",
    fields: { sourceRows: {}, ...fields },
  });

  it("puts a source error on the right row even when an empty row was dropped", async () => {
    const rows = [newRow("https://a.example/"), newRow(""), newRow("https://b.example/")];
    const { onSubmit } = setup({
      draft: { content: "Claim", postType: "fact", rows },
      onSubmit: async () => fieldsFailure({ sourceRows: { 1: "Server says no." } }),
    });
    await userEvent.click(submitButton());
    expect(lastPayload(onSubmit).rowIds).toEqual([rows[0].id, rows[2].id]);
    await screen.findByText("Server says no.");
    // Sent index 1 is the third row (the empty second one was dropped).
    expect(sourceInputs()[2]).toHaveAttribute("aria-invalid", "true");
    expect(sourceInputs()[1]).not.toHaveAttribute("aria-invalid");
    expect(sourceInputs()[2]).toHaveFocus();
    expect(screen.getByText("Fix the highlighted fields and try again.")).toBeInTheDocument();
  });

  it("shows a content error from the server under the text", async () => {
    setup({
      draft: { content: "Claim", postType: "opinion", rows: [newRow()] },
      onSubmit: async () => fieldsFailure({ content: "Keep it to 500 characters." }),
    });
    await userEvent.click(submitButton());
    await screen.findByText("Keep it to 500 characters.");
    expect(text()).toHaveAttribute("aria-invalid", "true");
  });

  it("shows the list-level source error", async () => {
    setup({
      draft: { content: "Claim", postType: "fact", rows: [newRow("10.1000/a")] },
      onSubmit: async () => fieldsFailure({ sources: "You can add up to 5 sources." }),
    });
    await userEvent.click(submitButton());
    expect(await screen.findAllByText("You can add up to 5 sources.")).not.toHaveLength(0);
  });

  it("drops the 'fix the fields' banner once every field is fixed", async () => {
    setup({
      draft: { content: "Claim", postType: "opinion", rows: [newRow()] },
      onSubmit: async () => fieldsFailure({ content: "Write something first." }),
    });
    await userEvent.click(submitButton());
    await screen.findByText("Fix the highlighted fields and try again.");
    await userEvent.type(text(), "!");
    expect(screen.queryByText("Fix the highlighted fields and try again.")).toBeNull();
  });

  it("shows a banner for a failure that isn't about a field", () => {
    const failure: ComposerFailure = {
      kind: "throttled",
      message: "You're posting too fast. Try again in about 10 minutes.",
      fields: { sourceRows: {} },
    };
    setup({ failure });
    expect(screen.getByRole("alert")).toHaveTextContent("You're posting too fast.");
  });

  it("clears old errors after a successful answer", async () => {
    setup({ draft: { content: "Claim", postType: "opinion", rows: [newRow()] } });
    await userEvent.click(submitButton());
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("ComposerModal: the fact allowance", () => {
  it("shows how many fact posts are left", () => {
    setup({ quota: makeQuota({ remaining: 7 }) });
    expect(screen.getByText("7/10", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/fact posts left/)).toBeInTheDocument();
  });

  it("shows when the next one frees up once none are left", () => {
    setup({
      quota: makeQuota({ used: 10, remaining: 0, next_slot_at: "2026-10-08T14:05:00Z" }),
    });
    expect(screen.getByText(/fact posts left · next at 2:05 PM/)).toBeInTheDocument();
  });

  it("says fact posts are paused when the limit is 0", () => {
    setup({ quota: makeQuota({ limit: 0, used: 0, remaining: 0 }) });
    expect(screen.getByText("Fact posts are paused right now")).toBeInTheDocument();
  });

  it("hides the line when the allowance is unknown", () => {
    setup({ quota: null });
    expect(screen.queryByText(/fact posts left/)).toBeNull();
  });

  it("doesn't send a fact post that is sure to be refused, and says why", async () => {
    const { onSubmit } = setup({
      draft: { content: "Claim", postType: "fact", rows: [newRow()] },
      quota: makeQuota({ used: 10, remaining: 0, next_slot_at: "2026-10-08T14:05:00Z" }),
    });
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "You've used all 10 of your fact posts for the last 24 hours. You can post another next at 2:05 PM.",
    );
  });

  it("says posting is paused instead of sending when the limit is 0", async () => {
    const { onSubmit } = setup({
      draft: { content: "Claim", postType: "fact", rows: [newRow()] },
      quota: makeQuota({ limit: 0, used: 0, remaining: 0 }),
    });
    await userEvent.click(submitButton());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Fact posts are paused right now.");
  });

  it("still sends an opinion when no fact posts are left", async () => {
    const { onSubmit } = setup({
      draft: { content: "My view", postType: "opinion", rows: [newRow()] },
      quota: makeQuota({ used: 10, remaining: 0 }),
    });
    await userEvent.click(submitButton());
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("lets the server decide when the allowance is unknown", async () => {
    const { onSubmit } = setup({
      draft: { content: "Claim", postType: "fact", rows: [newRow()] },
      quota: null,
    });
    await userEvent.click(submitButton());
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("drops the allowance notice when the type changes to Opinion", async () => {
    setup({
      draft: { content: "Claim", postType: "fact", rows: [newRow()] },
      quota: makeQuota({ used: 10, remaining: 0 }),
    });
    await userEvent.click(submitButton());
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await typeOpinion();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("ComposerModal: an unverified user", () => {
  it("explains why and locks the form", () => {
    setup({ verified: false });
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Verify your email to post")).toBeInTheDocument();
    expect(text()).toBeDisabled();
    expect(screen.getByRole("button", { name: /Post/ })).toBeDisabled();
  });

  it("switches to the same state when the server says the email isn't verified", () => {
    setup({
      failure: {
        kind: "unverified",
        message: "Verify your email to post.",
        fields: { sourceRows: {} },
      },
    });
    expect(screen.getByText("Verify your email to post")).toBeInTheDocument();
    expect(text()).toBeDisabled();
  });
});
