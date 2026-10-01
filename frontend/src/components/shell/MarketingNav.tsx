"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { buttonClasses } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { cn } from "@/lib/cn";

/** Only pages that exist (user decision, 2026-10-01): About and Community Guidelines are gone. */
export const MARKETING_LINKS = [{ label: "How it works", href: "/how-it-works" }] as const;

/** The public header (Stitch a1 L18–37). The logo replaces the "RUMOR ZERO" text. */
export function MarketingNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-50 w-full border-b border-outline-variant/30 bg-surface-container-lowest">
      <div className="mx-auto flex h-16 max-w-wide items-center justify-between gap-space-md px-space-lg">
        <div className="flex items-center gap-space-md lg:gap-10">
          <Link href="/" className="rounded-lg text-on-surface">
            <Logo size="md" />
          </Link>
          <nav
            aria-label="Site"
            className="hidden items-center gap-space-md font-body-md text-body-md font-medium text-on-surface-variant md:flex lg:gap-space-xl"
          >
            {MARKETING_LINKS.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "lg:whitespace-nowrap",
                    active
                      ? "font-semibold text-on-surface"
                      : "transition-colors hover:text-on-surface",
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-space-md font-body-md text-body-md lg:gap-space-lg">
          <Link
            href="/login"
            className="font-medium whitespace-nowrap text-secondary transition-colors hover:text-on-secondary-container hover:underline"
          >
            Log in
          </Link>
          <Link href="/signup" className={buttonClasses({ className: "whitespace-nowrap" })}>
            Sign up
          </Link>
        </div>
      </div>
    </header>
  );
}
