"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { PasswordField } from "@/components/ui/PasswordField";
import { PasswordStrengthMeter } from "@/components/ui/PasswordStrengthMeter";
import { RadioCardGroup } from "@/components/ui/RadioCard";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TextField } from "@/components/ui/TextField";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import { PostCard, type PostCardProps } from "@/features/posts/PostCard";
import { RemovedPostCard } from "@/features/posts/RemovedPostCard";
import type { Post } from "@/lib/api/types";
import { scorePassword } from "@/lib/password-strength";
import { Section } from "./GalleryLayout";

const NOW = new Date("2026-09-30T12:00:00Z");

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
              {kind === "opinion" ? "Post opinion" : "Post fact, will be checked"}
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
                    Emergency
                  </p>
                  <p className="mt-0.5 font-body-sm text-body-sm text-outline">
                    Pin this post for 24 hours. It is still fact-checked first.
                  </p>
                </div>
              </div>
              <Toggle
                label="Toggle Emergency Mode"
                tone="tertiary"
                checked={emergency}
                onCheckedChange={setEmergency}
              />
            </div>
            {emergency && (
              <div className="flex items-start gap-space-sm rounded-lg border border-tertiary/30 bg-tertiary/5 p-space-md font-body-sm text-body-sm text-on-surface-variant">
                <Icon name="warning" className="mt-0.5 shrink-0 text-tertiary" />
                <p>
                  <strong className="font-semibold text-tertiary">Misuse has consequences.</strong>{" "}
                  A FALSE emergency lowers your credibility score and blocks emergency posts for 30
                  days.
                </p>
              </div>
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
    </>
  );
}
