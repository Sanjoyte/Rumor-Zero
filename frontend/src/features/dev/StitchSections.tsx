"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips, type FilterChip } from "@/components/ui/FilterChips";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { PasswordField } from "@/components/ui/PasswordField";
import { PasswordStrengthMeter } from "@/components/ui/PasswordStrengthMeter";
import { RadioCardGroup } from "@/components/ui/RadioCard";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Tabs } from "@/components/ui/Tabs";
import { TextField } from "@/components/ui/TextField";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import { confirmationText, EMERGENCY_COPY } from "@/features/posts/emergency-copy";
import { PinnedEmergencies, PinnedEmergenciesBar } from "@/features/posts/PinnedEmergencies";
import { PostCard, type PostCardProps } from "@/features/posts/PostCard";
import { PostStatsView } from "@/features/posts/PostStats";
import { CredibilityPanelView } from "@/features/reputation/CredibilityPanel";
import { CredibilityWidgetView } from "@/features/reputation/CredibilityWidget";
import { RemovedPostCard } from "@/features/posts/RemovedPostCard";
import { queryTerms } from "@/features/search/highlight";
import { SearchBar } from "@/features/search/SearchBar";
import { UserRow } from "@/features/social/UserRow";
import type { DailyBucket, LedgerEntry, Post, PostStats, UserRowData } from "@/lib/api/types";
import { scorePassword } from "@/lib/password-strength";
import { Section } from "./GalleryLayout";

const NOW = new Date("2026-09-30T12:00:00Z");

const STATS_DAILY: DailyBucket[] = Array.from({ length: 14 }, (_, i) => ({
  date: `2026-10-${String(i + 1).padStart(2, "0")}`,
  reposts: [0, 3, 5, 2, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0][i],
  likes: [2, 9, 14, 6, 4, 2, 3, 1, 1, 0, 0, 1, 0, 0][i],
  comments: [0, 1, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0][i],
}));
const STATS_PIPELINE: PostStats = {
  confidence_score: "95.00",
  confidence_threshold: 85,
  verdict_source: "pipeline",
  seconds_to_verdict: 134,
  verdict_at: "2026-10-02T09:02:14Z",
  daily: STATS_DAILY,
};
const STATS_BLANK: PostStats = {
  confidence_score: null,
  confidence_threshold: null,
  verdict_source: null,
  seconds_to_verdict: null,
  verdict_at: null,
  daily: STATS_DAILY.map((d) => ({ ...d, reposts: 0, likes: 0, comments: 0 })),
};
const STATS_SPECIMENS: {
  label: string;
  post: Parameters<typeof PostStatsView>[0]["post"];
  stats: PostStats;
}[] = [
  {
    label: "b3 verified by the pipeline (95% over 85%)",
    post: { post_type: "fact", status: "verified_true", verdict_source: "pipeline" },
    stats: STATS_PIPELINE,
  },
  {
    label: "b3 FALSE by the pipeline, threshold raised since (97%)",
    post: { post_type: "fact", status: "verified_false", verdict_source: "pipeline" },
    stats: { ...STATS_PIPELINE, confidence_threshold: 97 },
  },
  {
    label: "b3 decided by a moderator (never a percentage)",
    post: { post_type: "fact", status: "verified_true", verdict_source: "moderator" },
    stats: {
      ...STATS_BLANK,
      verdict_source: "moderator",
      seconds_to_verdict: 7260,
      verdict_at: "2026-10-02T11:01:00Z",
      daily: STATS_DAILY,
    },
  },
  {
    label: "b3 still being checked (no meter, empty bars)",
    post: { post_type: "fact", status: "pending", verdict_source: null },
    stats: STATS_BLANK,
  },
  {
    label: "b3 under review",
    post: { post_type: "fact", status: "under_review", verdict_source: null },
    stats: STATS_BLANK,
  },
];

const TREND = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.UTC(2026, 8, 21 + i)).toISOString().slice(0, 10),
  score: [
    58, 58, 58, 59, 59, 60, 60, 60, 61, 61, 61, 62, 62, 62, 62, 61, 61, 63, 63, 64, 64, 64, 65, 65,
    66, 66, 67, 67, 68, 68,
  ][i],
}));

