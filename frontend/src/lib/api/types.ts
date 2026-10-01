/**
 * API shapes from ARCHITECTURE §9. JSON is snake_case, IDs are UUID strings, and timestamps are
 * ISO-8601 UTC strings. Fields arrive in the parts named in the §9 endpoint index; the shapes are
 * fixed now so they never change under a later part.
 */
import type { PostStatus, PostType, VerdictSource } from "@/lib/post-display";

export type { PostStatus, PostType, VerdictSource };

/** An author, a reposter, or a row in a user list. */
export interface UserSummary {
  id: string;
  username: string;
  display_name: string;
  /** `/api/v1/avatars/{user_id}/{avatar_version}-96.webp`, or null for initials (14B). */
  avatar_url: string | null;
}

/** The public credibility block on user objects (never on post authors). */
export interface Reputation {
  /** null while fewer than 3 events count. */
  score: number | null;
  sample: number;
}

export type SourceKind = "url" | "doi";

/** One of up to five sources on a fact post, in the order the author entered them (§4c). */
export interface PostSource {
  value: string;
  kind: SourceKind;
}

export type AppealStatus = "open" | "upheld" | "overturned";

export interface Post {
  id: string;
  author: UserSummary;
  content: string;
  post_type: PostType;
  status: PostStatus;
  /** Empty for opinions and for facts without sources. */
  sources: PostSource[];
  is_emergency: boolean;
  /** Computed by the API with the current time (§4b). */
  emergency_active: boolean;
  emergency_expires_at: string | null;
  /** Non-null only for `verified_*` posts with `verdict_source = "pipeline"`, e.g. "94.00". */
  confidence_score: string | null;
  verdict_source: VerdictSource | null;
  verdict_note: string;
  like_count: number;
  comment_count: number;
  repost_count: number;
  liked_by_me: boolean;
  reposted_by_me: boolean;
  bookmarked_by_me: boolean;
  reported_by_me: boolean;
  is_mine: boolean;
  can_appeal: boolean;
  /** Only returned to the author. */
  appeal_status: AppealStatus | null;
  created_at: string;
}

/** A repost whose original was deleted or removed: "This post is no longer available". */
export interface UnavailablePost {
  id: string;
  unavailable: true;
}

export type FeedItem =
  | { kind: "post"; post: Post; reposted_by: null; activity_at: string }
  | { kind: "repost"; post: Post | UnavailablePost; reposted_by: UserSummary; activity_at: string };

/** Cursor pagination: `?cursor=<opaque>`, never an absolute `next` URL. */
export interface CursorPage<T> {
  results: T[];
  next_cursor: string | null;
}

/** Recent, Following and profile post lists. `pinned` is [] until 11C and after the first page. */
export interface FeedResponse extends CursorPage<FeedItem> {
  pinned: Post[];
  pinned_total: number;
}

export type Role = "user" | "moderator" | "senior_moderator";

/** `GET /api/v1/me/` (Part 1). */
export interface Me {
  id: string;
  username: string;
  display_name: string;
  email: string;
  is_email_verified: boolean;
  role: Role;
  has_usable_password: boolean;
  google_connected: boolean;
  /** The shell's avatar; null (initials) until photos exist in 14B. */
  avatar_url: string | null;
  /** Django Admin URL, sent to staff only. */
  admin_url?: string;
}

/** DRF errors through the custom exception handler: `{"detail": "...", "code": "..."}`. */
export interface DrfErrorBody {
  detail: string;
  code?: string;
}

/** DRF validation errors: `{"field": ["message"], "non_field_errors": [...]}`, possibly nested. */
export type DrfValidationBody = Record<string, unknown>;

/** allauth headless keeps its own envelope. Its 401 carries `data.flows` instead of `errors`. */
export interface AllauthBody {
  status: number;
  errors?: { code: string; param?: string; message: string }[];
  data?: unknown;
  meta?: unknown;
}
