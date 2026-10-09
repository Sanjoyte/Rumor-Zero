import { describe, expect, it } from "vitest";
import type { Post } from "@/lib/api/types";
import { toPostCardProps } from "./post-card-props";
import { makePost } from "./test-helpers";

const POST: Post = makePost({
  id: "11111111-1111-4111-8111-111111111111",
  content: "Claim",
  post_type: "fact",
  status: "verified_true",
  sources: [{ value: "10.1000/xyz", kind: "doi" }],
  confidence_score: "94.00",
  verdict_source: "pipeline",
  created_at: "2026-10-08T12:00:00Z",
});

describe("toPostCardProps", () => {
  it("maps the API post to the card's props", () => {
    expect(toPostCardProps(POST)).toEqual({
      author: { displayName: "Ada", username: "ada", avatarUrl: null },
      content: "Claim",
      postType: "fact",
      status: "verified_true",
      confidenceScore: "94.00",
      verdictSource: "pipeline",
      emergencyActive: false,
      appealPending: false,
      createdAt: "2026-10-08T12:00:00Z",
      sources: [{ value: "10.1000/xyz", kind: "doi" }],
    });
  });

  it("marks an open appeal as pending", () => {
    expect(toPostCardProps({ ...POST, appeal_status: "open" }).appealPending).toBe(true);
    expect(toPostCardProps({ ...POST, appeal_status: "upheld" }).appealPending).toBe(false);
  });

  it("passes a blank display name through for the card to handle", () => {
    expect(
      toPostCardProps({ ...POST, author: { ...POST.author, display_name: "" } }).author.displayName,
    ).toBe("");
  });
});
