import { Icon } from "@/components/ui/Icon";
import type { Post } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { emergencyShown } from "@/lib/post-display";

/**
 * The post page's neutral note once an emergency's priority is over (§4b, Part 11C): "Posted as an
 * emergency on Oct 19, 2026. Priority ended." (it expired or was labelled FALSE) or "… Priority
 * removed by a moderator." (Demote). Grey, never violet: the card looks like any other post now.
 */
export function EmergencyNote({ post }: { post: Post }) {
  if (!post.is_emergency || emergencyShown(post) || post.status === "removed") return null;
  return (
    <p className="flex items-start gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
      <Icon name="history" className="mt-0.5 shrink-0 text-outline" />
      <span>
        Posted as an emergency on {formatDate(post.created_at)}.{" "}
        {post.emergency_demoted ? "Priority removed by a moderator." : "Priority ended."}
      </span>
    </p>
  );
}
