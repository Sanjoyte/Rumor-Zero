"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { MESSAGES } from "@/features/auth/messages";
import { UnreadCountProvider, useUnreadCount } from "@/features/notifications/UnreadCountProvider";
import { useResendVerification } from "@/features/auth/useResendVerification";
import { ComposerProvider, useComposer } from "@/features/posts/ComposerProvider";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isProtectedPath, loginRedirectFor } from "@/lib/auth/route-guard";

const LOGOUT_FAILED = "Couldn't log out. Check your connection and try again.";

/**
 * Every app page sits in the shell. Pages that need a user (`PROTECTED_PREFIXES`) show a
 * placeholder while the session is restored, and send anonymous visitors to `/login?next=…`.
 * The composer lives above the shell (Part 4), so every "New post" button opens the same one, and so
 * does the unread count (Part 13): one poll feeds the badge and the notifications page.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <UnreadCountProvider>
      <ComposerProvider>
        <AppFrame>{children}</AppFrame>
      </ComposerProvider>
    </UnreadCountProvider>
  );
}

function AppFrame({ children }: { children: ReactNode }) {
  const { status, user, logout } = useAuth();
  const composer = useComposer();
  const unread = useUnreadCount();
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const toast = useToast();
  const loggingOut = useRef(false);
  // The banner's Resend answers with a toast; the shell itself stays presentational.
  const resend = useResendVerification({
    onResult: ({ tone, message }) =>
      toast.show(message, { tone: tone === "info" ? "neutral" : tone }),
  });
  const onNewPostBlocked = useCallback(() => toast.show(MESSAGES.newPostBlocked), [toast]);
  const guarded = isProtectedPath(pathname);

  useEffect(() => {
    if (!guarded || status !== "anonymous" || loggingOut.current) return;
    router.replace(loginRedirectFor(window.location.pathname + window.location.search));
  }, [guarded, status, router]);

  const onLogout = useCallback(() => {
    // Logging out on a protected page must go to /login, not /login?next=<that page>.
    loggingOut.current = true;
    logout().then(
      () => router.replace("/login"),
      () => {
        loggingOut.current = false;
        toast.show(LOGOUT_FAILED, { tone: "error" });
      },
    );
  }, [logout, router, toast]);

  return (
    <AppShell
      user={user}
      status={status}
      onLogout={onLogout}
      onNewPost={composer.open}
      onNewPostBlocked={onNewPostBlocked}
      onResend={() => void resend.resend()}
      resendSecondsLeft={resend.secondsLeft}
      resending={resend.busy}
      unreadCount={unread.count}
    >
      {guarded && status !== "authenticated" ? <PageSkeleton /> : children}
    </AppShell>
  );
}

function PageSkeleton() {
  return (
    <div
      aria-busy="true"
      className="mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg"
    >
      <span className="sr-only">Loading…</span>
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
