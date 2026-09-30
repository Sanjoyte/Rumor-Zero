"use client";

import { type KeyboardEvent, type ReactNode, useId, useRef } from "react";
import { cn } from "@/lib/cn";

export interface TabItem {
  id: string;
  label: string;
  /** Optional count chip (Stitch b4). */
  count?: number;
}

export interface TabsProps {
  tabs: TabItem[];
  value: string;
  onChange: (id: string) => void;
  /** Name of the tab list for assistive tech. */
  label: string;
  /** Needed only when a TabPanel should be tied to these tabs; pass the same prefix to it. */
  idPrefix?: string;
  className?: string;
}

export const tabId = (prefix: string, id: string) => `${prefix}-tab-${id}`;
export const panelId = (prefix: string, id: string) => `${prefix}-panel-${id}`;

/**
 * Underline tabs (Stitch b1 and b4). ARIA tablist: arrow keys, Home and End move the selection.
 * The underline lives inside the selected tab, so it moves with the selection (Stitch b1 did not).
 */
export function Tabs({ tabs, value, onChange, label, idPrefix, className }: TabsProps) {
  const autoPrefix = useId();
  const prefix = idPrefix ?? autoPrefix;
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function move(nextIndex: number) {
    const next = tabs[(nextIndex + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const keys: Record<string, () => void> = {
      ArrowRight: () => move(index + 1),
      ArrowLeft: () => move(index - 1),
      Home: () => move(0),
      End: () => move(tabs.length - 1),
    };
    const handler = keys[event.key];
    if (handler) {
      event.preventDefault();
      handler();
    }
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "flex items-center gap-space-xl border-b border-outline-variant/30 pb-space-md",
        className,
      )}
    >
      {tabs.map((tab, index) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(node) => {
              refs.current[tab.id] = node;
            }}
            id={tabId(prefix, tab.id)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId(prefix, tab.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "relative flex items-center gap-space-sm pb-space-xs font-label-code text-label-code uppercase transition-colors",
              selected ? "font-bold text-on-surface" : "text-outline hover:text-on-surface",
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span
                className={cn(
                  "rounded-lg bg-surface-container px-space-sm py-0.5 font-label-code text-label-code",
                  selected ? "text-on-surface-variant" : "text-outline",
                )}
              >
                {tab.count}
              </span>
            )}
            {selected && (
              <span
                aria-hidden="true"
                className="absolute right-0 -bottom-[15px] left-0 h-[2px] bg-secondary"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export interface TabPanelProps {
  idPrefix: string;
  tab: string;
  selected: boolean;
  children: ReactNode;
  className?: string;
}

export function TabPanel({ idPrefix, tab, selected, children, className }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      id={panelId(idPrefix, tab)}
      aria-labelledby={tabId(idPrefix, tab)}
      hidden={!selected}
      className={className}
    >
      {children}
    </div>
  );
}
