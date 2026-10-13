import { Icon } from "@/components/ui/Icon";
import type { Post } from "@/lib/api/types";

/**
 * The author's one line about their appeal, from `appeal_status` and where the post stands now.
 * The API doesn't send the kind of appeal, so the words fit both: "the decision stands" after a
 * FALSE label that was kept or a removal that was kept. `null` when there is no appeal.
 */
export function appealOutcomeText(post: Pick<Post, "status" | "appeal_status">): string | null {
  const lead = "You asked for another look.";
  switch (post.appeal_status) {
    case "open":
      return `${lead} A moderator who didn't make the first decision will review it.`;
    case "overturned":
      return `${lead} A moderator reversed the decision.`;
    case "upheld":
      if (post.status === "removed")
        return `${lead} A moderator reviewed it, and the post stays removed.`;
      if (post.status === "verified_false") {
        return `${lead} A moderator reviewed it, and the FALSE label stays.`;
      }
      return `${lead} A moderator reviewed it, and the decision stands.`;
    default:
      return null;
  }
}

/** What happened to your request. Only an author gets `appeal_status`, so only they see this. */
export function AppealOutcome({
  post,
  className,
}: {
  post: Pick<Post, "status" | "appeal_status">;
  className?: string;
}) {
  const text = appealOutcomeText(post);
  if (!text) return null;
  return (
    <p
      className={
        "flex items-start gap-space-xs font-body-sm text-body-sm text-on-surface-variant" +
        (className ? ` ${className}` : "")
      }
    >
      <Icon name="gavel" size="md" className="mt-0.5 shrink-0 text-outline" />
      <span>{text}</span>
    </p>
  );
}
