import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useComposer } from "./ComposerProvider";
import {
  VERIFIED_ME,
  makePost,
  makeQuota,
  renderWithComposer,
  type SessionKind,
} from "./test-helpers";

const api = vi.hoisted(() => ({
  createPost: vi.fn(),
  fetchFactQuota: vi.fn(),
}));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/home",
}));

function Probe({ onPosted }: { onPosted?: (post: Post) => void }) {
  const composer = useComposer();
  const { status } = useAuth();
  const [listening, setListening] = useState(true);
  useEffect(
    () => (onPosted && listening ? composer.onPosted(onPosted) : undefined),
    [composer, onPosted, listening],
  );
  return (
    <>
      <p data-testid="status">{status}</p>
      <button onClick={composer.open}>Open composer</button>
      <button onClick={() => setListening(false)}>Stop listening</button>
    </>
  );
}

async function renderProbe(kind: SessionKind = "verified", onPosted?: (post: Post) => void) {
  const view = renderWithComposer(<Probe onPosted={onPosted} />, kind);
  if (kind !== "loading") {
    await waitFor(() => expect(screen.getByTestId("status")).not.toHaveTextContent("loading"));
  }
  return view;
}

const open = () => userEvent.click(screen.getByRole("button", { name: "Open composer" }));
const dialog = () => screen.queryByRole("dialog", { name: "New post" });
const text = () => screen.getByRole("textbox", { name: "Post text" });
const choose = (name: "Opinion" | "Fact") => userEvent.click(screen.getByRole("radio", { name }));
const post = () => userEvent.click(screen.getByRole("button", { name: /^Post (opinion|fact)/ }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  api.createPost.mockReset();
  api.fetchFactQuota.mockReset();
  api.fetchFactQuota.mockResolvedValue(makeQuota());
  push.mockClear();
  window.history.pushState({}, "", "/home");
});

describe("ComposerProvider: opening", () => {
  it("opens the composer for a verified user and loads the allowance", async () => {
    await renderProbe("verified");
    await open();
    expect(dialog()).toBeInTheDocument();
    expect(api.fetchFactQuota).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/fact posts left/)).toBeInTheDocument();
    expect(screen.getByText("7/10", { exact: false })).toBeInTheDocument();
  });

  it("tells an unverified user to verify, and opens nothing", async () => {
    await renderProbe("unverified");
    await open();
    expect(dialog()).toBeNull();
    expect(
      await screen.findByText(/Verify your email to post\. Check your inbox/),
    ).toBeInTheDocument();
    expect(api.fetchFactQuota).not.toHaveBeenCalled();
  });

  it("sends a visitor to log in, and back to where they were", async () => {
    window.history.pushState({}, "", "/home?x=1");
    await renderProbe("anonymous");
    await open();
    expect(dialog()).toBeNull();
    expect(push).toHaveBeenCalledWith("/login?next=%2Fhome%3Fx%3D1");
  });

  it("does nothing while the session is still being restored", async () => {
    await renderProbe("loading");
    await open();
    expect(dialog()).toBeNull();
    expect(push).not.toHaveBeenCalled();
  });

  it("still opens when the allowance can't be loaded (the server decides)", async () => {
    api.fetchFactQuota.mockRejectedValue(new Error("offline"));
    await renderProbe("verified");
    await open();
    expect(dialog()).toBeInTheDocument();
    expect(screen.queryByText(/fact posts left/)).toBeNull();
  });
});

