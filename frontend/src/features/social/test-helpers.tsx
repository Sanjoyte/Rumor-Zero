/** Shared test helpers for the social feature (not shipped: only *.test.* files import it). */
import type { Comment, UserProfile, UserRowData } from "@/lib/api/types";

export function makeProfile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: "u-2",
    username: "bob",
    display_name: "Bob Stone",
    bio: "Counting things.",
    avatar_url: null,
    created_at: "2024-03-15T10:00:00Z",
    counts: { followers: 1420, following: 186, posts: 42, verified: 68, false: 0 },
    reputation: { score: null, sample: 0 },
    is_following: false,
    is_me: false,
    ...overrides,
  };
}

export function makeRow(overrides: Partial<UserRowData> = {}): UserRowData {
  return {
    id: "u-3",
    username: "cy",
    display_name: "Cy Lane",
    bio: "",
    avatar_url: null,
    reputation: { score: null, sample: 0 },
    is_following: false,
    is_me: false,
    ...overrides,
  };
}

export function makeComment(overrides: Partial<Comment> = {}): Comment {
  return {
    id: "c-1",
    author: { id: "u-3", username: "cy", display_name: "Cy Lane", avatar_url: null },
    content: "A fair point.",
    is_mine: false,
    created_at: "2026-10-08T11:00:00Z",
    ...overrides,
  };
}
