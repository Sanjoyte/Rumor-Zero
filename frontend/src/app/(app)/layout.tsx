"use client";

import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { useAuth } from "@/lib/auth/AuthProvider";

/** Every app page sits in the shell. Part 1 adds the route guard for pages that need a user. */
export default function AppLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return <AppShell user={user}>{children}</AppShell>;
}