describe("ComposerProvider: posting (insert on success)", () => {
  it("posts an opinion, closes, tells listeners and toasts", async () => {
    const created = makePost({ id: "p-1", content: "Rain is nice" });
    api.createPost.mockResolvedValue(created);
    const onPosted = vi.fn();
    await renderProbe("verified", onPosted);
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "Rain is nice");
    await post();
    expect(api.createPost).toHaveBeenCalledWith({ content: "Rain is nice", post_type: "opinion" });
    await waitFor(() => expect(dialog()).toBeNull());
    expect(onPosted).toHaveBeenCalledWith(created);
    expect(await screen.findByText("Posted.")).toBeInTheDocument();
  });

  it("posts a fact with its sources in order, and refreshes the allowance", async () => {
    api.createPost.mockResolvedValue(makePost({ post_type: "fact", status: "pending" }));
    await renderProbe();
    await open();
    await choose("Fact");
    await userEvent.type(text(), "Water boils at 100C");
    await userEvent.type(screen.getByRole("textbox", { name: "Source 1" }), "doi:10.1000/xyz");
    await userEvent.click(screen.getByRole("button", { name: "Add another source" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Source 2" }),
      "https://Example.org/report",
    );
    await post();
    expect(api.createPost).toHaveBeenCalledWith({
      content: "Water boils at 100C",
      post_type: "fact",
      sources: ["10.1000/xyz", "https://example.org/report"],
    });
    expect(await screen.findByText("Posted. Checking the facts…")).toBeInTheDocument();
    await waitFor(() => expect(api.fetchFactQuota).toHaveBeenCalledTimes(2));
  });

  it("shows Posting… until the answer arrives, then closes", async () => {
    const pending = deferred<Post>();
    api.createPost.mockReturnValue(pending.promise);
    await renderProbe();
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "Hello");
    await post();
    expect(screen.getByRole("button", { name: /Posting/ })).toBeDisabled();
    expect(dialog()).toBeInTheDocument();
    await act(async () => pending.resolve(makePost()));
    await waitFor(() => expect(dialog()).toBeNull());
  });

  it("clears the draft after a successful post", async () => {
    api.createPost.mockResolvedValue(makePost());
    await renderProbe();
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "Hello");
    await post();
    await waitFor(() => expect(dialog()).toBeNull());
    await open();
    expect(text()).toHaveValue("");
    expect(screen.getByRole("radio", { name: "Opinion" })).not.toBeChecked();
  });

  it("stops telling a listener once it has unsubscribed", async () => {
    api.createPost.mockResolvedValue(makePost());
    const onPosted = vi.fn();
    await renderProbe("verified", onPosted);
    await userEvent.click(screen.getByRole("button", { name: "Stop listening" }));
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "Hello");
    await post();
    await waitFor(() => expect(dialog()).toBeNull());
    expect(onPosted).not.toHaveBeenCalled();
  });
});

describe("ComposerProvider: when it fails", () => {
  async function fillOpinion() {
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "Hello there");
  }

  it("keeps the draft and shows the server's quota message in the composer", async () => {
    api.createPost.mockRejectedValue(
      new ApiError({
        status: 429,
        code: "fact_quota_exceeded",
        detail: "You've used all 10 of your fact posts for the last 24 hours.",
        retryAfter: 600,
      }),
    );
    await renderProbe();
    await open();
    await choose("Fact");
    await userEvent.type(text(), "A claim");
    await post();
    expect(await screen.findByRole("alert")).toHaveTextContent("all 10 of your fact posts");
    expect(dialog()).toBeInTheDocument();
    expect(text()).toHaveValue("A claim");
    await waitFor(() => expect(api.fetchFactQuota).toHaveBeenCalledTimes(2)); // the line refreshes
  });

  it("says the throttle is the throttle", async () => {
    api.createPost.mockRejectedValue(
      new ApiError({ status: 429, code: "throttled", detail: "x", retryAfter: 1200 }),
    );
    await renderProbe();
    await fillOpinion();
    await post();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You're posting too fast. Try again in about 20 minutes.",
    );
  });

  it("puts a server field error on its row", async () => {
    api.createPost.mockRejectedValue(
      new ApiError({
        status: 400,
        code: "invalid",
        detail: "x",
        fieldErrors: { "sources.0": ["That source isn't allowed."] },
      }),
    );
    await renderProbe();
    await open();
    await choose("Fact");
    await userEvent.type(text(), "A claim");
    await userEvent.type(screen.getByRole("textbox", { name: "Source 1" }), "https://a.example/");
    await post();
    expect(await screen.findByText("That source isn't allowed.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Source 1" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("can be tried again after a failure", async () => {
    api.createPost
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }))
      .mockResolvedValueOnce(makePost());
    await renderProbe();
    await fillOpinion();
    await post();
    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach Rumor Zero");
    await post();
    await waitFor(() => expect(dialog()).toBeNull());
    expect(api.createPost).toHaveBeenCalledTimes(2);
  });

  it("switches to the verify state on a 403 and reloads the account", async () => {
    api.createPost.mockRejectedValue(
      new ApiError({ status: 403, code: "email_unverified", detail: "x" }),
    );
    const view = await renderProbe();
    const fetchMeCalls = view.api.fetchMe.mock.calls.length;
    await fillOpinion();
    await post();
    expect(await screen.findByText("Verify your email to post")).toBeInTheDocument();
    expect(text()).toBeDisabled();
    await waitFor(() => expect(view.api.fetchMe.mock.calls.length).toBeGreaterThan(fetchMeCalls));
  });
});

