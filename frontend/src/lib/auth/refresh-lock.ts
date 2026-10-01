/**
 * Serialises token refreshes across tabs with the Web Locks API (ARCHITECTURE §7), so two tabs
 * can't both spend the same rotating refresh token. Where Web Locks are missing, refreshes are at
 * least serialised within the tab.
 */
export const REFRESH_LOCK_NAME = "rz-refresh";

let inTabQueue: Promise<unknown> = Promise.resolve();

export function withRefreshLock<T>(task: () => Promise<T>): Promise<T> {
  const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
  if (locks && typeof locks.request === "function") {
    return locks.request(REFRESH_LOCK_NAME, () => task()) as Promise<T>;
  }
  const run = inTabQueue.then(task, task);
  inTabQueue = run.catch(() => undefined);
  return run;
}