let entryCount = 0;
function entry(overrides: Partial<LedgerEntry>): LedgerEntry {
  entryCount += 1;
  return {
    id: `gallery-${entryCount}`,
    kind: "fact_true",
    label: "Fact verified true",
    positive: "1.00",
    negative: "0.00",
    score_after: 68,
    created_at: "2026-10-12T09:30:00Z",
    post_id: "11111111-1111-4111-8111-111111111111",
    reverses: null,
    reversed: false,
    appeal: null,
    ...overrides,
  };
}
const LEDGER: LedgerEntry[] = [
  entry({
    label: "Reversed: Fact labelled FALSE",
    positive: "0.00",
    negative: "-1.00",
    kind: "reversal",
    reverses: "x",
    score_after: 68,
  }),
  entry({
    label: "Fact labelled FALSE",
    positive: "0.00",
    negative: "1.00",
    kind: "fact_false",
    score_after: 62,
    reversed: true,
    appeal: null,
  }),
  entry({
    label: "Post removed by a moderator",
    positive: "0.00",
    negative: "2.00",
    kind: "post_removed",
    score_after: 61,
    created_at: "2026-10-09T08:00:00Z",
    appeal: { status: null, can_appeal: true },
  }),
  entry({
    label: "Fact labelled FALSE",
    positive: "0.00",
    negative: "1.00",
    kind: "fact_false",
    score_after: 66,
    created_at: "2026-10-07T08:00:00Z",
    appeal: { status: "upheld", can_appeal: false },
  }),
  entry({
    label: "Repost of a fact verified true",
    positive: "0.25",
    negative: "0.00",
    kind: "repost_true",
    score_after: 67,
    created_at: "2026-10-05T08:00:00Z",
    post_id: null,
  }),
];
const NOOP = () => {};

const AUTHOR = { displayName: "Ada Example", username: "ada_example" };

const CARDS: { label: string; props: PostCardProps }[] = [
  {
    label: "b1 verified (pipeline, 94%)",
    props: {
      author: AUTHOR,
      content: "Global renewable energy additions exceeded 500 GW in 2023, a record for the year.",
      postType: "fact",
      status: "verified_true",
      verdictSource: "pipeline",
      confidenceScore: "94.00",
      createdAt: "2026-09-30T09:00:00Z",
      now: NOW,
    },
  },
  {
    label: "b1 FALSE (pipeline, 88%)",
    props: {
      author: { displayName: "Ben Sample", username: "ben_sample" },
      content: "The city banned all cars downtown last week.",
      postType: "fact",
      status: "verified_false",
      verdictSource: "pipeline",
      confidenceScore: "88.00",
      createdAt: "2026-09-30T06:30:00Z",
      now: NOW,
    },
  },
  {
    label: "b1 emergency, still being checked (violet stripe + EMERGENCY chip)",
    props: {
      author: { displayName: "Cara Test", username: "cara_test" },
      content: "The bridge on Route 9 is closed in both directions until further notice.",
      postType: "fact",
      status: "pending",
      emergencyActive: true,
      createdAt: "2026-09-30T11:40:00Z",
      now: NOW,
    },
  },
  {
    label: "b1 under review (appeal pending, shown to the author)",
    props: {
      author: AUTHOR,
      content: "The new transit levy raised twice what the council projected.",
      postType: "fact",
      status: "under_review",
      appealPending: true,
      createdAt: "2026-09-29T15:00:00Z",
      now: NOW,
    },
  },
  {
    label: "b1 opinion",
    props: {
      author: { displayName: "Dev Placeholder", username: "dev_placeholder" },
      content:
        "Pure optimisation cannot substitute for ethical frameworks when a city allocates transit capital.",
      postType: "opinion",
      status: "published",
      createdAt: "2026-09-27T10:00:00Z",
      now: NOW,
    },
  },
  {
    label: "verified by a moderator (no percentage)",
    props: {
      author: AUTHOR,
      content: "The library extended its weekend hours from this month.",
      postType: "fact",
      status: "verified_true",
      verdictSource: "moderator",
      createdAt: "2026-09-20T10:00:00Z",
      now: NOW,
    },
  },
  {
    label: "FALSE by a moderator, emergency ended (back to red)",
    props: {
      author: AUTHOR,
      content: "Tap water in the north district is unsafe to drink.",
      postType: "fact",
      status: "verified_false",
      verdictSource: "moderator",
      emergencyActive: false,
      createdAt: "2025-12-01T10:00:00Z",
      now: NOW,
    },
  },
  {
    label: "removed tombstone",
    props: {
      author: AUTHOR,
      content: "Hidden text",
      postType: "fact",
      status: "removed",
      createdAt: "2026-09-28T10:00:00Z",
      now: NOW,
    },
  },
];

