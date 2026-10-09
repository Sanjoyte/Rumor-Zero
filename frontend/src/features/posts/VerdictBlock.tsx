import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import { formatConfidence } from "@/lib/format";
import type { Post } from "@/lib/api/types";
import { statusBadgeSpec } from "@/lib/post-display";

interface Explanation {
  title: string;
  body: string;
}

const INSET: Record<string, string> = {
  primary: "border-primary/20 bg-primary/5",
  error: "border-error/20 bg-error/5",
  review: "border-verdict-review/20 bg-verdict-review/5",
  "neutral-dashed": "border-outline-variant/30 bg-surface-container-low",
  neutral: "border-outline-variant/30 bg-surface-container-low",
};

const GLYPH_TONE: Record<string, string> = {
  primary: "text-primary",
  error: "text-error",
  review: "text-on-verdict-review",
  "neutral-dashed": "text-outline",
  neutral: "text-outline",
};

/** What the status means, in words (ARCHITECTURE §4; labels say FALSE, never "debunked"). */
export function explain(
  post: Pick<Post, "status" | "verdict_source" | "confidence_score">,
): Explanation {
  const how =
    post.verdict_source === "moderator"
      ? "Reviewed by a moderator"
      : post.verdict_source === "pipeline"
        ? `Checked automatically${
            formatConfidence(post.confidence_score)
              ? ` · ${formatConfidence(post.confidence_score)} confidence`
              : ""
          }`
        : "";
  switch (post.status) {
    case "pending":
      return {
        title: "Checking facts…",
        body: "We're checking this claim. This page updates on its own when there is a result.",
      };
    case "verified_true":
      return { title: how || "Verified", body: "This claim was found to be true." };
    case "verified_false":
      return { title: how || "FALSE", body: "This claim was found to be FALSE." };
    case "under_review":
      return {
        title: "Under review",
        body: "A moderator is taking a look at this post. The label changes once they decide.",
      };
    default:
      return { title: "", body: "" };
  }
}

/**
 * The verdict under the claim (Stitch b3's verification card, cut to what exists): the status in
 * words and, for a moderator's verdict, their public note. A published opinion has no verdict, only
 * one neutral line.
 */
export function VerdictBlock({ post }: { post: Post }) {
  if (post.post_type === "opinion" && post.status === "published") {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Opinions aren&apos;t fact-checked.
      </p>
    );
  }
  // A removed post (seen only by its author) is explained by the banner above the claim.
  if (post.status === "removed") return null;
  const spec = statusBadgeSpec({
    status: post.status,
    verdictSource: post.verdict_source,
    confidenceScore: post.confidence_score,
  });
  if (!spec) return null;
  const { title, body } = explain(post);
  const note = post.verdict_source === "moderator" ? post.verdict_note.trim() : "";
  return (
    <section aria-labelledby="verdict-heading" className="flex flex-col gap-space-md">
      <h2 id="verdict-heading" className="font-headline-sm text-headline-sm text-on-surface">
        Verdict
      </h2>
      <Card className="flex flex-col gap-space-md p-space-lg">
        <div
          className={cn(
            "flex items-start gap-space-sm rounded-lg border p-space-md",
            INSET[spec.tone],
          )}
        >
          <Icon
            name={spec.glyph}
            size="xl"
            className={cn(
              "mt-0.5 shrink-0",
              GLYPH_TONE[spec.tone],
              spec.spin && "animate-spin motion-reduce:animate-none",
            )}
          />
          <div className="flex min-w-0 flex-col gap-space-xs">
            <p className="font-label-code text-label-code font-bold tracking-wider text-on-surface uppercase">
              {title}
            </p>
            <p className="font-body-sm text-body-sm text-on-surface-variant">{body}</p>
          </div>
        </div>
        {note && (
          <blockquote className="font-body-sm text-body-sm break-words whitespace-pre-wrap text-on-surface-variant">
            <span className="font-label-code text-label-code font-semibold tracking-wider text-outline uppercase">
              Moderator&apos;s note
            </span>
            <br />
            {note}
          </blockquote>
        )}
      </Card>
    </section>
  );
}