describe("ComposerProvider: the draft and closing", () => {
  it("keeps the draft when the composer is closed with Cancel", async () => {
    await renderProbe();
    await open();
    await choose("Fact");
    await userEvent.type(text(), "Unfinished thought");
    await userEvent.type(screen.getByRole("textbox", { name: "Source 1" }), "10.1000/xyz");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(dialog()).toBeNull();
    await open();
    expect(text()).toHaveValue("Unfinished thought");
    expect(screen.getByRole("radio", { name: "Fact" })).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Source 1" })).toHaveValue("10.1000/xyz");
  });

  it("keeps the draft when it is closed with Escape", async () => {
    await renderProbe();
    await open();
    await userEvent.type(text(), "Unfinished");
    await userEvent.keyboard("{Escape}");
    expect(dialog()).toBeNull();
    await open();
    expect(text()).toHaveValue("Unfinished");
  });

  it("still finishes the post when the modal is closed while it is sending", async () => {
    const pending = deferred<Post>();
    api.createPost.mockReturnValue(pending.promise);
    const created = makePost({ id: "late" });
    const onPosted = vi.fn();
    await renderProbe("verified", onPosted);
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "On its way");
    await post();
    await userEvent.click(screen.getByRole("button", { name: "Close" })); // × stays usable while sending
    expect(dialog()).toBeNull();
    await act(async () => pending.resolve(created));
    expect(onPosted).toHaveBeenCalledWith(created);
    expect(await screen.findByText("Posted.")).toBeInTheDocument();
    await open();
    expect(text()).toHaveValue(""); // sent, so cleared
  });

  it("keeps the draft and says so when a post fails after the modal was closed", async () => {
    const pending = deferred<Post>();
    api.createPost.mockReturnValue(pending.promise);
    await renderProbe();
    await open();
    await choose("Opinion");
    await userEvent.type(text(), "Keep me");
    await post();
    await userEvent.click(screen.getByRole("button", { name: "Close" })); // × stays usable while sending
    await act(async () =>
      pending.reject(new ApiError({ status: 0, code: "network_error", detail: "x" })),
    );
    expect(await screen.findByText(/Can't reach Rumor Zero/)).toBeInTheDocument();
    await open();
    expect(text()).toHaveValue("Keep me");
    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach Rumor Zero");
  });

  it("does not hand one person's draft to the next one", async () => {
    const view = await renderProbe("verified");
    await open();
    await userEvent.type(text(), "Private words");
    await userEvent.keyboard("{Escape}");
    // Another account signs in (a logout, then a different user).
    view.api.fetchMe.mockResolvedValue({ ...VERIFIED_ME, id: "u-2", username: "bo" });
    await act(async () => {
      await view.session.logout();
      await view.session.signInWithToken("another-token");
    });
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    await open();
    expect(text()).toHaveValue("");
  });

  it("closes an open composer when the user logs out", async () => {
    const view = await renderProbe();
    await open();
    expect(dialog()).toBeInTheDocument();
    await act(async () => view.session.logout());
    await waitFor(() => expect(dialog()).toBeNull());
  });
});

describe("ComposerProvider: emergency posts (Part 11C)", () => {
  const emergencyToggle = () => screen.getByRole("switch", { name: "Emergency post" });

  async function openFact(content = "Gas leak on Main Street") {
    await renderProbe();
    await open();
    await choose("Fact");
    await userEvent.type(text(), content);
    await waitFor(() => expect(emergencyToggle()).toBeEnabled());
  }

  it("sends is_emergency, says it's pinned, and tells listeners", async () => {
    const created = makePost({
      post_type: "fact",
      status: "pending",
      is_emergency: true,
      emergency_active: true,
    });
    api.createPost.mockResolvedValue(created);
    await openFact();
    await userEvent.click(emergencyToggle());
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand/ }));
    await userEvent.click(screen.getByRole("button", { name: "Post emergency, will be checked" }));
    await waitFor(() => expect(dialog()).toBeNull());
    expect(api.createPost).toHaveBeenCalledWith({
      content: "Gas leak on Main Street",
      post_type: "fact",
      sources: [],
      is_emergency: true,
    });
    expect(await screen.findByText("Posted. It's pinned while it's checked.")).toBeInTheDocument();
  });

  it("sends no is_emergency for a plain fact", async () => {
    api.createPost.mockResolvedValue(makePost({ post_type: "fact", status: "pending" }));
    await openFact();
    await post();
    await waitFor(() => expect(api.createPost).toHaveBeenCalled());
    expect(api.createPost.mock.calls[0][0]).not.toHaveProperty("is_emergency");
  });

  it("turns the toggle off when switching to Opinion", async () => {
    await openFact();
    await userEvent.click(emergencyToggle());
    await choose("Opinion");
    await choose("Fact");
    expect(emergencyToggle()).not.toBeChecked();
  });

  it("shows the server's refusal, keeps the text and turns the toggle off with its reason", async () => {
    api.createPost.mockRejectedValue(
      new ApiError({
        status: 403,
        code: "emergency_not_allowed",
        detail: "Emergency posting is blocked on your account until Nov 7, 2026 at 12:00 UTC.",
      }),
    );
    await openFact();
    api.fetchFactQuota.mockResolvedValue(
      makeQuota({
        emergency: {
          allowed: false,
          reason: "blocked",
          next_allowed_at: "2026-11-07T12:00:00Z",
          block_days: 30,
        },
      }),
    );
    await userEvent.click(emergencyToggle());
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand/ }));
    await userEvent.click(screen.getByRole("button", { name: "Post emergency, will be checked" }));
    expect(
      await screen.findByText(
        "Emergency posting is blocked on your account until Nov 7, 2026 at 12:00 UTC.",
      ),
    ).toBeInTheDocument();
    expect(dialog()).not.toBeNull();
    expect(text()).toHaveValue("Gas leak on Main Street");
    await waitFor(() => expect(emergencyToggle()).toBeDisabled());
    expect(emergencyToggle()).not.toBeChecked();
    expect(emergencyToggle()).toHaveAccessibleDescription(
      "Emergency posting is blocked on your account until Nov 7, 2026.",
    );
    expect(api.fetchFactQuota).toHaveBeenCalledTimes(2);
  });

  it("turns a draft's toggle off when a reopened allowance says no", async () => {
    await openFact();
    await userEvent.click(emergencyToggle());
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    api.fetchFactQuota.mockResolvedValue(
      makeQuota({
        emergency: {
          allowed: false,
          reason: "daily_limit",
          next_allowed_at: null,
          block_days: 30,
        },
      }),
    );
    await open();
    await waitFor(() => expect(emergencyToggle()).toBeDisabled());
    expect(emergencyToggle()).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Post fact, will be checked" })).toBeVisible();
  });

  it("keeps the toggle and the tick off when the allowance says yes again later", async () => {
    await openFact();
    await userEvent.click(emergencyToggle());
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand/ }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    const no = makeQuota({
      emergency: { allowed: false, reason: "daily_limit", next_allowed_at: null, block_days: 30 },
    });
    api.fetchFactQuota.mockResolvedValue(no);
    await open();
    await waitFor(() => expect(emergencyToggle()).toBeDisabled());
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    api.fetchFactQuota.mockResolvedValue(makeQuota());
    await open();
    await waitFor(() => expect(emergencyToggle()).toBeEnabled());
    // Never back on by itself, and never sent unconfirmed: the person chooses again.
    expect(emergencyToggle()).not.toBeChecked();
    await userEvent.click(emergencyToggle());
    expect(screen.getByRole("checkbox", { name: /I understand/ })).not.toBeChecked();
  });

  it("turns the toggle off after a refusal even when the refreshed allowance still says yes", async () => {
    api.createPost.mockRejectedValue(
      new ApiError({
        status: 403,
        code: "emergency_not_allowed",
        detail: "You've posted 1 emergency post in the last 24 hours.",
      }),
    );
    await openFact();
    await userEvent.click(emergencyToggle());
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand/ }));
    await userEvent.click(screen.getByRole("button", { name: "Post emergency, will be checked" }));
    expect(
      await screen.findByText("You've posted 1 emergency post in the last 24 hours."),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.fetchFactQuota).toHaveBeenCalledTimes(2));
    expect(emergencyToggle()).toBeEnabled();
    expect(emergencyToggle()).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Post fact, will be checked" })).toBeVisible();
  });
});
