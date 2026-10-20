/** Shared test helpers for the auth forms (not shipped: only *.test.tsx files import it). */
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi, type Mock } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import type { AuthApi } from "@/lib/auth/auth-api";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { AuthSession } from "@/lib/auth/session";
import type {
  GoogleButtonOptions,
  GoogleCredentialResponse,
  GoogleIdentityApi,
} from "@/lib/google-identity";

export const ME: Me = {
  id: "u-1",
  username: "ada",
  display_name: "",
  bio: "",
  email: "ada@example.test",
  is_email_verified: false,
  role: "user",
  has_usable_password: true,
  google_connected: false,
  avatar_url: null,
  public_score: null,
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

export type MockedAuthApi = { [K in keyof AuthApi]: Mock<AuthApi[K]> };

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
  } as MockedAuthApi;
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

export const GOOGLE_CLIENT_ID = "123456789012-abc.apps.googleusercontent.com";

/**
 * Installs a fake `window.google` (what Google's script defines). `credential()` plays the part
 * of the callback Google fires when a person finishes the popup. Remove it with
 * `delete window.google`.
 */
export function fakeGoogleIdentity() {
  const buttons: GoogleButtonOptions[] = [];
  let callback: ((response: GoogleCredentialResponse) => void) | null = null;
  const api = {
    initialize: vi.fn((config: Parameters<GoogleIdentityApi["initialize"]>[0]) => {
      callback = config.callback;
    }),
    renderButton: vi.fn((parent: HTMLElement, options: GoogleButtonOptions) => {
      buttons.push(options);
      const frame = document.createElement("div");
      frame.dataset.testid = "google-iframe";
      parent.appendChild(frame);
    }),
  } satisfies GoogleIdentityApi;
  window.google = { accounts: { id: api } };
  return {
    api,
    buttons,
    credential: (value = "google-id-token") => callback?.({ credential: value }),
    click: () => buttons[buttons.length - 1]?.click_listener?.(),
  };
}
