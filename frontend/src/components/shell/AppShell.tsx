"use client";

import { usePathname } from "next/navigation";
import { useMemo, type ReactNode } from "react";
import type { MenuAction } from "./AccountMenu";
import { MobileNav } from "./MobileNav";
import { LOG_OUT, type ShellUser } from "./nav-items";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { UnverifiedBanner } from "./UnverifiedBanner";

export interface AppShellProps {
  user: ShellUser | null;
  /** `loading` while the session is restored: the account areas show placeholders. */
  status?: "loading" | "anonymous" | "authenticated";
  children: ReactNode;
  /** Opens the composer (Part 4). */
  onNewPost?: () => void;
  /** New post was pressed while the email is unverified: explain why nothing opens. */
  onNewPostBlocked?: () => void;
  /** Resend in the unverified banner (the layout owns the request and the countdown). */
  onResend?: () => void;
  resendSecondsLeft?: number;
  resending?: boolean;
  /** Adds Log out to the user menu and the phone account sheet. */
  onLogout?: () => void;
  /** Overrides the current path for the active item (the `/dev/shell` preview). */
  activePath?: string;
}

/**
 * The logged-in layout (Stitch b1; ARCHITECTURE §10): the full rail at ≥1280px, an icon dock at
 * 768–1279px, and a top bar plus bottom bar below 768px. Pages pick their own container width.
 */
export function AppShell({
  user,
  status,
  children,
  onNewPost,
  onNewPostBlocked,
  onResend,
  resendSecondsLeft,
  resending,
  onLogout,
  activePath,
}: AppShellProps) {
  const currentPath = usePathname();
  const pathname = activePath ?? currentPath ?? "/";
  const loading = status === "loading";
  const shownUser = loading ? null : user;
  const actions = useMemo<MenuAction[]>(
    () => (onLogout ? [{ ...LOG_OUT, onSelect: onLogout }] : []),
    [onLogout],
  );

  return (
    <div className="min-h-screen bg-surface">
      <a
        href="#main"
        className="sr-only rounded-lg bg-secondary px-space-md py-space-sm font-body-md text-body-md font-semibold text-on-secondary focus:not-sr-only focus:fixed focus:top-space-sm focus:left-space-sm focus:z-[60]"
      >
        Skip to content
      </a>
      <Sidebar
        user={shownUser}
        loading={loading}
        pathname={pathname}
        onNewPost={onNewPost}
        onNewPostBlocked={onNewPostBlocked}
        actions={actions}
      />
      <TopBar user={shownUser} loading={loading} />
      <MobileNav
        user={shownUser}
        loading={loading}
        pathname={pathname}
        onNewPost={onNewPost}
        onNewPostBlocked={onNewPostBlocked}
        actions={actions}
      />
      <main id="main" className="pt-16 pb-16 md:pb-0 md:pl-16 xl:pl-64">
        {shownUser && !shownUser.is_email_verified && (
          <UnverifiedBanner onResend={onResend} secondsLeft={resendSecondsLeft} busy={resending} />
        )}
        {children}
      </main>
    </div>
  );
}
