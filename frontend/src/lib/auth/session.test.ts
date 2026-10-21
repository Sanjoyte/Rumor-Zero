import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { ApiError, setUnauthorizedHandler } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { authApi, type AuthApi } from "./auth-api";
import {
  AuthSession,
  RETRY_DELAYS_MS,
  refreshDelayMs,
  type AuthChannel,
  type AuthMessage,
  type SessionDeps,
  type TokenStore,
} from "./session";

// ---------- helpers ----------

function base64url(value: object): string {
  return btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

/** An unsigned access token with the claims the session reads. */
function accessToken(sub: string, lifetimeSeconds = 900, serial = 0): string {
  const iat = 1_800_000_000 + serial;
  return `${base64url({ alg: "HS256" })}.${base64url({ sub, iat, exp: iat + lifetimeSeconds, n: serial })}.sig`;
}

function me(id = "user-1", username = "ada"): Me {
  return {
    id,
    username,
    display_name: "",
    bio: "",
    email: `${username}@example.test`,
    is_email_verified: false,
    role: "user",
    has_usable_password: true,
    google_connected: false,
    avatar_url: null,
    avatar_uploads_blocked: false,
    public_score: null,
  };
}

const apiError = (status: number, code = `http_${status}`) =>
  new ApiError({ status, code, detail: code });

function memoryStore(): TokenStore & { value: string | null } {
  return {
    value: null,
    get() {
      return this.value;
    },
    set(token) {
      this.value = token;
    },
  };
}

function fakeVisibility() {
  let visible = true;
  const listeners = new Set<() => void>();
  return {
    isVisible: () => visible,
    onVisible: (listener: () => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    set(next: boolean) {
      visible = next;
      if (next) listeners.forEach((listener) => listener());
    },
  };
}

/** Like BroadcastChannel: a message reaches every other tab, never the sender. */
function fakeBus() {
  const all = new Set<(message: AuthMessage) => void>();
  return {
    channel(): AuthChannel {
      const mine = new Set<(message: AuthMessage) => void>();
      return {
        post: (message) => all.forEach((listener) => !mine.has(listener) && listener(message)),
        subscribe: (listener) => {
          all.add(listener);
          mine.add(listener);
          return () => all.delete(listener);
        },
      };
    },
  };
}

/** A queue that serialises tasks, like the Web Lock shared by every tab of a browser. */
function sharedLock(): SessionDeps["lock"] {
  let queue: Promise<unknown> = Promise.resolve();
  return <T>(task: () => Promise<T>) => {
    const run = queue.then(task, task);
    queue = run.catch(() => undefined);
    return run;
  };
}

const noLock: SessionDeps["lock"] = (task) => task();

type MockedApi = { [K in keyof AuthApi]: Mock<AuthApi[K]> };

function fakeApi(overrides: Partial<AuthApi> = {}): MockedApi {
  return {
    login: vi.fn(async () => accessToken("user-1")),
    signup: vi.fn(async () => accessToken("user-1")),
    refresh: vi.fn(async () => accessToken("user-1")),
    logout: vi.fn(async () => undefined),
    fetchMe: vi.fn(async () => me()),
    ...overrides,
  } as MockedApi;
}

const sessions: AuthSession[] = [];

function makeSession(deps: Partial<SessionDeps> = {}) {
  const store = memoryStore();
  const api = fakeApi();
  const session = new AuthSession({
    api,
    lock: noLock,
    store,
    hasHint: () => true,
    logError: vi.fn(),
    ...deps,
  });
  sessions.push(session);
  return { session, store, api: deps.api ?? api };
}

afterEach(() => {
  sessions.splice(0).forEach((session) => session.dispose());
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
});

// ---------- bootstrap ----------

describe("bootstrap", () => {
  it("is anonymous at once without the hint, and makes no request", async () => {
    const api = fakeApi();
    const { session } = makeSession({ api, hasHint: () => false });
    expect(session.getState().status).toBe("loading");
    await session.bootstrap();
    expect(session.getState()).toEqual({ status: "anonymous", user: null });
    expect(api.refresh).not.toHaveBeenCalled();
    expect(api.fetchMe).not.toHaveBeenCalled();
  });

  it("refreshes, loads /me and keeps the token in memory", async () => {
    const { session, store, api } = makeSession();
    await session.bootstrap();
    expect(session.getState()).toEqual({ status: "authenticated", user: me() });
    expect(store.value).toBe(accessToken("user-1"));
    expect(api.fetchMe).toHaveBeenCalledWith(accessToken("user-1"));
  });

  it("runs once, however often it is called", async () => {
    const { session, api } = makeSession();
    await Promise.all([session.bootstrap(), session.bootstrap()]);
    await session.bootstrap();
    expect(api.refresh).toHaveBeenCalledTimes(1);
  });

  it.each([400, 401, 403, 410])("treats a %i refresh as no session", async (status) => {
    const api = fakeApi({ refresh: vi.fn(async () => Promise.reject(apiError(status))) });
    const logError = vi.fn();
    const { session, store } = makeSession({ api, logError });
    await session.bootstrap();
    expect(session.getState().status).toBe("anonymous");
    expect(store.value).toBeNull();
    expect(logError).toHaveBeenCalledTimes(status === 403 ? 1 : 0);
  });

  it("goes anonymous, without a deadlock, when /me answers 401 (real client)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        String(url).endsWith("/tokens/refresh")
          ? Response.json({ status: 200, data: { access_token: accessToken("gone") } })
          : Response.json({ detail: "No.", code: "authentication_failed" }, { status: 401 }),
      ),
    );
    const { session } = makeSession({ api: authApi, lock: sharedLock() });
    setUnauthorizedHandler(() => session.handleUnauthorized());
    await session.bootstrap();
    expect(session.getState().status).toBe("anonymous");
  });
});

