/** Shared test helpers for Settings (not shipped: only *.test.tsx files import it). */
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { ME, testSession } from "@/features/auth/test-helpers";
import type { Me } from "@/lib/api/types";
import { AuthProvider } from "@/lib/auth/AuthProvider";

export const SETTINGS_ME: Me = {
  ...ME,
  is_email_verified: true,
  display_name: "Ada L.",
  bio: "Hi",
};

/** The signed-in session and the toast region around `ui`; `me` overrides fields of the user. */
export function renderSettings(ui: ReactNode, me: Partial<Me> = {}) {
  const user = { ...SETTINGS_ME, ...me };
  const fetchMe = vi.fn(async () => user);
  const session = testSession({ fetchMe }, { loggedIn: true });
  const wrap = (node: ReactNode) => (
    <AuthProvider session={session.session}>
      <ToastProvider>{node}</ToastProvider>
    </AuthProvider>
  );
  const view = render(wrap(ui));
  // `rerender` keeps the providers, so a test can change props without losing the session.
  return {
    ...view,
    ...session,
    user,
    fetchMe,
    rerender: (next: ReactNode) => view.rerender(wrap(next)),
  };
}
