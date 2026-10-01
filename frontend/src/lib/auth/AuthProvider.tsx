"use client";

/**
 * Who is signed in. Part 0C is the skeleton: everyone is anonymous. Part 1 adds the refresh on
 * load, the scheduled refresh before expiry, the 401 refresh-and-retry (through `withRefreshLock`)
 * and logout.
 */
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { setAccessTokenGetter, setUnauthorizedHandler } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { getAccessToken } from "./token-store";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export interface AuthState {
  status: AuthStatus;
  user: Me | null;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    setAccessTokenGetter(getAccessToken);
    // No refresh yet, so a 401 is final. Part 1 refreshes here and returns true to retry.
    setUnauthorizedHandler(async () => false);
    return () => setUnauthorizedHandler(null);
  }, []);

  const value = useMemo<AuthState>(() => ({ status: "anonymous", user: null }), []);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth() must be used inside <AuthProvider>");
  return state;
}