/**
 * A removed post as its author sees it (Part 11), after the request: the button needs a session,
 * so the gallery shows the two states that don't (the chip, and what became of it).
 */
const REMOVED_AS_AUTHOR: { label: string; post: Post }[] = [
  {
    label: "removed, author's view: appeal open",
    post: {
      id: "00000000-0000-4000-8000-000000000001",
      author: { id: "u-ada", username: "ada", display_name: "Ada", avatar_url: null },
      content: "Hidden text that only its author can read.",
      post_type: "fact",
      status: "removed",
      sources: [],
      is_emergency: false,
      emergency_active: false,
      emergency_expires_at: null,
      emergency_demoted: false,
      confidence_score: null,
      verdict_source: null,
      verdict_note: "",
      like_count: 0,
      comment_count: 0,
      repost_count: 0,
      liked_by_me: false,
      reposted_by_me: false,
      bookmarked_by_me: false,
      reported_by_me: false,
      is_mine: true,
      can_appeal: false,
      appeal_status: "open",
      removal_reason: "Harassment of a private person.",
      created_at: "2026-09-28T10:00:00Z",
    },
  },
  {
    label: "removed, author's view: appeal upheld",
    post: {
      id: "00000000-0000-4000-8000-000000000002",
      author: { id: "u-ada", username: "ada", display_name: "Ada", avatar_url: null },
      content: "Another hidden claim.",
      post_type: "opinion",
      status: "removed",
      sources: [],
      is_emergency: false,
      emergency_active: false,
      emergency_expires_at: null,
      emergency_demoted: false,
      confidence_score: null,
      verdict_source: null,
      verdict_note: "",
      like_count: 0,
      comment_count: 0,
      repost_count: 0,
      liked_by_me: false,
      reposted_by_me: false,
      bookmarked_by_me: false,
      reported_by_me: false,
      is_mine: true,
      can_appeal: false,
      appeal_status: "upheld",
      removal_reason: "",
      created_at: "2026-09-28T10:00:00Z",
    },
  },
];

/** Pinned emergencies (Part 11C): two shown of three, so "Show all (3)" appears. */
function pinnedPost(id: string, content: string, status: Post["status"], at: string): Post {
  return {
    ...REMOVED_AS_AUTHOR[0].post,
    id,
    author: { id: `u-${id}`, username: "cara_test", display_name: "Cara Test", avatar_url: null },
    content,
    status,
    removal_reason: "",
    appeal_status: null,
    is_mine: false,
    is_emergency: true,
    emergency_active: true,
    emergency_expires_at: "2026-10-01T11:00:00Z",
    created_at: at,
  };
}

const PINNED: Post[] = [
  pinnedPost(
    "00000000-0000-4000-8000-0000000000a1",
    "The bridge on Route 9 is closed in both directions until further notice.",
    "pending",
    "2026-09-30T11:40:00Z",
  ),
  pinnedPost(
    "00000000-0000-4000-8000-0000000000a2",
    "A boil-water notice is in force for the east side until Friday.",
    "under_review",
    "2026-09-30T10:05:00Z",
  ),
];
const PINNED_ALL: Post[] = [
  ...PINNED,
  pinnedPost(
    "00000000-0000-4000-8000-0000000000a3",
    "The north shelter is full; the school gym on Elm Street is open instead.",
    "verified_true",
    "2026-09-30T08:30:00Z",
  ),
];

function pinnedCard(post: Post) {
  return (
    <PostCard
      author={{ displayName: post.author.display_name, username: post.author.username }}
      content={post.content}
      postType={post.post_type}
      status={post.status}
      emergencyActive={post.emergency_active}
      createdAt={post.created_at}
      now={NOW}
    />
  );
}

