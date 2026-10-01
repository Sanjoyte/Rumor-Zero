"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { MobileNav } from "./MobileNav";
import type { ShellUser } from "./nav-items";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export interface AppShellProps {
  user: ShellUser | null;
  children: ReactNode;
  /** Opens the composer (Part 4). */
  onNewPost?: () => void;
  /** Overrides the current path for the active item (the `/dev/shell` preview). */
  activePath?: string;
}

/**
 * The logged-in layout (Stitch b1; ARCHITECTURE §10): the full rail at ≥1280px, an icon dock at
 * 768–1279px, and a top bar plus bottom bar below 768px. Pages pick their own container width.
 */
export function AppShell({ user, children, onNewPost, activePath }: AppShellProps) {
  const currentPath = usePathname();
  const pathname = activePath ?? currentPath ?? "/";

  return (
    <div className="min-h-screen bg-surface">
      <a
        href="#main"
        className="sr-only rounded-lg bg-secondary px-space-md py-space-sm font-body-md text-body-md font-semibold text-on-secondary focus:not-sr-only focus:fixed focus:top-space-sm focus:left-space-sm focus:z-[60]"
      >
        Skip to content
      </a>
      <Sidebar user={user} pathname={pathname} onNewPost={onNewPost} />
      <TopBar user={user} />
      <MobileNav user={user} pathname={pathname} onNewPost={onNewPost} />
      <main id="main" className="pt-16 pb-16 md:pb-0 md:pl-16 xl:pl-64">
        {children}
      </main>
    </div>
  );
}
