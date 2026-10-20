"use client";

/**
 * Who is signed in (ARCHITECTURE §7). A thin React binding of `AuthSession`: one session per
 * browser tab, created on first use, so React StrictMode's double effects can't bootstrap twice.
 * The access token stays in memory (`token-store`), never in localStorage, sessionStorage or a
 * script-readable cookie.
 */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { setAccessTokenGetter, setUnauthorizedHandler } from "@/lib/api/client";
import { authApi, type SignupInput } from "./auth-api";
import { withRefreshLock } from "./refresh-lock";
import {
  AuthSession,
  type AuthChannel,
  type AuthMessage,
  type AuthState,
  type AuthStatus,
  type Visibility,
} from "./session";
import { hasSessionHint } from "./session-hint";
import { getAccessToken, setAccessToken } from "./token-store";

export type { AuthState, AuthStatus };

export interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  signup: (input: SignupInput) => Promise<void>;
  /** Log in with the access token a password reset returned (the refresh cookie is already set). */
  signInWithToken: (token: string) => Promise<void>;
  /** Throws (and changes nothing) when the server can't be reached. */
  logout: () => Promise<void>;
  /** Become anonymous without a request: the account was just deleted (Part 14). */
  endSession: () => void;
  reloadMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// The server render, and the first client render that hydrates it, don't know the user yet.
const LOADING: AuthState = { status: "loading", user: null };
const CHANNEL_NAME = "rz-auth";

function browserChannel(): AuthChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  const channel = new BroadcastChannel(CHANNEL_NAME);
  return {
    post: (message) => channel.postMessage(message),
    subscribe: (listener) => {
      const onMessage = (event: MessageEvent<AuthMessage>) => listener(event.data);
      channel.addEventListener("message", onMessage);
      return () => {
        channel.removeEventListener("message", onMessage);
        channel.close();
      };
    },
  };
}

const documentVisibility: Visibility = {
  isVisible: () => document.visibilityState === "visible",
  onVisible: (listener) => {
    const onChange = () => {
      if (document.visibilityState === "visible") listener();
    };
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  },
};

let browserSession: AuthSession | null = null;

/** The tab's session (created on first use). Exported for tests, which reset it. */
export function getBrowserSession(): AuthSession {
  browserSession ??= new AuthSession({
    api: authApi,
    lock: withRefreshLock,
    store: { get: getAccessToken, set: setAccessToken },
    hasHint: () => hasSessionHint(),
    channel: browserChannel(),
    visibility: documentVisibility,
  });
  return browserSession;
}

export function resetBrowserSessionForTests(): void {
  browserSession?.dispose();
  browserSession = null;
}

export function AuthProvider({
  children,
  session: injected,
}: {
  children: ReactNode;
  /** Tests pass their own session. */
  session?: AuthSession;
}) {
  const session = typeof window === "undefined" ? null : (injected ?? getBrowserSession());

  const state = useSyncExternalStore(
    session?.subscribe ?? noSubscribe,
    session?.getState ?? loadingState,
    loadingState,
  );

  useEffect(() => {
    if (!session) return;
    setAccessTokenGetter(getAccessToken);
    setUnauthorizedHandler(() => session.handleUnauthorized());
    void session.bootstrap();
    return () => setUnauthorizedHandler(null);
  }, [session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login: (email, password) => requireSession(session).login(email, password),
      signup: (input) => requireSession(session).signup(input),
      signInWithToken: (token) => requireSession(session).signInWithToken(token),
      logout: () => requireSession(session).logout(),
      endSession: () => requireSession(session).endSession(),
      reloadMe: () => requireSession(session).reloadMe(),
    }),
    [state, session],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function noSubscribe(): () => void {
  return () => {};
}

function loadingState(): AuthState {
  return LOADING;
}

function requireSession(session: AuthSession | null): AuthSession {
  if (!session) throw new Error("Auth actions run in the browser only");
  return session;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