const REASONS = [
  {
    value: "inaccurate",
    label: "False or inaccurate",
    description: "The claim is wrong or not supported by the evidence.",
  },
  {
    value: "misleading",
    label: "Missing context or misleading",
    description: "True on its own, but it leaves out something important.",
  },
  {
    value: "harassment",
    label: "Harassment or defamation",
    description: "It targets a person or group.",
  },
  {
    value: "spam",
    label: "Spam or fake accounts",
    description: "Promotion or inauthentic activity.",
  },
  { value: "other", label: "Something else", description: "Tell us more in the details." },
];

function ComposerModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [kind, setKind] = useState<"opinion" | "fact" | null>("fact");
  const [emergency, setEmergency] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [text, setText] = useState("");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New post"
      icon="edit_note"
      footer={
        <>
          <p className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
            <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full bg-secondary" />
            <span>
              <strong className="font-semibold text-on-surface">7 of 10</strong> fact posts left
              today
            </span>
          </p>
          <div className="flex items-center gap-space-sm">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!kind}>
              {kind === "fact" && <Icon name="bolt" size="sm" filled />}
              {kind === "opinion"
                ? "Post opinion"
                : emergency
                  ? EMERGENCY_COPY.submit
                  : "Post fact, will be checked"}
            </Button>
          </div>
        </>
      }
    >
      <Textarea
        label="Post text"
        variant="bare"
        maxCount={500}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="What do you want to say?"
        data-autofocus
      />
      <div className="space-y-space-xs">
        <div className="flex items-center justify-between">
          <span className="font-body-sm text-body-sm font-semibold text-on-surface">Post type</span>
          {!kind && (
            <span className="font-body-sm text-body-sm text-outline">Choose one to continue</span>
          )}
        </div>
        <SegmentedControl
          label="Post type"
          value={kind}
          onChange={setKind}
          options={[
            { value: "opinion", label: "Opinion", icon: "format_quote" },
            { value: "fact", label: "Fact", icon: "fact_check" },
          ]}
        />
      </div>
      {kind === "fact" && (
        <>
          <div className="space-y-space-sm">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-space-sm">
                <Icon name="bolt" filled className="mt-0.5 shrink-0 text-tertiary" />
                <div>
                  <p className="font-body-sm text-body-sm font-semibold text-on-surface">
                    {EMERGENCY_COPY.title}
                  </p>
                  <p className="mt-0.5 font-body-sm text-body-sm text-outline">
                    {EMERGENCY_COPY.description}
                  </p>
                </div>
              </div>
              <Toggle
                label={EMERGENCY_COPY.toggleLabel}
                tone="tertiary"
                checked={emergency}
                onCheckedChange={setEmergency}
              />
            </div>
            {emergency && (
              <>
                <div className="flex items-start gap-space-sm rounded-lg border border-tertiary/30 bg-tertiary/5 p-space-md">
                  <div className="mt-0.5 flex shrink-0 items-center text-tertiary">
                    <Icon name="warning" className="-mr-space-xs" />
                    <Icon name="bolt" size="xs" filled />
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    <strong className="font-semibold text-tertiary">
                      {EMERGENCY_COPY.warningTitle}
                    </strong>
                    <br />
                    {EMERGENCY_COPY.warning}
                  </p>
                </div>
                <Checkbox
                  label={confirmationText(30)}
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
              </>
            )}
          </div>
          <TextField
            label="Source (optional)"
            leadingIcon="link"
            mono
            placeholder="https://… or a DOI"
          />
        </>
      )}
    </Modal>
  );
}

function ReportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [reason, setReason] = useState<string | null>("inaccurate");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Report this post"
      eyebrow="Report"
      footerTone="plain"
      footer={
        <>
          <p className="flex max-w-xs items-center gap-space-sm font-body-sm text-body-sm leading-tight text-outline">
            <Icon name="fingerprint" className="shrink-0" />
            Reports are private. The author is never told who reported.
          </p>
          <div className="flex shrink-0 items-center gap-space-md">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button>Submit report</Button>
          </div>
        </>
      }
    >
      <div className="relative overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md pl-space-lg">
        <VerdictStripe tone="inverse-surface" />
        <p className="font-claim-headline text-body-sm leading-relaxed text-on-surface-variant">
          {"“"}Global renewable energy additions exceeded 500 GW in 2023.{"”"}
        </p>
      </div>
      <RadioCardGroup
        name="report-reason"
        legend="Why are you reporting this post?"
        options={REASONS}
        value={reason}
        onChange={setReason}
      />
      <Alert tone="info" title="What happens next">
        A few independent reports send a post to a human moderator. Nothing is removed
        automatically.
      </Alert>
    </Modal>
  );
}

