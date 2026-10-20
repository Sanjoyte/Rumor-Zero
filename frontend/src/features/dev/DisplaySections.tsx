"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { BarChart } from "@/components/ui/charts/BarChart";
import { MeterBar } from "@/components/ui/charts/MeterBar";
import { RingGauge } from "@/components/ui/charts/RingGauge";
import { Sparkline } from "@/components/ui/charts/Sparkline";
import { StatTile } from "@/components/ui/charts/StatTile";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { DangerAction, DangerZone } from "@/components/ui/DangerZone";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips } from "@/components/ui/FilterChips";
import { LoadMore } from "@/components/ui/LoadMore";
import { PasswordStrengthMeter } from "@/components/ui/PasswordStrengthMeter";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Skeleton } from "@/components/ui/Skeleton";
import { AppealPendingBadge, EmergencyBadge, StatusBadge } from "@/components/ui/StatusBadge";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { TextField } from "@/components/ui/TextField";
import { Toast, useToast } from "@/components/ui/Toast";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import { scorePassword } from "@/lib/password-strength";
import type { StripeTone } from "@/lib/post-display";
import { Section, Specimen } from "./GalleryLayout";

const SPREAD_DAYS = Array.from({ length: 14 }, (_, i) => ({
  date: `2026-10-${String(i + 1).padStart(2, "0")}`,
  counts: {
    reposts: [0, 3, 5, 2, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0][i],
    likes: [2, 9, 14, 6, 4, 2, 3, 1, 1, 0, 0, 1, 0, 0][i],
    comments: [0, 1, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0][i],
  },
}));
const EMPTY_DAYS = SPREAD_DAYS.map((d) => ({ date: d.date, counts: {} }));
const SPREAD_SERIES = [
  { key: "reposts", label: "Reposts", tone: "secondary" as const },
  { key: "likes", label: "Likes", tone: "outline" as const },
];
const RISING = [58, 58, 60, 60, 61, 63, 62, 64, 66, 66, 67, 68];

function MeterSpecimen({
  value,
  threshold,
  tone,
}: {
  value: number;
  threshold?: number;
  tone: "primary" | "error" | "neutral";
}) {
  return (
    <div className="w-full max-w-reading">
      <MeterBar
        value={value}
        tone={tone}
        threshold={threshold}
        thresholdLabel={threshold === undefined ? undefined : `Auto-label threshold ${threshold}%`}
        summary={`${value}%${threshold === undefined ? "" : `, threshold ${threshold}%`}`}
        table={{ caption: "Meter", rows: [["Value", `${value}%`]] }}
      />
    </div>
  );
}

const STRIPES: StripeTone[] = ["primary", "error", "verdict-review", "tertiary", "outline-variant"];

