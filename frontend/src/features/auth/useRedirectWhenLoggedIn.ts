"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth/AuthProvider";
import { safeNextPath } from "@/lib/auth/next-path";

/**
 * On /login and /signup: a logged-in visitor (including one who just logged in or signed up)
 * goes on to `?next=` when it is safe, else /home. `next` is read from the address at redirect
 * time, so the pages stay prerendered (useSearchParams would need a Suspense boundary).
 * `skip.current` true switches it off (read when the status changes).
 */
export function useRedirectWhenLoggedIn({ skip }: { skip?: { current: boolean } } = {}): void {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => {
    // The sign-up form sets `skip` while it submits: it sends a new account to /verify-email.
    if (status !== "authenticated" || skip?.current) return;
    const next = new URLSearchParams(window.location.search).get("next");
    router.replace(safeNextPath(next) ?? "/home");
  }, [status, router, skip]);
}
