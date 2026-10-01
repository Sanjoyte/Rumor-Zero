import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";

/**
 * Every auth page shares this card (Stitch a2 page and card; a3's brand-header spot). The logo
 * replaces the per-page emblem tiles and taglines (ANALYSIS e.2). Also frames the 404/500 pages.
 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-space-md py-10 sm:px-space-lg">
      <main id="main" className="w-full max-w-form">
        <div className="w-full rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-xl shadow-sm sm:p-11">
          <div className="mb-space-lg flex justify-center">
            <Link href="/" className="rounded-lg">
              <Logo size="lg" />
            </Link>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
