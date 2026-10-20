"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { RingGauge } from "@/components/ui/charts/RingGauge";
import { Sparkline } from "@/components/ui/charts/Sparkline";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import type { TrendPoint, UserProfile } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatCount, formatShortDate } from "@/lib/format";
import { CREDIBILITY_HELP_HREF, NEW_SCORE_HINT } from "./CredibilityBadge";
import { CREDIBILITY_COPY, trendSummary } from "./ledger-copy";
import type { TrendPhase } from "./useReputationTrend";
import { useReputationTrend } from "./useReputationTrend";

function Count({ dot, children }: { dot: "primary" | "error"; children: ReactNode }) {
  return (
    <span className="flex items-center gap-space-xs">
      <span
        aria-hidden="true"
        className={cn("h-2 w-2 rounded-full", dot === "primary" ? "bg-primary" : "bg-error")}
      />
      {children}
    </span>
  );
}

export interface CredibilityWidgetViewProps {
  score: number | null;
  verified: number;
  falseCount: number;
  trend: TrendPoint[] | null;
  trendPhase: TrendPhase;
}

/**
 * The Credibility widget (Stitch c1's "Epistemic Standing" ring, b4's sparkline), presentational.
 * Neutral on purpose (user decision 2026-10-13, extended 2026-10-20): the ring and the line are
 * greys; only the two count dots carry the verdict colours, as c1's counters do. No seal.
 */
export function CredibilityWidgetView({
  score,
  verified,
  falseCount,
  trend,
  trendPhase,
}: CredibilityWidgetViewProps) {
  const first = trend?.[0]?.score;
  const last = trend?.[trend.length - 1]?.score;
  return (
    <Card as="section" aria-labelledby="credibility-heading" className="p-space-lg">
      <div className="flex flex-col gap-space-lg sm:flex-row sm:items-center">
        <RingGauge
          value={score}
          centre={
            score === null ? (
              <span className="font-label-code text-label-code text-on-surface-variant">New</span>
            ) : (
              <span className="font-headline-md text-headline-md text-on-surface">{score}</span>
            )
          }
          summary={
            score === null
              ? `Credibility: New. ${NEW_SCORE_HINT}`
              : `Credibility score ${score} out of 100.`
          }
          table={{
            caption: "Credibility score",
            rows: [["Score", score === null ? "New" : String(score)]],
          }}
        />
        <div className="flex min-w-0 flex-1 flex-col gap-space-sm">
          <h2
            id="credibility-heading"
            className="font-headline-sm text-headline-sm text-on-surface"
          >
            {CREDIBILITY_COPY.widgetHeading}
          </h2>
          <p className="flex flex-wrap items-center gap-x-space-sm gap-y-space-xs font-label-code text-label-code text-on-surface-variant">
            <Count dot="primary">{formatCount(verified)} verified</Count>
            <span aria-hidden="true">·</span>
            <Count dot="error">{formatCount(falseCount)} FALSE</Count>
          </p>
          {score === null && (
            <p className="font-body-sm text-body-sm text-on-surface-variant">{NEW_SCORE_HINT}</p>
          )}
          {score !== null && trendPhase === "loading" && <Skeleton className="h-6 w-28" />}
          {score !== null && trend && first !== undefined && last !== undefined && (
            <div className="flex flex-col gap-space-xs">
              <Sparkline
                values={trend.map((p) => p.score)}
                summary={trendSummary(first, last)}
                table={{
                  caption: "Credibility score, last 30 days",
                  columns: ["Day", "Score"],
                  rows: trend.map((p) => [formatShortDate(p.date), p.score]),
                }}
              />
              <p className="font-label-code text-label-badge text-outline">
                {CREDIBILITY_COPY.lastThirtyDays}
              </p>
            </div>
          )}
          <Link
            href={CREDIBILITY_HELP_HREF}
            prefetch={false}
            className="self-start font-body-sm text-body-sm font-medium text-secondary hover:underline"
          >
            How this is calculated
          </Link>
        </div>
      </div>
    </Card>
  );
}

/**
 * On every profile, between the header card and the filter chips. The ring and the counts come from
 * the profile already loaded (so they are in the server render); only the trend is fetched, and only
 * while the score is public.
 */
export function CredibilityWidget({ profile }: { profile: UserProfile }) {
  const { score } = profile.reputation;
  const { trend, phase } = useReputationTrend(profile.username, score !== null);
  return (
    <CredibilityWidgetView
      score={score}
      verified={profile.counts.verified}
      falseCount={profile.counts.false}
      trend={trend}
      trendPhase={phase}
    />
  );
}