// ---------- schedule ----------

describe("scheduled refresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("refreshes 60 s before expiry, or at half-life for short tokens", () => {
    expect(refreshDelayMs(900)).toBe(840_000);
    expect(refreshDelayMs(60)).toBe(30_000);
    expect(refreshDelayMs(100)).toBe(50_000);
  });

  it("fires at the scheduled time, measured from when the token arrived", async () => {
    const { session, api } = makeSession();
    await session.bootstrap();
    await vi.advanceTimersByTimeAsync(839_000);
    expect(api.refresh).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(api.refresh).toHaveBeenCalledTimes(2);
    // ...and again, one lifetime-minus-60 s after the new token.
    await vi.advanceTimersByTimeAsync(840_000);
    expect(api.refresh).toHaveBeenCalledTimes(3);
  });

  it("catches up when the tab becomes visible after missing its timer", async () => {
    const visibility = fakeVisibility();
    const { session, api } = makeSession({ visibility });
    await session.bootstrap();
    visibility.set(false);
    // A sleeping laptop: the clock jumps, the timer hasn't fired yet.
    vi.setSystemTime(Date.now() + 900_000);
    visibility.set(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(api.refresh).toHaveBeenCalledTimes(2);
  });

  it("doesn't refresh on visibility when nothing is due", async () => {
    const visibility = fakeVisibility();
    const { session, api } = makeSession({ visibility });
    await session.bootstrap();
    visibility.set(false);
    visibility.set(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(api.refresh).toHaveBeenCalledTimes(1);
  });
});

// ---------- transient failures ----------

