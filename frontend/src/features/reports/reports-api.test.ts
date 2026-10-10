import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { REPORT_PATHS, reportPost } from "./reports-api";

vi.mock("@/lib/api/client", () => ({ api: { post: vi.fn() } }));

beforeEach(() => {
  vi.mocked(api.post).mockReset();
  vi.mocked(api.post).mockResolvedValue({ reported: true });
});

describe("reports-api", () => {
  it("posts to the report endpoint of that post", async () => {
    await expect(reportPost("p1", { reason: "spam", details: "" })).resolves.toEqual({
      reported: true,
    });
    expect(api.post).toHaveBeenCalledWith("/v1/posts/p1/report/", { reason: "spam", details: "" });
  });

  it("encodes the id", () => {
    expect(REPORT_PATHS.report("a/b c")).toBe("/v1/posts/a%2Fb%20c/report/");
  });
});
