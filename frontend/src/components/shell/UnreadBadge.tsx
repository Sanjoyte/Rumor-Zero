import { cn } from "@/lib/cn";

/** The number shown in the badge: exact up to 99, then "99+". */
export function badgeNumber(count: number): string {
  return count > 99 ? "99+" : String(count);
}

export interface UnreadBadgeProps {
  count: number;
  /** `pill` sits after the label in the full rail; `corner` sits on the icon (dock and tabs). */
  variant: "pill" | "corner";
  /** On the active item, which is already `bg-secondary`: swap the colours so it still shows. */
  inverted?: boolean;
  className?: string;
}

/**
 * The unread count on the Notifications link (ARCHITECTURE §10). Visual only: the link's own name
 * carries ", N unread" for assistive tech (`unreadHint`), so this is `aria-hidden`. Nothing for 0.
 */
export function UnreadBadge({ count, variant, inverted, className }: UnreadBadgeProps) {
  if (count <= 0) return null;
  return (
    <span
      aria-hidden="true"
      data-testid="unread-badge"
      className={cn(
        "inline-flex items-center justify-center rounded-full font-label-badge text-label-badge font-bold",
        variant === "pill" ? "min-w-5 px-space-xs py-0.5" : "absolute -top-1 -right-2 min-w-4 px-1",
        inverted ? "bg-on-secondary text-secondary" : "bg-secondary text-on-secondary",
        className,
      )}
    >
      {badgeNumber(count)}
    </span>
  );
}

/** The spoken addition to the link's name: ", 3 unread" (empty for 0). */
export function unreadHint(count: number): string {
  return count > 0 ? `, ${badgeNumber(count)} unread` : "";
}
