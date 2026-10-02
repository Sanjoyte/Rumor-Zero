import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ShellPreview } from "@/features/dev/ShellPreview";

export const metadata: Metadata = {
  title: "Shell preview",
  robots: { index: false, follow: false },
};

type Props = { searchParams: Promise<{ user?: string; path?: string }> };

/**
 * Development-only: the app shell with a sample user, for the Stitch b1 comparison. `?user=none` shows the logged-out shell; `?path=/search` moves the
 * active item. A production build answers 404 for this route.
 */
export default async function DevShellPage({ searchParams }: Props) {
  if (process.env.NODE_ENV === "production") notFound();
  const { user, path } = await searchParams;
  return <ShellPreview loggedIn={user !== "none"} activePath={path ?? "/home"} />;
}
