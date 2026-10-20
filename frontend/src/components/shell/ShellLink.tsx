import Link from "next/link";
import type { MouseEventHandler, ReactNode } from "react";
import type { NavItem } from "./nav-items";

export interface ShellLinkProps {
  item: NavItem;
  active?: boolean;
  className?: string;
  /** Shown as a tooltip where the label is visually hidden (the tablet icon dock). */
  title?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
  /**
   * The link's whole accessible name, when its content can't give it: "Notifications, 3 unread"
   * (the unread count is a badge, and browsers put a space before text in a separate hidden span).
   */
  label?: string;
  children: ReactNode;
}

/** One shell destination: `aria-current="page"` when active; external links open a new tab. */
export function ShellLink({
  item,
  active,
  className,
  title,
  onClick,
  label,
  children,
}: ShellLinkProps) {
  if (item.external) {
    return (
      <a
        href={item.href}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
        title={title}
        onClick={onClick}
        aria-label={label}
      >
        {children}
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    );
  }
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      aria-label={label}
      className={className}
      title={title}
      onClick={onClick}
    >
      {children}
    </Link>
  );
}
