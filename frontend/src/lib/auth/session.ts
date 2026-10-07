/**
 * The browser's auth session (ARCHITECTURE §7), free of React so it can be unit-tested with fake
 * timers, and as two "tabs" sharing one fake backend.
 *
 * - The access token lives only in memory (`store`). The refresh token is the httpOnly cookie.
 * - Bootstrap: without the `rz_session` hint there is nothing to refresh, so the visitor is
 *   anonymous at once. Otherwise refresh, then load `/me`.
 * - Refresh is single-flight in a tab, and only the refresh POST runs inside the cross-tab lock
 *   (Web Locks aren't re-entrant, so `/me` or a retried request must never wait on it).
 * - The next refresh is scheduled at max(lifetime / 2, lifetime − 60 s) after a token arrives,
 *   measured from its arrival, so the browser's clock doesn't matter. A tab coming back into view
 *   refreshes at once if one is due.
 * - A refresh answered 400/401/403/410 means the session is gone (anonymous). A network error or
 *   5xx is transient: the state stays and the refresh is retried after 2 s, 5 s, 15 s, then every
 *   30 s while the tab is visible.
 * - Login and logout are broadcast to the other tabs, and so is "the user changed" (the email got
 *   verified), which makes the other authenticated tabs reload `/me` (and nothing else).
 */
import { ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import type { AuthApi, SignupInput } from "./auth-api";
import { tokenClaims, tokenLifetimeSeconds } from "./jwt";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export interface AuthState {
  status: AuthStatus;
  user: Me | null;
}

export type RefreshOutcome = "ok" | "invalid" | "transient";

export interface Clock {
  now(): number;
  setTimeout(callback: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
}

export interface TokenStore {
  get(): string | null;
  set(token: string | null): void;
}

export type AuthMessage = { type: "login" } | { type: "logout" } | { type: "user-changed" };

export interface AuthChannel {
  post(message: AuthMessage): void;
  subscribe(listener: (message: AuthMessage) => void): () => void;
}

export interface Visibility {
  isVisible(): boolean;
  /** Called whenever the tab becomes visible. */
  onVisible(listener: () => void): () => void;
}

export interface SessionDeps {
  api: AuthApi;
  /** Serialises refresh and logout across tabs (`withRefreshLock`). */
  lock: <T>(task: () => Promise<T>) => Promise<T>;
  store: TokenStore;
  hasHint: () => boolean;
  clock?: Clock;
  channel?: AuthChannel | null;
  visibility?: Visibility;
  logError?: (message: string) => void;
}

/** Transient-failure retries; the last delay repeats. */
export const RETRY_DELAYS_MS = [2_000, 5_000, 15_000, 30_000] as const;
/** A 401 this soon after a refresh is just retried with the new token. */
export const RECENT_REFRESH_MS = 10_000;
export const EARLY_REFRESH_SECONDS = 60;

const INVALID_STATUSES = new Set([400, 401, 403, 410]);

export function refreshDelayMs(lifetimeSeconds: number): number {
  return Math.max(lifetimeSeconds / 2, lifetimeSeconds - EARLY_REFRESH_SECONDS) * 1000;
}

function isInvalid(error: unknown): boolean {
  return error instanceof ApiError && INVALID_STATUSES.has(error.status);
}

const systemClock: Clock = {
  now: () => Date.now(),
  setTimeout: (callback, ms) => setTimeout(callback, ms),
  clearTimeout: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

const ANONYMOUS: AuthState = { status: "anonymous", user: null };

export class AuthSession {
  private state: AuthState = { status: "loading", user: null };
  private readonly listeners = new Set<() => void>();
  private readonly clock: Clock;
  private readonly cleanups: (() => void)[] = [];
  private bootstrapping: Promise<void> | null = null;
  private refreshing: Promise<RefreshOutcome> | null = null;
  private refreshTimer: unknown = null;
  private retryTimer: unknown = null;
  private retryIndex = 0;
  private retryWaiting = false;
  private dueAt: number | null = null;
  private lastRefreshAt: number | null = null;
  /** Bumped whenever the identity changes, so a stale async result is dropped. */
  private generation = 0;

  constructor(private readonly deps: SessionDeps) {
    this.clock = deps.clock ?? systemClock;
    if (deps.channel) this.cleanups.push(deps.channel.subscribe((m) => this.onMessage(m)));
    if (deps.visibility) this.cleanups.push(deps.visibility.onVisible(() => this.onVisible()));
  }

  getState = (): AuthState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /** Runs once per session, however often it is called (React StrictMode runs effects twice). */
  bootstrap(): Promise<void> {
    this.bootstrapping ??= this.start();
    return this.bootstrapping;
  }

  /** Refresh now, or join the refresh already running in this tab. */
  refresh(): Promise<RefreshOutcome> {
    this.refreshing ??= this.runRefresh().finally(() => {
      this.refreshing = null;
    });
    return this.refreshing;
  }

  /** The API client's 401 hook: true means "retry the request with the current token". */
  async handleUnauthorized(): Promise<boolean> {
    if (this.state.status === "anonymous") return false;
    const recent =
      this.lastRefreshAt !== null && this.clock.now() - this.lastRefreshAt < RECENT_REFRESH_MS;
    if (recent && this.deps.store.get()) return true;
    return (await this.refresh()) === "ok";
  }

  async login(email: string, password: string): Promise<void> {
    await this.signIn(await this.deps.api.login(email, password));
  }

  async signup(input: SignupInput): Promise<void> {
    await this.signIn(await this.deps.api.signup(input));
  }

  /** On failure this throws and changes nothing: the user is still logged in. */
  async logout(): Promise<void> {
    await this.deps.lock(() => this.deps.api.logout());
    this.becomeAnonymous();
    this.deps.channel?.post({ type: "logout" });
  }

  /** Sign in with an access token that another call returned (the password reset logs in). */
  async signInWithToken(token: string): Promise<void> {
    await this.signIn(token);
  }

  /** Load `/me` again, e.g. after the profile changed, and tell the other tabs to do the same. */
  async reloadMe(): Promise<void> {
    if (await this.loadMe()) this.deps.channel?.post({ type: "user-changed" });
  }

  dispose(): void {
    this.clearTimers();
    for (const cleanup of this.cleanups.splice(0)) cleanup();
    this.listeners.clear();
  }

  // ---------- internals ----------

  /** Load `/me` with the current token. Never posts, so a tab reacting to a message can't echo. */
  private async loadMe(): Promise<boolean> {
    const token = this.deps.store.get();
    if (!token) return false;
    const generation = this.generation;
    const user = await this.deps.api.fetchMe(token);
    if (generation !== this.generation) return false;
    this.setState({ status: "authenticated", user });
    return true;
  }

  private async start(): Promise<void> {
    if (!this.deps.hasHint()) {
      this.setState(ANONYMOUS);
      return;
    }
    await this.refresh();
  }

  private async runRefresh(): Promise<RefreshOutcome> {
    const generation = this.generation;
    let token: string;
    try {
      token = await this.deps.lock(() => this.deps.api.refresh());
    } catch (error) {
      if (generation !== this.generation) return "invalid";
      return this.failed(error);
    }
    if (generation !== this.generation) return "invalid";
    this.acceptToken(token);

    // A new account may have logged in through the shared cookie in another tab.
    const sub = tokenClaims(token)?.sub;
    if (this.state.user && this.state.status === "authenticated" && sub === this.state.user.id) {
      return "ok";
    }
    try {
      const user = await this.deps.api.fetchMe(token);
      if (generation !== this.generation) return "invalid";
      this.setState({ status: "authenticated", user });
      return "ok";
    } catch (error) {
      if (generation !== this.generation) return "invalid";
      return this.failed(error);
    }
  }

  private failed(error: unknown): RefreshOutcome {
    if (isInvalid(error)) {
      if (error instanceof ApiError && error.status === 403) {
        // Only the CSRF guard answers 403 here: FRONTEND_ORIGIN or the relay is misconfigured.
        (this.deps.logError ?? console.error)(
          "Token refresh was refused (403). Check FRONTEND_ORIGIN and the API relay.",
        );
      }
      this.becomeAnonymous();
      return "invalid";
    }
    this.scheduleRetry();
    return "transient";
  }

  private async signIn(token: string): Promise<void> {
    this.generation += 1;
    const generation = this.generation;
    this.clearTimers();
    this.acceptToken(token);
    const user = await this.deps.api.fetchMe(token);
    if (generation !== this.generation) return;
    this.setState({ status: "authenticated", user });
    this.deps.channel?.post({ type: "login" });
  }

  private acceptToken(token: string): void {
    this.deps.store.set(token);
    this.lastRefreshAt = this.clock.now();
    this.retryIndex = 0;
    this.retryWaiting = false;
    this.clearTimer("retry");
    this.scheduleRefresh(token);
  }

  private scheduleRefresh(token: string): void {
    this.clearTimer("refresh");
    const claims = tokenClaims(token);
    if (!claims) {
      // Unreadable: the 401 hook will refresh when the API refuses it.
      this.dueAt = null;
      return;
    }
    const delay = refreshDelayMs(tokenLifetimeSeconds(claims));
    this.dueAt = this.clock.now() + delay;
    this.refreshTimer = this.clock.setTimeout(() => {
      this.refreshTimer = null;
      void this.refresh();
    }, delay);
  }

  private scheduleRetry(): void {
    this.clearTimer("retry");
    const delay = RETRY_DELAYS_MS[Math.min(this.retryIndex, RETRY_DELAYS_MS.length - 1)];
    this.retryIndex += 1;
    this.retryTimer = this.clock.setTimeout(() => {
      this.retryTimer = null;
      if (this.isVisible()) void this.refresh();
      else this.retryWaiting = true;
    }, delay);
  }

  private onVisible(): void {
    if (this.state.status === "anonymous") return;
    const overdue = this.dueAt !== null && this.clock.now() >= this.dueAt;
    if (overdue || this.retryWaiting) {
      this.retryWaiting = false;
      void this.refresh();
    }
  }

  private onMessage(message: AuthMessage): void {
    switch (message.type) {
      case "logout":
        this.becomeAnonymous();
        break;
      case "login":
        // Another tab logged in, so the cookie (and the hint) now exist.
        if (this.state.status !== "authenticated") void this.refresh();
        break;
      case "user-changed":
        // Only a signed-in tab has anything to reload; an anonymous one must not treat this as a
        // login. A failure is harmless: the state stays and the next refresh catches up.
        if (this.state.status === "authenticated") this.loadMe().catch(() => {});
        break;
    }
  }

  private isVisible(): boolean {
    return this.deps.visibility?.isVisible() ?? true;
  }

  private becomeAnonymous(): void {
    this.generation += 1;
    this.clearTimers();
    this.dueAt = null;
    this.lastRefreshAt = null;
    this.retryIndex = 0;
    this.retryWaiting = false;
    this.deps.store.set(null);
    this.setState(ANONYMOUS);
  }

  private clearTimer(which: "refresh" | "retry"): void {
    const handle = which === "refresh" ? this.refreshTimer : this.retryTimer;
    if (handle !== null) this.clock.clearTimeout(handle);
    if (which === "refresh") this.refreshTimer = null;
    else this.retryTimer = null;
  }

  private clearTimers(): void {
    this.clearTimer("refresh");
    this.clearTimer("retry");
  }

  private setState(next: AuthState): void {
    if (next.status === this.state.status && next.user === this.state.user) return;
    this.state = next;
    for (const listener of this.listeners) listener();
  }
}
