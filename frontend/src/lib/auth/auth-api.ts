/**
 * The auth endpoints (ARCHITECTURE §7, §9). allauth answers login and signup with the access token
 * in `meta`, and refresh with it in `data`. The refresh token never reaches JavaScript: the backend
 * keeps it in the httpOnly `rz_refresh` cookie.
 *
 * None of these send the in-memory token (`token: false`). Refresh and logout take no AbortSignal:
 * cancelling a refresh after the server rotated the cookie would strand the new token.
 */
import { api, ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

export const AUTH_PATHS = {
  login: "/auth/app/v1/auth/login",
  signup: "/auth/app/v1/auth/signup",
  refresh: "/auth/app/v1/tokens/refresh",
  logout: "/auth/logout/",
  me: "/v1/me/",
  usernameAvailable: "/v1/auth/username-available/",
} as const;

export interface SignupInput {
  email: string;
  username: string;
  password: string;
  turnstileToken: string;
}

interface AllauthTokenBody {
  status: number;
  data?: { access_token?: unknown };
  meta?: { access_token?: unknown };
}

function accessTokenFrom(value: unknown): string {
  if (typeof value === "string" && value) return value;
  // A 200 without a token would be a pending allauth flow, which this app never starts.
  throw new ApiError({
    status: 500,
    code: "no_access_token",
    detail: "Something went wrong. Try again.",
  });
}

export async function login(email: string, password: string): Promise<string> {
  const body = await api.post<AllauthTokenBody>(
    AUTH_PATHS.login,
    { email, password },
    { token: false },
  );
  return accessTokenFrom(body?.meta?.access_token);
}

export async function signup(input: SignupInput): Promise<string> {
  const body = await api.post<AllauthTokenBody>(
    AUTH_PATHS.signup,
    {
      email: input.email,
      username: input.username,
      password: input.password,
      turnstile_token: input.turnstileToken,
    },
    { token: false },
  );
  return accessTokenFrom(body?.meta?.access_token);
}

/** The cookie is the refresh token, so the body is empty. */
export async function refresh(): Promise<string> {
  const body = await api.post<AllauthTokenBody>(AUTH_PATHS.refresh, undefined, { token: false });
  return accessTokenFrom(body?.data?.access_token);
}

export async function logout(): Promise<void> {
  await api.post<void>(AUTH_PATHS.logout, undefined, { token: false });
}

/** With an explicit token, so a 401 here never waits on the refresh that is calling it. */
export async function fetchMe(accessToken: string): Promise<Me> {
  return api.get<Me>(AUTH_PATHS.me, {
    token: false,
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export type AuthApi = {
  login: typeof login;
  signup: typeof signup;
  refresh: typeof refresh;
  logout: typeof logout;
  fetchMe: typeof fetchMe;
};

export const authApi: AuthApi = { login, signup, refresh, logout, fetchMe };
