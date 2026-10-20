"use client";

import type { ReactNode } from "react";
import { BarChart } from "@/components/ui/charts/BarChart";
import { MeterBar } from "@/components/ui/charts/MeterBar";
import { StatTile } from "@/components/ui/charts/StatTile";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import type { Post, PostStats as PostStatsData } from "@/lib/api/types";
import { formatConfidence, formatDuration } from "@/lib/format";
import { usePostStats } from "./usePostStats";

export const STATS_MESSAGES = {
  heading: "How this was checked",
  pending: "Checking facts… The result and how it was reached appear here.",
  underReview: "A moderator is taking a look. There is no automatic result to show.",
  moderator: "Reviewed by a moderator",
  spreadHeading: "Reposts and likes",
  spreadCaption: "First 14 days after posting (UTC)",
  spreadEmpty: "No reposts or likes yet.",
} as const;

type Label = Pick<Post, "status" | "verdict_source" | "post_type">;

/** The whole numbers of a confidence and a threshold, and how far apart they are. */
export function marginOf(confidence: string | null, threshold: number | null) {
  if (confidence === null || threshold === null) return null;
  const value = Math.round(Number(confidence));
  if (!Number.isFinite(value)) return null;
  return { confidence: value, threshold, margin: value - threshold };
}

function CheckBody({ post, stats }: { post: Label; stats: PostStatsData }) {
  if (post.status === "pending") {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">{STATS_MESSAGES.pending}</p>
    );
  }
  if (post.status === "under_review") {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        {STATS_MESSAGES.underReview}
      </p>
    );
  }
  if (post.status !== "verified_true" && post.status !== "verified_false") return null;

  const time = formatDuration(stats.seconds_to_verdict);
  if (post.verdict_source === "moderator") {
    return (
      <div className="flex flex-col gap-space-md">
        <p className="font-body-md text-body-md text-on-surface">{STATS_MESSAGES.moderator}</p>
        {time && (
          <div className="grid grid-cols-1 gap-space-md sm:grid-cols-3">
            <StatTile label="Time to decision" value={time} />
          </div>
        )}
      </div>
    );
  }

  const numbers = marginOf(stats.confidence_score, stats.confidence_threshold);
  // The label just changed and the numbers haven't arrived yet: say nothing until they do.
  if (!numbers) return null;
  const { confidence, threshold, margin } = numbers;
  const below = margin < 0;
  return (
    <div className="flex flex-col gap-space-lg">
      <MeterBar
        value={confidence}
        tone={post.status === "verified_true" ? "primary" : "error"}
        threshold={threshold}
        thresholdLabel={`Auto-label threshold ${threshold}%`}
        summary={`Confidence ${confidence}%. The automatic label threshold is ${threshold}%.`}
        table={{
          caption: "Confidence and threshold",
          rows: [
            ["Confidence", `${confidence}%`],
            ["Threshold", `${threshold}%`],
            ["Margin", below ? `Below the threshold by ${-margin} points` : `${margin} points`],
          ],
        }}
      />
      <div className="grid grid-cols-1 gap-space-md sm:grid-cols-3">
        <StatTile label="Confidence" value={formatConfidence(stats.confidence_score)} />
        <StatTile
          label="Threshold and margin"
          value={`${threshold}%`}
          sub={below ? `Below today's threshold of ${threshold}%` : `+${margin} points`}
        />
        <StatTile label="Time to verdict" value={time || "—"} />
      </div>
    </div>
  );
}

function sectionCard(children: ReactNode) {
  return <Card className="flex flex-col gap-space-lg p-space-lg">{children}</Card>;
}

/** The UTC day (`YYYY-MM-DD`) of the verdict, when it falls inside the chart. */
function verdictDay(stats: PostStatsData): string | undefined {
  const day = stats.verdict_at?.slice(0, 10);
  return day && stats.daily.some((d) => d.date === day) ? day : undefined;
}

/**
 * "How this was checked" (Part 11D; Stitch b3's gauge, tiles and Exhibit A, re-purposed): what the
 * check found and how the post spread. Presentational; `PostStats` fetches. A moderator's verdict
 * never shows a percentage, and a post with no label yet shows a one-line note instead of a meter.
 */
export function PostStatsView({ post, stats }: { post: Label; stats: PostStatsData }) {
  const reposts = stats.daily.reduce((n, d) => n + d.reposts, 0);
  const likes = stats.daily.reduce((n, d) => n + d.likes, 0);
  const marker =
    post.status === "verified_true" || post.status === "verified_false"
      ? verdictDay(stats)
      : undefined;
  const check = <CheckBody post={post} stats={stats} />;
  return (
    <section aria-labelledby="stats-heading" className="flex flex-col gap-space-md">
      <h2 id="stats-heading" className="font-headline-sm text-headline-sm text-on-surface">
        {STATS_MESSAGES.heading}
      </h2>
      {sectionCard(check)}
      {sectionCard(
        <>
          <h3 className="font-label-code text-label-code tracking-wider text-outline uppercase">
            {STATS_MESSAGES.spreadHeading}
          </h3>
          <BarChart
            days={stats.daily.map((d) => ({
              date: d.date,
              counts: { reposts: d.reposts, likes: d.likes, comments: d.comments },
            }))}
            series={[
              { key: "reposts", label: "Reposts", tone: "secondary" },
              { key: "likes", label: "Likes", tone: "outline" },
            ]}
            tableOnly={[{ key: "comments", label: "Comments" }]}
            markerDate={marker}
            markerLabel="Verdict"
            summary={`Reposts and likes per day for the first 14 days: ${reposts} ${reposts === 1 ? "repost" : "reposts"} and ${likes} ${likes === 1 ? "like" : "likes"} in all.`}
            caption={STATS_MESSAGES.spreadCaption}
            emptyNote={STATS_MESSAGES.spreadEmpty}
          />
        </>,
      )}
    </section>
  );
}

/**
 * The section on `/p/[id]` for a fact post. It loads its numbers on the client (the page's server
 * render is unchanged): a placeholder while loading, nothing when the request fails.
 */
export function PostStats({ post }: { post: Post }) {
  const { stats, phase } = usePostStats(post.id, post);
  if (post.post_type !== "fact" || post.status === "removed") return null;
  if (phase === "error") return null;
  if (!stats) {
    return (
      <div aria-busy="true" className="flex flex-col gap-space-md">
        <span className="sr-only">Loading how this was checked…</span>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  return <PostStatsView post={post} stats={stats} />;
}