export function DisplaySections() {
  const toast = useToast();
  const [tab, setTab] = useState("following");
  const [kind, setKind] = useState<"opinion" | "fact" | null>(null);
  const [status, setStatus] = useState<string[]>(["all"]);
  const [multi, setMulti] = useState<string[]>(["fact"]);
  const [password, setPassword] = useState("correct horse");
  const [dismissed, setDismissed] = useState(false);

  return (
    <>
      <Section
        id="navigation"
        title="Tabs, SegmentedControl, FilterChips"
        note="Arrow keys, Home and End work on the tabs and the segmented control."
      >
        <Tabs
          label="Feed"
          idPrefix="gallery"
          value={tab}
          onChange={setTab}
          tabs={[
            { id: "following", label: "Following" },
            { id: "recent", label: "Recent", count: 12 },
            { id: "saved", label: "Saved" },
          ]}
        />
        {["following", "recent", "saved"].map((id) => (
          <TabPanel key={id} idPrefix="gallery" tab={id} selected={tab === id}>
            <p className="font-body-sm text-body-sm text-outline">Panel for {id}</p>
          </TabPanel>
        ))}
        <Specimen label="segmented control, nothing pre-selected" className="max-w-md">
          <SegmentedControl
            label="Post type"
            value={kind}
            onChange={setKind}
            options={[
              { value: "opinion", label: "Opinion", icon: "format_quote" },
              { value: "fact", label: "Fact", icon: "fact_check" },
            ]}
            className="w-full"
          />
        </Specimen>
        <Specimen label="filter chips: single choice, then multiple">
          <FilterChips
            label="Status"
            selected={status}
            onChange={setStatus}
            chips={[
              { id: "all", label: "All", count: 24 },
              { id: "verified", label: "Verified", dot: "primary", count: 9 },
              { id: "review", label: "Under review", dot: "verdict-review", count: 3 },
              { id: "false", label: "False", dot: "error", count: 4 },
              { id: "opinion", label: "Opinion", dot: "outline-variant" },
            ]}
          />
          <FilterChips
            label="Type"
            multiple
            selected={multi}
            onChange={setMulti}
            chips={[
              { id: "fact", label: "Facts" },
              { id: "opinion", label: "Opinions" },
            ]}
          />
        </Specimen>
      </Section>

      <Section
        id="badges"
        title="StatusBadge, CategoryChip, VerdictStripe"
        note="Every status is a glyph, a label and a colour. Labels always say FALSE."
      >
        <Specimen label="the nine rows of the ARCHITECTURE section 4 badge table">
          <CategoryChip type="opinion" />
          <StatusBadge status="pending" />
          <StatusBadge status="verified_true" verdictSource="pipeline" confidenceScore="94.00" />
          <StatusBadge status="verified_true" verdictSource="moderator" />
          <StatusBadge status="verified_false" verdictSource="pipeline" confidenceScore="88.00" />
          <StatusBadge status="verified_false" verdictSource="moderator" />
          <StatusBadge status="under_review" />
          <StatusBadge status="removed" />
          <EmergencyBadge />
        </Specimen>
        <Specimen label="category chip, appeal pending">
          <CategoryChip type="fact" />
          <AppealPendingBadge />
        </Specimen>
        <Specimen label="verdict stripes">
          {STRIPES.map((tone) => (
            <Card
              key={tone}
              className="h-16 w-40 pt-space-sm pl-space-md font-label-code text-label-code text-outline"
            >
              <VerdictStripe tone={tone} />
              {tone}
            </Card>
          ))}
        </Specimen>
      </Section>

      <Section id="avatars" title="Avatar">
        <Specimen label="sizes 6, 8, 10, 14, 20" className="items-center">
          {([6, 8, 10, 14, 20] as const).map((size) => (
            <Avatar key={size} name="Ada Lovelace" size={size} />
          ))}
        </Specimen>
        <Specimen
          label="a photo that fails to load falls back to initials"
          className="items-center"
        >
          <Avatar name="Grace Hopper" src="/dev/does-not-exist.webp" size={14} />
          <Avatar name="rumor" size={14} />
        </Specimen>
      </Section>

      <Section id="feedback" title="Alert, Toast, EmptyState, Skeleton, LoadMore, ProgressBar">
        <div className="grid max-w-wide gap-space-md md:grid-cols-2">
          <Alert tone="info" title="Verify your email">
            You can read everything now; posting needs a verified address.
          </Alert>
          <Alert tone="success">Your password was updated.</Alert>
          <Alert tone="warning" title="Under review">
            A moderator is taking another look at this post.
          </Alert>
          {!dismissed && (
            <Alert tone="error" title="Could not log in" onDismiss={() => setDismissed(true)}>
              The email or password is not right.
            </Alert>
          )}
          <Alert tone="neutral">We never show your email address to other people.</Alert>
        </div>
        <Specimen label="toast (static, and live via the button)" className="items-center">
          <Toast message="Link copied" />
          <Toast message="Post published" tone="success" />
          <Toast message="Could not save" tone="error" />
          <Button
            variant="secondary"
            onClick={() => toast.show("Saved just now", { tone: "success" })}
          >
            Show a live toast
          </Button>
        </Specimen>
        <Card className="max-w-reading">
          <EmptyState
            icon="verified"
            tone="success"
            title="You are all caught up"
            action={<Button variant="secondary">Refresh</Button>}
          >
            You have seen every post from the people you follow.
          </EmptyState>
        </Card>
        <Specimen label="skeleton card" className="max-w-reading">
          <Card className="w-full space-y-space-md p-space-lg">
            <div className="flex items-center gap-space-md">
              <Skeleton className="h-10 w-10 rounded-full" />
              <Skeleton className="h-4 w-40" />
            </div>
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-2/3" />
          </Card>
        </Specimen>
        <Specimen label="load more: idle, loading, at the end" className="items-start">
          <LoadMore hasMore onClick={() => {}} className="pb-0" />
          <LoadMore hasMore loading onClick={() => {}} className="pb-0" />
          <LoadMore hasMore={false} onClick={() => {}} className="pb-0" />
        </Specimen>
        <div className="max-w-form space-y-space-sm">
          <ProgressBar value={99} label="Credibility" />
          <ProgressBar value={60} label="Verified" tone="secondary" />
          <ProgressBar value={30} label="False" tone="error" />
        </div>
      </Section>

      <Section
        id="charts"
        title="Charts: MeterBar, StatTile, BarChart, RingGauge, Sparkline"
        note="Part 11D. Token-built HTML and SVG, no chart library; each graphic is an image with a summary and a hidden table beside it."
      >
        <Specimen label="MeterBar: TRUE 95% over a threshold of 85%, FALSE 90%, neutral without a tick">
          <MeterSpecimen value={95} threshold={85} tone="primary" />
          <MeterSpecimen value={90} threshold={85} tone="error" />
          <MeterSpecimen value={50} tone="neutral" />
        </Specimen>
        <Specimen label="StatTile">
          <StatTile label="Confidence" value="95%" className="w-48" />
          <StatTile label="Threshold and margin" value="85%" sub="+10 points" className="w-48" />
          <StatTile label="Time to verdict" value="2 min 14 s" className="w-48" />
        </Specimen>
        <Specimen label="BarChart: with data and the verdict day marked, then empty">
          <div className="w-full max-w-reading">
            <BarChart
              days={SPREAD_DAYS}
              series={SPREAD_SERIES}
              tableOnly={[{ key: "comments", label: "Comments" }]}
              markerDate="2026-10-02"
              markerLabel="Verdict"
              summary="Reposts and likes per day"
              caption="First 14 days after posting (UTC)"
            />
          </div>
          <div className="w-full max-w-reading">
            <BarChart
              days={EMPTY_DAYS}
              series={SPREAD_SERIES}
              summary="No reposts or likes yet"
              caption="First 14 days after posting (UTC)"
              emptyNote="No reposts or likes yet."
            />
          </div>
        </Specimen>
        <Specimen label="RingGauge: 68, New, 100">
          {[68, null, 100].map((value) => (
            <RingGauge
              key={String(value)}
              value={value}
              centre={
                <span className="font-headline-md text-headline-md text-on-surface">
                  {value ?? "New"}
                </span>
              }
              summary={`Credibility ${value ?? "New"}`}
              table={{ caption: "Credibility", rows: [["Score", String(value ?? "New")]] }}
            />
          ))}
        </Specimen>
        <Specimen label="Sparkline: rising, flat (does not zoom in), one point">
          {[RISING, [62, 62, 62, 62], [62]].map((values) => (
            <Sparkline
              key={values.join()}
              values={values}
              summary="Credibility, last 30 days"
              table={{
                caption: "Credibility, last 30 days",
                columns: ["Day", "Score"],
                rows: values.map((v, i) => [`Day ${i + 1}`, v]),
              }}
            />
          ))}
        </Specimen>
      </Section>

      <Section
        id="password-meter"
        title="PasswordStrengthMeter"
        note="Advisory scale: Weak, Fair, Good, Strong. The server validators decide what is accepted."
      >
        <div className="max-w-form space-y-space-md">
          <TextField
            label="Try a password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <PasswordStrengthMeter score={scorePassword(password)} />
        </div>
        <div className="grid max-w-wide gap-space-md md:grid-cols-4">
          {([1, 2, 3, 4] as const).map((score) => (
            <PasswordStrengthMeter key={score} score={score} />
          ))}
        </div>
      </Section>

      <Section id="danger" title="DangerZone">
        <div className="max-w-reading">
          <DangerZone tag="Irreversible">
            <DangerAction
              title="Delete account"
              description="Removes your profile and posts. This cannot be undone."
              action={<Button variant="destructive">Delete account</Button>}
            />
          </DangerZone>
        </div>
      </Section>
    </>
  );
}