const SEARCH_QUERY = "solar capacity";
const SEARCH_TERMS = queryTerms(SEARCH_QUERY);
const SEARCH_CHIPS: FilterChip[] = [
  { id: "all", label: "All" },
  { id: "facts", label: "Facts" },
  { id: "opinions", label: "Opinions", dot: "outline-variant" },
  { id: "verified", label: "Verified", dot: "primary" },
  { id: "false", label: "FALSE", dot: "error" },
  { id: "review", label: "Under review", dot: "verdict-review" },
];
// `is_me` rows have no Follow button, which needs a session this gallery doesn't have.
const SEARCH_PEOPLE: UserRowData[] = [
  {
    id: "search-1",
    username: "solar_sam",
    display_name: "Sam Solar",
    bio: "Writes about solar capacity and the grid.",
    avatar_url: null,
    reputation: { score: 86, sample: 14 },
    counts: { verified: 31 },
    is_following: false,
    is_me: true,
  },
  {
    id: "search-2",
    username: "wren",
    display_name: "Wren Capacity-Lee",
    bio: "",
    avatar_url: null,
    reputation: { score: null, sample: 1 },
    counts: { verified: 0 },
    is_following: false,
    is_me: true,
  },
];

export function StitchSections() {
  const [password, setPassword] = useState("");
  const [composer, setComposer] = useState(false);
  const [report, setReport] = useState(false);

  return (
    <>
      <Section
        id="stitch-post-cards"
        title="Stitch b1: PostCard"
        note="Compare with design/stitch/stitch_website_sitemap_grid_builder/b1_home_feed/code.html at 1280px."
      >
        <div className="max-w-reading space-y-space-lg">
          {CARDS.map(({ label, props }) => (
            <div key={label} className="space-y-space-xs">
              <p className="font-label-code text-label-code text-outline uppercase">{label}</p>
              <PostCard {...props} />
            </div>
          ))}
          {REMOVED_AS_AUTHOR.map(({ label, post }) => (
            <div key={label} className="space-y-space-xs">
              <p className="font-label-code text-label-code text-outline uppercase">{label}</p>
              <RemovedPostCard post={post} now={NOW} />
            </div>
          ))}
        </div>
      </Section>

      <Section
        id="stitch-pinned"
        title="Stitch b1: pinned emergencies"
        note="b1's dispatch banner as the pinned section (Part 11C): open, then folded with ×."
      >
        <div className="max-w-reading space-y-space-lg">
          <PinnedEmergencies
            feed="recent"
            posts={PINNED}
            total={PINNED_ALL.length}
            renderCard={pinnedCard}
            fetchAll={async () => ({ items: PINNED_ALL, nextCursor: null })}
          />
          <PinnedEmergenciesBar count={2} onShow={() => {}} />
        </div>
      </Section>

      <Section
        id="stitch-stats"
        title="Stitch b3: How this was checked"
        note="Part 11D. b3's gauge, tiles and Exhibit A, re-purposed; the meter keeps its verdict tone."
      >
        <div className="max-w-reading space-y-space-xl">
          {STATS_SPECIMENS.map(({ label, post, stats }) => (
            <div key={label} className="space-y-space-xs">
              <p className="font-label-code text-label-code text-outline uppercase">{label}</p>
              <PostStatsView post={post} stats={stats} />
            </div>
          ))}
        </div>
      </Section>

      <Section
        id="stitch-credibility"
        title="Stitch c1, b4 and c2: Credibility"
        note="Part 11D. The ring and the line are neutral grey. The panel is yours alone."
      >
        <div className="max-w-reading space-y-space-lg">
          <CredibilityWidgetView
            score={68}
            verified={20}
            falseCount={3}
            trend={TREND}
            trendPhase="ready"
          />
          <CredibilityWidgetView
            score={null}
            verified={1}
            falseCount={0}
            trend={null}
            trendPhase="idle"
          />
          <CredibilityWidgetView
            score={68}
            verified={20}
            falseCount={3}
            trend={null}
            trendPhase="loading"
          />
          <CredibilityPanelView
            phase="ready"
            entries={LEDGER}
            hasMore={false}
            loadingMore={false}
            moreError={false}
            publicScore={68}
            open
            onToggle={NOOP}
            onRetry={NOOP}
            onLoadMore={NOOP}
          />
          <CredibilityPanelView
            phase="ready"
            entries={LEDGER.slice(2, 3)}
            hasMore
            loadingMore={false}
            moreError={false}
            publicScore={null}
            open={false}
            onToggle={NOOP}
            onRetry={NOOP}
            onLoadMore={NOOP}
          />
          <CredibilityPanelView
            phase="ready"
            entries={[]}
            hasMore={false}
            loadingMore={false}
            moreError={false}
            publicScore={null}
            open={false}
            onToggle={NOOP}
            onRetry={NOOP}
            onLoadMore={NOOP}
          />
          <CredibilityPanelView
            phase="error"
            entries={[]}
            hasMore={false}
            loadingMore={false}
            moreError={false}
            publicScore={null}
            open={false}
            onToggle={NOOP}
            onRetry={NOOP}
            onLoadMore={NOOP}
          />
        </div>
      </Section>

      <Section
        id="stitch-signup"
        title="Stitch a2: sign-up fields"
        note="Compare with a2_sign_up/code.html. The real form arrives in Part 1."
      >
        <Card className="max-w-form space-y-space-md p-space-lg">
          <TextField
            label="Email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
          />
          <TextField
            label="Username"
            placeholder="ada_example"
            trailing={<Icon name="check" className="text-primary" />}
            success="Available: @ada_example"
          />
          <div>
            <PasswordField
              label="Password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <PasswordStrengthMeter score={scorePassword(password)} />
          </div>
          <Button block>Create account</Button>
        </Card>
      </Section>

      <Section
        id="stitch-modals"
        title="Stitch b2 and d1: modals"
        note="Native dialog: focus is trapped, Esc closes it, and focus returns to the button."
      >
        <div className="flex flex-wrap gap-space-md">
          <Button onClick={() => setComposer(true)}>
            <Icon name="edit_note" size="lg" />
            Open the composer (b2)
          </Button>
          <Button variant="secondary" onClick={() => setReport(true)}>
            Open the report modal (d1)
          </Button>
        </div>
        <ComposerModal open={composer} onClose={() => setComposer(false)} />
        <ReportModal open={report} onClose={() => setReport(false)} />
      </Section>

      <Section
        id="stitch-search"
        title="Stitch b4: search results"
        note="Part 12. Compare with b4_search_results/code.html at 1280px: no counts, no sort menu, no Primary Sources."
      >
        <div className="max-w-reading space-y-space-lg">
          <section className="space-y-space-md rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-lg shadow-sm">
            <SearchBar q={SEARCH_QUERY} type="posts" filter="verified" />
            <hr className="border-outline-variant/30" />
            <Tabs
              tabs={[
                { id: "posts", label: "Posts" },
                { id: "users", label: "People" },
              ]}
              value="posts"
              onChange={NOOP}
              label="Search in (specimen)"
            />
            <FilterChips
              label="Filter posts (specimen)"
              chips={SEARCH_CHIPS}
              selected={["verified"]}
              onChange={NOOP}
              className="pt-space-xs"
            />
          </section>
          <PostCard
            {...CARDS[0].props}
            content="Solar capacity grew 30% last year, and capacity auctions broke records."
            highlight={SEARCH_TERMS}
          />
          <PostCard
            author={{ displayName: "Dev Opinion", username: "dev_opinion" }}
            content="I think more solar capacity belongs on every school roof."
            postType="opinion"
            status="published"
            createdAt="2026-09-30T08:00:00Z"
            now={NOW}
            highlight={SEARCH_TERMS}
          />
          <div className="divide-y divide-outline-variant/30 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
            {SEARCH_PEOPLE.map((row) => (
              <UserRow key={row.id} user={row} highlight={SEARCH_TERMS} />
            ))}
          </div>
          <EmptyState icon="search" title="Search Rumor Zero">
            Type a word or a phrase to find posts, or a name to find people.
          </EmptyState>
          <EmptyState icon="search_off" title={"No results for \u201Czzz\u201D"}>
            Try different words or remove a filter.
          </EmptyState>
          <Alert tone="error" title="Couldn't load posts">
            <p>You&apos;re going too fast. Try again in a minute.</p>
          </Alert>
        </div>
      </Section>
    </>
  );
}