describe("transient failures", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it.each([0, 500, 502, 503])("keeps the state after a %i and backs off", async (status) => {
    const refresh = vi.fn(async (): Promise<string> => Promise.reject(apiError(status)));
    const { session } = makeSession({ api: fakeApi({ refresh }) });
    await session.bootstrap();
    expect(session.getState().status).toBe("loading");

    const elapsed: number[] = [];
    for (const delay of [...RETRY_DELAYS_MS, 30_000]) {
      await vi.advanceTimersByTimeAsync(delay - 1);
      elapsed.push(refresh.mock.calls.length);
      await vi.advanceTimersByTimeAsync(1);
    }
    // 1 at bootstrap, then one more exactly at 2 s, 5 s, 15 s, 30 s and 30 s.
    expect(elapsed).toEqual([1, 2, 3, 4, 5]);
    expect(refresh).toHaveBeenCalledTimes(6);
    expect(session.getState().status).toBe("loading");
  });

  it("recovers on the next try, and an authenticated tab stays authenticated meanwhile", async () => {
    let fail = false;
    const refresh = vi.fn(async () => {
      if (fail) throw apiError(503, "backend_waking");
      return accessToken("user-1");
    });
    const { session } = makeSession({ api: fakeApi({ refresh }) });
    await session.bootstrap();
    fail = true;
    await vi.advanceTimersByTimeAsync(840_000);
    expect(session.getState().status).toBe("authenticated");
    fail = false;
    await vi.advanceTimersByTimeAsync(2_000);
    expect(refresh).toHaveBeenCalledTimes(3);
    expect(session.getState().status).toBe("authenticated");
  });

  it("waits for the tab to be visible before retrying", async () => {
    const visibility = fakeVisibility();
    const refresh = vi.fn(async (): Promise<string> => Promise.reject(apiError(0)));
    const { session } = makeSession({ api: fakeApi({ refresh }), visibility });
    await session.bootstrap();
    visibility.set(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(refresh).toHaveBeenCalledTimes(1);
    visibility.set(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(refresh).toHaveBeenCalledTimes(2);
  });
});

// ---------- the API client's 401 hook ----------

describe("handleUnauthorized", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("just retries right after a refresh, and refreshes once later on", async () => {
    const { session, api } = makeSession();
    await session.bootstrap();
    expect(await session.handleUnauthorized()).toBe(true);
    expect(api.refresh).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(11_000);
    expect(await session.handleUnauthorized()).toBe(true);
    expect(api.refresh).toHaveBeenCalledTimes(2);
  });

  it("shares one refresh between concurrent 401s", async () => {
    const { session, api } = makeSession();
    await session.bootstrap();
    await vi.advanceTimersByTimeAsync(11_000);
    await Promise.all([session.handleUnauthorized(), session.handleUnauthorized()]);
    expect(api.refresh).toHaveBeenCalledTimes(2);
  });

  it("declines when anonymous or when the refresh fails", async () => {
    const anonymous = makeSession({ hasHint: () => false });
    await anonymous.session.bootstrap();
    expect(await anonymous.session.handleUnauthorized()).toBe(false);
    expect(anonymous.api.refresh).not.toHaveBeenCalled();

    let calls = 0;
    const refresh = vi.fn(async () => {
      calls += 1;
      if (calls > 1) throw apiError(400);
      return accessToken("user-1");
    });
    const { session } = makeSession({ api: fakeApi({ refresh }) });
    await session.bootstrap();
    await vi.advanceTimersByTimeAsync(11_000);
    expect(await session.handleUnauthorized()).toBe(false);
    expect(session.getState().status).toBe("anonymous");
  });
});

// ---------- identity ----------

