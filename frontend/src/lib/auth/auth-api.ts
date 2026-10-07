/**
 * The auth endpoints (ARCHITECTURE §7, §9). allauth answers login and signup with the access token
 * in `meta`, and refresh with it in `data`. The refresh token never reaches JavaScript: the backend
 * keeps it in the httpOnly `rz_refresh` cookie.
 *
 * None of these send the in-memory token (`token: false`), except `resendVerificationEmail`, which
 * is an ordinary app call. Refresh and logout take no AbortSignal: cancelling a refresh after the
 * server rotated the cookie would strand the new token.
 *
 * The email-flow calls (Part 2) are standalone exports, not part of the `AuthApi` type that the
 * session injects: the session never needs them.
 */
import { api, ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

export const AUTH_PATHS = {
  login: "/auth/app/v1/auth/login",
  signup: "/auth/app/v1/auth/signup",
  refresh: "/auth/app/v1/tokens/refresh",
  logout: "/auth/logout/",
  verifyEmail: "/auth/app/v1/auth/email/verify",
  passwordRequest: "/auth/app/v1/auth/password/request",
  passwordReset: "/auth/app/v1/auth/password/reset",
  me: "/v1/me/",
  verificationEmail: "/v1/me/verification-email/",
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

/** Header that carries the reset key for the pre-check (GET has no body). */
export const RESET_KEY_HEADER = "X-Password-Reset-Key";

/**
 * Confirm the address behind a verification link. 200 means verified; 400 `invalid_or_expired_key`
 * covers expired, used and forged keys. Anonymous on purpose: a link never logs anyone in.
 */
export async function verifyEmail(key: string): Promise<void> {
  await api.post<unknown>(AUTH_PATHS.verifyEmail, { key }, { token: false });
}

/** Always 200 for a well-formed address, whether or not an account exists (no enumeration). */
export async function requestPasswordReset(email: string): Promise<void> {
  await api.post<unknown>(AUTH_PATHS.passwordRequest, { email }, { token: false });
}

/** Is the key from a reset link still good? 200 yes, 400 `invalid_password_reset` no. */
export async function checkResetKey(key: string): Promise<void> {
  await api.get<unknown>(AUTH_PATHS.passwordReset, {
    token: false,
    headers: { [RESET_KEY_HEADER]: key },
  });
}

/** Sets the new password and logs in: resolves with the access token (the cookie is set too). */
export async function resetPassword(key: string, password: string): Promise<string> {
  const body = await api.post<AllauthTokenBody>(
    AUTH_PATHS.passwordReset,
    { key, password },
    { token: false },
  );
  return accessTokenFrom(body?.meta?.access_token);
}

/**
 * Send the signed-in user a new verification link. 204 sent; 409 `already_verified`; 429
 * `verification_email_throttled`. An ordinary app call: Bearer token, retried after a 401 refresh.
 */
export async function resendVerificationEmail(): Promise<void> {
  await api.post<void>(AUTH_PATHS.verificationEmail);
}

export type AuthApi = {
  login: typeof login;
  signup: typeof signup;
  refresh: typeof refresh;
  logout: typeof logout;
  fetchMe: typeof fetchMe;
};

export const authApi: AuthApi = { login, signup, refresh, logout, fetchMe };
