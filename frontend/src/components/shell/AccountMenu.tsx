"use client";

import { useRef } from "react";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import { isActive, type NavItem } from "./nav-items";
import { ShellLink } from "./ShellLink";

/** A menu entry that does something instead of opening a page (Log out). */
export interface MenuAction {
  label: string;
  icon: string;
  onSelect: () => void;
}

export interface AccountMenuProps {
  /** Referenced by the trigger's `popoverTarget`. */
  id: string;
  label: string;
  items: NavItem[];
  /** Rendered as buttons after the links. */
  actions?: MenuAction[];
  /** `rail`: a small menu above the sidebar's user card. `sheet`: a bottom sheet on phones. */
  placement: "rail" | "sheet";
  pathname: string;
}

/**
 * A native popover: the browser handles Esc, light dismiss and the top layer. A popover is centred
 * by default, so each placement sets all four sides itself.
 */
export function AccountMenu({
  id,
  label,
  items,
  actions = [],
  placement,
  pathname,
}: AccountMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  // Client-side navigation keeps the DOM, so close the menu when a link is chosen.
  const close = () => ref.current?.hidePopover?.();
  const entry = (active: boolean) =>
    cn(
      "flex w-full items-center gap-space-sm rounded-lg px-space-md font-body-md text-body-md transition-colors",
      placement === "sheet" ? "py-space-md" : "py-space-sm",
      active
        ? "bg-secondary font-semibold text-on-secondary"
        : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
    );

  return (
    <div
      ref={ref}
      id={id}
      popover="auto"
      className={cn(
        "fixed m-0 rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-xs text-on-surface shadow-sm",
        placement === "rail"
          ? "top-auto right-auto bottom-20 left-space-sm w-56"
          : "top-auto right-0 bottom-0 left-0 w-full pb-space-lg",
      )}
    >
      <nav aria-label={label}>
        <ul className="flex flex-col gap-space-xs">
          {items.map((item) => {
            const active = !item.external && isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <ShellLink item={item} active={active} onClick={close} className={entry(active)}>
                  <Icon name={item.icon} size="xl" />
                  <span>{item.label}</span>
                </ShellLink>
              </li>
            );
          })}
          {actions.map((action) => (
            <li key={action.label}>
              <button
                type="button"
                onClick={() => {
                  close();
                  action.onSelect();
                }}
                className={entry(false)}
              >
                <Icon name={action.icon} size="xl" />
                <span>{action.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