describe("login, signup, logout and other tabs", () => {
  it("logs in, loads /me and tells the other tabs", async () => {
    const bus = fakeBus();
    const tabA = makeSession({ hasHint: () => false, channel: bus.channel() });
    const tabB = makeSession({ hasHint: () => false, channel: bus.channel() });
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);

    await tabA.session.login("ada@example.test", "pw");
    expect(tabA.api.login).toHaveBeenCalledWith("ada@example.test", "pw");
    expect(tabA.session.getState()).toEqual({ status: "authenticated", user: me() });
    // The anonymous tab heard about it and refreshed with the new cookie.
    await vi.waitFor(() => expect(tabB.session.getState().status).toBe("authenticated"));
    expect(tabB.api.refresh).toHaveBeenCalledTimes(1);
  });

  it("signs up the same way", async () => {
    const { session, api } = makeSession({ hasHint: () => false });
    await session.bootstrap();
    const input = { email: "a@b.c", username: "ada", password: "pw", turnstileToken: "t" };
    await session.signup(input);
    expect(api.signup).toHaveBeenCalledWith(input);
    expect(session.getState().status).toBe("authenticated");
  });

  it("a failed login changes nothing", async () => {
    const api = fakeApi({ login: vi.fn(async () => Promise.reject(apiError(400))) });
    const { session, store } = makeSession({ api, hasHint: () => false });
    await session.bootstrap();
    await expect(session.login("a@b.c", "bad")).rejects.toMatchObject({ status: 400 });
    expect(session.getState().status).toBe("anonymous");
    expect(store.value).toBeNull();
  });

  it("logs out inside the lock, clears everything and tells the other tabs", async () => {
    const bus = fakeBus();
    const shared = sharedLock();
    let lockCalls = 0;
    const lock: SessionDeps["lock"] = (task) => {
      lockCalls += 1;
      return shared(task);
    };
    const tabA = makeSession({ channel: bus.channel(), lock });
    const tabB = makeSession({ channel: bus.channel() });
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);

    await tabA.session.logout();
    expect(lockCalls).toBe(2); // the bootstrap refresh, then the logout
    expect(tabA.session.getState()).toEqual({ status: "anonymous", user: null });
    expect(tabA.store.value).toBeNull();
    expect(tabB.session.getState().status).toBe("anonymous");
    expect(tabB.store.value).toBeNull();
  });

  it("ends the session without a request and tells the other tabs (the account was deleted)", async () => {
    const bus = fakeBus();
    const tabA = makeSession({ channel: bus.channel() });
    const tabB = makeSession({ channel: bus.channel() });
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);

    tabA.session.endSession();

    expect(tabA.session.getState()).toEqual({ status: "anonymous", user: null });
    expect(tabA.store.value).toBeNull();
    expect(tabA.api.logout).not.toHaveBeenCalled();
    expect(tabB.session.getState().status).toBe("anonymous");
    expect(tabB.store.value).toBeNull();
  });

  it("a failed logout throws and keeps you logged in", async () => {
    const api = fakeApi({ logout: vi.fn(async () => Promise.reject(apiError(0))) });
    const { session, store } = makeSession({ api });
    await session.bootstrap();
    await expect(session.logout()).rejects.toMatchObject({ status: 0 });
    expect(session.getState().status).toBe("authenticated");
    expect(store.value).toBe(accessToken("user-1"));
  });

  it("reloads /me when a refresh brings another account's token", async () => {
    vi.useFakeTimers();
    let sub = "user-1";
    const api = fakeApi({
      refresh: vi.fn(async () => accessToken(sub)),
      fetchMe: vi.fn(async () => (sub === "user-1" ? me() : me("user-2", "grace"))),
    });
    const { session } = makeSession({ api });
    await session.bootstrap();
    expect(api.fetchMe).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(840_000); // same account: /me isn't asked again
    expect(api.fetchMe).toHaveBeenCalledTimes(1);

    sub = "user-2"; // someone else logged in through the shared cookie in another tab
    await vi.advanceTimersByTimeAsync(840_000);
    expect(api.fetchMe).toHaveBeenCalledTimes(2);
    expect(session.getState().user?.username).toBe("grace");
  });

  it("reloadMe refreshes the user", async () => {
    const api = fakeApi();
    const { session } = makeSession({ api });
    await session.bootstrap();
    api.fetchMe.mockResolvedValueOnce({ ...me(), display_name: "Ada L." });
    await session.reloadMe();
    expect(session.getState().user?.display_name).toBe("Ada L.");
  });

  it("signInWithToken logs in with a token another call returned, and tells the other tabs", async () => {
    const bus = fakeBus();
    const tabA = makeSession({ hasHint: () => false, channel: bus.channel() });
    const tabB = makeSession({ hasHint: () => false, channel: bus.channel() });
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);
    expect(tabB.session.getState().status).toBe("anonymous");

    const token = accessToken("user-1");
    await tabA.session.signInWithToken(token);

    expect(tabA.api.login).not.toHaveBeenCalled();
    expect(tabA.api.fetchMe).toHaveBeenCalledWith(token);
    expect(tabA.store.value).toBe(token);
    expect(tabA.session.getState()).toMatchObject({ status: "authenticated", user: me() });
    await vi.waitFor(() => expect(tabB.session.getState().status).toBe("authenticated"));
  });
});

// ---------- the email got verified in another tab ----------

