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
  children: ReactNode;
}

/** One shell destination: `aria-current="page"` when active; external links open a new tab. */
export function ShellLink({ item, active, className, title, onClick, children }: ShellLinkProps) {
  if (item.external) {
    return (
      <a
        href={item.href}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
        title={title}
        onClick={onClick}
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
      className={className}
      title={title}
      onClick={onClick}
    >
      {children}
    </Link>
  );
}
