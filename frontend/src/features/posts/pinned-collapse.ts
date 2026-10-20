/**
 * Which pinned emergencies a reader folded away with ×, per feed and per browser tab
 * (sessionStorage, Part 11C; user decision 2026-10-19). Written only by a click on × or Show, never
 * before; a post pinned after the × opens the section again. Storage can be missing or refuse
 * (a private window, blocked site data): every access is guarded, and the fold is then kept in
 * memory until the page reloads. No token is ever stored here.
 */
import type { PinnedFeed } from "./posts-api";

const listeners = new Set<() => void>();
/** Where the fold lives when sessionStorage refuses. */
const memory = new Map<string, string>();

export function collapseKey(feed: PinnedFeed): string {
  return `rz:pinned-collapsed:${feed}`;
}

/** The raw stored value (a string is a stable snapshot for `useSyncExternalStore`), or null. */
export function readCollapsed(feed: PinnedFeed): string | null {
  try {
    return window.sessionStorage.getItem(collapseKey(feed));
  } catch {
    return memory.get(collapseKey(feed)) ?? null;
  }
}

/** The ids folded away, from the raw value; anything malformed counts as none. */
export function parseCollapsed(raw: string | null): ReadonlySet<string> {
  if (!raw) return new Set();
  try {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? new Set(value.filter((id) => typeof id === "string")) : new Set();
  } catch {
    return new Set();
  }
}

function notify() {
  listeners.forEach((listener) => listener());
}

/** × : remember these ids as folded for this tab. */
export function collapse(feed: PinnedFeed, ids: readonly string[]) {
  const raw = JSON.stringify(ids);
  try {
    window.sessionStorage.setItem(collapseKey(feed), raw);
  } catch {
    memory.set(collapseKey(feed), raw);
  }
  notify();
}

/** Show: open the section again. */
export function expand(feed: PinnedFeed) {
  memory.delete(collapseKey(feed));
  try {
    window.sessionStorage.removeItem(collapseKey(feed));
  } catch {
    // Nothing more to forget.
  }
  notify();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
