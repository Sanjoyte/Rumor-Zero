import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithComposer, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { Connections } from "./Connections";
import { makeProfile, makeRow } from "./test-helpers";

const api = vi.hoisted(() => ({
  fetchProfile: vi.fn(),
  fetchConnections: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
}));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  ...api,
}));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/u/bob/followers",
}));

const page = (names: string[], nextCursor: string | null = null) => ({
  items: names.map((name) => makeRow({ id: `id-${name}`, username: name, display_name: name })),
  nextCursor,
});
const rows = () => screen.queryAllByRole("article");

beforeEach(() => {
  nav.push.mockReset();
  api.fetchProfile.mockReset();
  api.fetchProfile.mockResolvedValue(makeProfile());
  api.fetchConnections.mockReset();
  api.fetchConnections.mockResolvedValue(page(["cy", "dee"]));
  api.followUser.mockReset();
  api.followUser.mockResolvedValue({ is_following: true });
  api.unfollowUser.mockReset();
  api.unfollowUser.mockResolvedValue(undefined);
});

function renderList(tab: "followers" | "following" = "followers", kind: SessionKind = "anonymous") {
  return renderWithComposer(<Connections username="bob" tab={tab} />, kind);
}

describe("Connections", () => {
  it("shows a back link, the two tabs with their counts and the people", async () => {
    renderList();
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(await screen.findByRole("link", { name: /Back to Bob Stone \(@bob\)/ })).toHaveAttribute(
      "href",
      "/u/bob",
    );
    const followers = await screen.findByRole("tab", { name: /Followers/ });
    expect(followers).toHaveAttribute("aria-selected", "true");
    expect(followers).toHaveTextContent("1420");
    expect(screen.getByRole("tab", { name: /Following/ })).toHaveTextContent("186");
    expect(
      screen.getByRole("heading", { level: 1, name: /People following Bob Stone/ }),
    ).toBeInTheDocument();
  });

  it("reads the followers list or the following list for its tab", async () => {
    renderList("followers");
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(api.fetchConnections).toHaveBeenCalledWith(
      "bob",
      "followers",
      null,
      expect.any(AbortSignal),
    );
  });

  it("the following tab reads the following list", async () => {
    renderList("following");
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(api.fetchConnections).toHaveBeenCalledWith(
      "bob",
      "following",
      null,
      expect.any(AbortSignal),
    );
    expect(screen.getByRole("tab", { name: /Following/ })).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("heading", { level: 1, name: /People followed by/ }),
    ).toBeInTheDocument();
  });

  it("goes to the other list's address when the other tab is chosen", async () => {
    renderList("followers");
    await userEvent.click(await screen.findByRole("tab", { name: /Following/ }));
    expect(nav.push).toHaveBeenCalledWith("/u/bob/following");
    await userEvent.click(screen.getByRole("tab", { name: /Followers/ }));
    expect(nav.push).toHaveBeenCalledTimes(1); // the selected tab does nothing
  });

  it("loads more with the cursor and ends with a note", async () => {
    api.fetchConnections
      .mockResolvedValueOnce(page(["cy"], "c1"))
      .mockResolvedValueOnce(page(["dee"]));
    renderList();
    await waitFor(() => expect(rows()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(api.fetchConnections).toHaveBeenLastCalledWith(
      "bob",
      "followers",
      "c1",
      expect.any(AbortSignal),
    );
    expect(screen.getByText("That's everyone.")).toBeInTheDocument();
  });

  it("keeps the list and offers another try when Load more fails", async () => {
    api.fetchConnections
      .mockResolvedValueOnce(page(["cy"], "c1"))
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }));
    renderList();
    await waitFor(() => expect(rows()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    expect(await screen.findByText(/Couldn't load more people/)).toBeInTheDocument();
    expect(rows()).toHaveLength(1);
  });

  it("words each empty list", async () => {
    api.fetchConnections.mockResolvedValue(page([]));
    renderList("followers");
    expect(await screen.findByText("No followers yet")).toBeInTheDocument();
    expect(await screen.findByText("Nobody follows Bob Stone yet.")).toBeInTheDocument();
  });

  it("words the empty following list", async () => {
    api.fetchConnections.mockResolvedValue(page([]));
    renderList("following");
    expect(await screen.findByText("Not following anyone yet")).toBeInTheDocument();
  });

  it("shows an error with Try again when the list can't load", async () => {
    api.fetchConnections
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }))
      .mockResolvedValueOnce(page(["cy"]));
    renderList();
    expect(await screen.findByText("Couldn't load this list")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(rows()).toHaveLength(1));
  });

  it("says so when the account does not exist", async () => {
    api.fetchProfile.mockRejectedValue(
      new ApiError({ status: 404, code: "not_found", detail: "x" }),
    );
    renderList();
    expect(await screen.findByText("Profile not found")).toBeInTheDocument();
  });

  it("doesn't fetch anything while the session is loading", async () => {
    renderList("followers", "loading");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.fetchConnections).not.toHaveBeenCalled();
    expect(api.fetchProfile).not.toHaveBeenCalled();
  });

  it("gives each row a working Follow button, and none on your own row", async () => {
    api.fetchConnections.mockResolvedValue({
      items: [
        makeRow({ id: "1", username: "cy", display_name: "Cy", is_following: false }),
        makeRow({ id: "2", username: "ada", display_name: "Ada", is_me: true }),
        makeRow({ id: "3", username: "dee", display_name: "Dee", is_following: true }),
      ],
      nextCursor: null,
    });
    renderList("followers", "verified");
    await waitFor(() => expect(rows()).toHaveLength(3));
    const [cy, ada, dee] = rows();
    await userEvent.click(await within(cy).findByRole("button", { name: "Follow" }));
    expect(api.followUser).toHaveBeenCalledWith("cy");
    expect(within(ada).queryByRole("button")).not.toBeInTheDocument();
    expect(within(dee).getByRole("button", { name: "Following" })).toBeInTheDocument();
  });

  it("works under StrictMode for a signed-in visitor", async () => {
    renderWithComposer(
      <StrictMode>
        <Connections username="bob" tab="followers" />
      </StrictMode>,
      "verified",
    );
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(await screen.findByRole("tab", { name: /Followers/ })).toHaveTextContent("1420");
  });
});
