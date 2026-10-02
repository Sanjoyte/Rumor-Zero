/** Shared test helpers for the auth forms (not shipped: only *.test.tsx files import it). */
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import type { AuthApi } from "@/lib/auth/auth-api";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { AuthSession } from "@/lib/auth/session";

export const ME: Me = {
  id: "u-1",
  username: "ada",
  display_name: "",
  email: "ada@example.test",
  is_email_verified: false,
  role: "user",
  has_usable_password: true,
  google_connected: false,
  avatar_url: null,
};

export function allauthError(
  status: number,
  errors: { code: string; message: string; param?: string }[] = [],
): ApiError {
  const fieldErrors: Record<string, string[]> = {};
  for (const error of errors)
    (fieldErrors[error.param ?? "non_field_errors"] ??= []).push(error.message);
  return new ApiError({
    status,
    code: errors[0]?.code ?? `http_${status}`,
    detail: errors[0]?.message ?? "",
    fieldErrors,
  });
}

/** A session whose API calls are mocks, logged out unless `loggedIn`. */
export function testSession(api: Partial<AuthApi> = {}, { loggedIn = false } = {}) {
  let token: string | null = null;
  const mocks = {
    login: vi.fn(async () => "access-token"),
    signup: vi.fn(async () => "access-token"),
    refresh: vi.fn(async () => "access-token"),
    logout: vi.fn(async () => undefined),
    fetchMe: vi.fn(async () => ME),
    ...api,
  };
  const session = new AuthSession({
    api: mocks,
    lock: (task) => task(),
    store: { get: () => token, set: (value) => (token = value) },
    hasHint: () => loggedIn,
  });
  return { session, api: mocks };
}

export function renderWithSession(ui: ReactNode, session: AuthSession) {
  return render(<AuthProvider session={session}>{ui}</AuthProvider>);
}
