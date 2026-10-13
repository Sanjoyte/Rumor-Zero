import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { makePost } from "@/features/posts/test-helpers";
import { APPEAL_PATHS, appealPost, MAX_APPEAL_REASON } from "./appeals-api";

vi.mock("@/lib/api/client", () => ({ api: { post: vi.fn() } }));

beforeEach(() => {
  vi.mocked(api.post).mockReset();
});

describe("appeals-api", () => {
  it("posts the reason to the appeal endpoint of that post and returns the post", async () => {
    const answer = makePost({ status: "under_review", appeal_status: "open" });
    vi.mocked(api.post).mockResolvedValue(answer);
    await expect(appealPost("p1", { reason: "It was a quote." })).resolves.toBe(answer);
    expect(api.post).toHaveBeenCalledWith("/v1/posts/p1/appeal/", { reason: "It was a quote." });
  });

  it("encodes the id", () => {
    expect(APPEAL_PATHS.appeal("a/b c")).toBe("/v1/posts/a%2Fb%20c/appeal/");
  });

  it("allows 500 characters, as the server does", () => {
    expect(MAX_APPEAL_REASON).toBe(500);
  });
});