describe("user-changed across tabs", () => {
  /** A bus that also counts what each tab posts. */
  function countingBus() {
    const bus = fakeBus();
    const posted: AuthMessage[] = [];
    return {
      posted,
      channel(): AuthChannel {
        const inner = bus.channel();
        return {
          subscribe: inner.subscribe,
          post: (message) => {
            posted.push(message);
            inner.post(message);
          },
        };
      },
    };
  }

  it("reloadMe tells the other signed-in tabs, which reload /me once and say nothing back", async () => {
    const bus = countingBus();
    const verified = { ...me(), is_email_verified: true };
    const apiA = fakeApi();
    const apiB = fakeApi();
    const tabA = makeSession({ channel: bus.channel(), api: apiA }); // the sign-up tab
    const tabB = makeSession({ channel: bus.channel(), api: apiB }); // the link's tab
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);
    expect(tabA.session.getState().user?.is_email_verified).toBe(false);
    const fetchesBefore = apiA.fetchMe.mock.calls.length;
    apiA.fetchMe.mockResolvedValue(verified);
    apiB.fetchMe.mockResolvedValue(verified);
    bus.posted.length = 0;

    await tabB.session.reloadMe();

    await vi.waitFor(() => expect(tabA.session.getState().user?.is_email_verified).toBe(true));
    expect(apiA.fetchMe).toHaveBeenCalledTimes(fetchesBefore + 1); // exactly one /me
    expect(apiA.refresh).toHaveBeenCalledTimes(1); // only the bootstrap one
    expect(bus.posted).toEqual([{ type: "user-changed" }]); // B's one message, no echo from A
  });

  it("an anonymous tab ignores it: no refresh, no login", async () => {
    const bus = countingBus();
    const anonymousApi = fakeApi();
    const signedIn = makeSession({ channel: bus.channel() });
    const anonymous = makeSession({
      channel: bus.channel(),
      hasHint: () => false,
      api: anonymousApi,
    });
    await Promise.all([signedIn.session.bootstrap(), anonymous.session.bootstrap()]);

    await signedIn.session.reloadMe();

    expect(anonymous.session.getState().status).toBe("anonymous");
    expect(anonymousApi.refresh).not.toHaveBeenCalled();
    expect(anonymousApi.fetchMe).not.toHaveBeenCalled();
  });

  it("a /me failure in the receiving tab changes nothing", async () => {
    const bus = countingBus();
    const apiA = fakeApi();
    const tabA = makeSession({ channel: bus.channel(), api: apiA });
    const tabB = makeSession({ channel: bus.channel() });
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);
    apiA.fetchMe.mockRejectedValue(apiError(0));

    await tabB.session.reloadMe();
    await Promise.resolve();

    expect(tabA.session.getState()).toMatchObject({ status: "authenticated", user: me() });
  });

  it("reloadMe says nothing when there is no token", async () => {
    const bus = countingBus();
    const { session } = makeSession({ channel: bus.channel(), hasHint: () => false });
    await session.bootstrap();
    await session.reloadMe();
    expect(bus.posted).toEqual([]);
  });
});

// ---------- two tabs, one strictly rotating backend ----------

/** One browser cookie jar and a backend whose refresh tokens die the moment they are used. */
class RotatingBackend {
  cookie: string | null = null;
  private valid = new Set<string>();
  private serial = 0;

  logIn(): void {
    this.cookie = this.issue();
  }

  private issue(): string {
    const token = `refresh-${++this.serial}`;
    this.valid.add(token);
    return token;
  }

  api(): AuthApi {
    return fakeApi({
      refresh: vi.fn(async () => {
        const sent = this.cookie; // the browser attaches the cookie when the request starts
        await new Promise((resolve) => setTimeout(resolve, 5)); // the network
        if (!sent || !this.valid.has(sent)) {
          this.cookie = null; // a rejected refresh deletes the cookie
          throw apiError(400);
        }
        this.valid.delete(sent);
        this.cookie = this.issue();
        return accessToken("user-1", 900, this.serial);
      }),
    });
  }
}

describe("two tabs refreshing at once", () => {
  async function bothTabs(lock: SessionDeps["lock"]) {
    const backend = new RotatingBackend();
    backend.logIn();
    const tabA = makeSession({ api: backend.api(), lock });
    const tabB = makeSession({ api: backend.api(), lock });
    await Promise.all([tabA.session.bootstrap(), tabB.session.bootstrap()]);
    // ...and at the next expiry, both again at the same moment.
    await Promise.all([tabA.session.refresh(), tabB.session.refresh()]);
    return { tabA, tabB, backend };
  }

  it("both stay logged in when refreshes share the lock", async () => {
    const { tabA, tabB, backend } = await bothTabs(sharedLock());
    expect(tabA.session.getState().status).toBe("authenticated");
    expect(tabB.session.getState().status).toBe("authenticated");
    expect(backend.cookie).toBe("refresh-5"); // four rotations, a live cookie for the next reload
  });

  it("control: without the lock, one tab loses the race", async () => {
    const { tabA, tabB } = await bothTabs(noLock);
    const statuses = [tabA.session.getState().status, tabB.session.getState().status];
    expect(statuses).toContain("anonymous");
  });
});

// ---------- storage ----------

describe("storage", () => {
  it("never writes the token to localStorage, sessionStorage or document.cookie", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const cookieBefore = document.cookie;
    const { session } = makeSession();
    await session.bootstrap();
    await session.login("a@b.c", "pw");
    await session.refresh();
    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe(cookieBefore);
  });
});
